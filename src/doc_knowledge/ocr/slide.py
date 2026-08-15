"""幻灯片级 OCR 服务 — 整页渲染 + 云端 VLM 三位一体意图识别（方案C）

与图像级 OCR（OCRService 系列：cloud/local/hybrid）不同，slide 模式把
**整页幻灯片渲染成图片**，让具备视觉理解能力的云端 VLM 直接读取
"文字 + 图片 + 空间"三维信息，输出结构化理解（图表语义、表格结构化、页面主旨）。

流程：soffice PPTX→PDF（完整渲染）→ fitz 整页 PNG → 云端 VLM → {页码: 文本}
"""

import logging
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from doc_knowledge.vision import LLMVisionService

logger = logging.getLogger(__name__)


DEFAULT_SLIDE_PROMPT = (
    "你正在分析一页 PPT 幻灯片。请用约定标记 Markdown 输出，不要输出 JSON：\n"
    "每个标记单独占一行，标记后换行写对应内容：\n"
    "[DK-标题] 本页标题\n"
    "[DK-概述] 全文概述（1-2 句话）\n"
    "[DK-结构] 本页内容逻辑结构，从以下 7 种中选一"
    "（一页混合多种时标注主结构，如\"总分结构（局部递进）\"）：\n"
    "   并列 / 递进 / 总分 / 分总 / 总分总 / 对比 / 矩阵象限\n"
    "[DK-正文] 按识别结构组织的正文，转译规则——\n"
    "   文字 → 文字；表格 → Markdown 表格；\n"
    "   数据型图表（柱状/折线/饼图/散点，含数值）→ Markdown 表格；\n"
    "   概念型图形（示意/流程图/装饰）→ 文字描述\n"
    "   [DK-正文] 之后的全部内容即正文，可含任意 Markdown；\n"
    "   多栏/并列内容用 Markdown 标题 + 列表组织\n"
    "[DK-标题]、[DK-概述]、[DK-结构] 均必须输出，不得省略；\n"
    "[DK-正文] 不可省略。"
)


def _find_soffice() -> str:
    """探测 LibreOffice soffice 可执行文件路径（PATH 或常见安装路径）"""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return ""


def _page_num(img: Path) -> int:
    """从 page{N}.png 文件名提取页码（供 recognize_slides / retry_pages 共用）"""
    m = re.search(r"page(\d+)\.png$", img.name)
    return int(m.group(1)) if m else 0


def _is_success(text: str | None) -> bool:
    """识别成功判定：非空且非错误标记（[图片识别失败: ...] / [图片解析失败: ...]）

    不再用"以 [ 开头即失败"：约定标记 Markdown（[DK-标题] 等）也以 [ 开头，
    精确匹配错误前缀，避免把正常标记输出误判为失败而无限重试。
    text 可为 None（推理模型 content:null 时回退后仍可能为空），None 判定为失败。
    """
    if text is None:
        return False
    return bool(text.strip()) and not text.startswith(
        ("[图片识别失败", "[图片解析失败")
    )


class SlideFusionService:
    """幻灯片级三位一体意图识别服务（slide 模式）

    双契约接口（见 08-OCR统一管道设计.md §7.3）：
    - 图像级接口 `OCRService.recognize_batch(image_paths)`  → cloud/local/hybrid
    - 页面级接口 `SlideFusionService.recognize_slides(pages)` → slide
    """

    def __init__(
        self,
        api_url: str,
        api_key: str = "",
        model: str = "glm-4.6v-flash",
        dpi: int = 150,
        prompt: Optional[str] = None,
        max_concurrency: int = 1,
        timeout: int = 120,
        libreoffice_path: str = "",
        max_tokens: int = 1024,
    ):
        # 默认并发 1：glm-4.6v-flash 等免费模型的 API 对并发请求限流
        # （并发 >1 会触发 401/连接重置）。用户可在需要时调高。
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.dpi = dpi
        self.prompt = prompt or DEFAULT_SLIDE_PROMPT
        self.libreoffice_path = libreoffice_path
        self._vision = LLMVisionService(
            api_url=api_url,
            api_key=api_key,
            model=model,
            system_prompt=(
                "你是幻灯片内容理解助手。请严格按照用户要求的约定标记 Markdown"
                " 格式输出，不输出多余内容。"
            ),
            user_text=self.prompt,
            timeout=timeout,
            max_workers=max_concurrency,
            max_tokens=max_tokens,
        )

    def process_pptx(self, pptx_path: Path, output_dir: Path, verbose: bool = False) -> dict[int, str]:
        """完整流程：soffice → PDF → 整页 PNG → VLM，返回 {页码: 结构化文本}

        临时目录（PDF / 整页 PNG）用完即清理，不落盘到输出目录 B。
        """
        work_dir = Path(tempfile.mkdtemp(prefix="dck_slide_", dir=output_dir))
        try:
            pdf = self._convert_pptx_to_pdf(pptx_path, work_dir)
            pages = self._render_pdf_to_pages(pdf, work_dir)
            return self.recognize_slides(pages, verbose=verbose)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def retry_pages(
        self,
        pptx_path: Path,
        output_dir: Path,
        page_numbers: list[int],
        verbose: bool = False,
    ) -> dict[int, str]:
        """渲染源 PPTX 后仅识别指定页（CLI retry-slide 补跑用）

        复用 process_pptx 的渲染流程，但只对 page_numbers 中的页送 VLM，
        不重跑成功页、省额度。识别仍带自动二次补跑（retry_failed_pass=True）。
        """
        if not page_numbers:
            return {}
        work_dir = Path(tempfile.mkdtemp(prefix="dck_slide_", dir=output_dir))
        try:
            pdf = self._convert_pptx_to_pdf(pptx_path, work_dir)
            all_pages = self._render_pdf_to_pages(pdf, work_dir)
            targets = set(page_numbers)
            wanted = [p for p in all_pages if _page_num(p) in targets]
            return self.recognize_slides(wanted, verbose=verbose)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _convert_pptx_to_pdf(self, pptx_path: Path, work_dir: Path) -> Path:
        """soffice headless PPTX→PDF，返回 PDF 路径"""
        soffice = self.libreoffice_path or _find_soffice()
        if not soffice:
            raise RuntimeError(
                "未找到 LibreOffice（soffice）。slide 模式需要完整渲染，请先安装 "
                "LibreOffice（Windows: winget install TheDocumentFoundation.LibreOffice），"
                "或在配置 ocr.slide.libreoffice_path 中指定路径。"
            )
        cmd = [
            soffice, "--headless", "--convert-to", "pdf",
            "--outdir", str(work_dir), str(pptx_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        pdf = work_dir / f"{pptx_path.stem}.pdf"
        if not pdf.exists():
            raise RuntimeError(f"soffice 转换失败：未生成 PDF：{pdf}")
        return pdf

    def _render_pdf_to_pages(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """fitz 渲染 PDF 每页为 PNG，返回 page1.png, page2.png, ...（数字序）"""
        import fitz

        images_dir = output_dir / "_slide_pages"
        images_dir.mkdir(parents=True, exist_ok=True)
        pages: list[Path] = []
        doc = fitz.open(str(pdf_path))
        try:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=self.dpi)
                img = images_dir / f"page{i + 1}.png"
                pix.save(str(img))
                pages.append(img)
        finally:
            doc.close()
        return pages

    def recognize_slides(
        self,
        page_images: list[Path],
        verbose: bool = False,
        max_retries: int = 3,
        retry_base_delay: float = 5.0,
        retry_failed_pass: bool = True,
    ) -> dict[int, str]:
        """送云端 VLM 识别整页截图，返回 {页码: 结构化文本}

        并发度由 max_concurrency 控制（默认 1=串行，免费 VLM 对并发/速率
        限流）；并发 >1 时用线程池并行发送，各页独立重试互不阻塞，
        结果仍按页码顺序返回。429/连接失败/空响应时按 5s → 10s → 20s
        指数退避重试，等待额度恢复。

        retry_failed_pass=True（默认）：第一轮全页识别后，对失败页再补跑一轮。
        第二轮时距第一轮已隔一段时间，限流额度恢复，失败页补跑成功率显著提升。

        页码从文件名 page{N}.png 提取；非该命名时按传入顺序兜底。
        """

        # 建立 页码 → 图片 映射（有序）
        pairs: list[tuple[int, Path]] = []
        fallback = 0
        for img in sorted(page_images, key=_page_num):
            num = _page_num(img)
            if num:
                pairs.append((num, img))
            else:
                fallback += 1
                pairs.append((fallback, img))
        # 同名页码去重（setdefault 语义：保留第一个）
        seen: set[int] = set()
        unique_pairs: list[tuple[int, Path]] = []
        for num, img in pairs:
            if num not in seen:
                seen.add(num)
                unique_pairs.append((num, img))
        img_by_num = dict(unique_pairs)

        results = self._recognize_pass(
            unique_pairs, verbose=verbose,
            max_retries=max_retries, retry_base_delay=retry_base_delay,
        )

        # 自动二次补跑：仅对失败页再来一轮
        if retry_failed_pass:
            failed = [num for num, text in results.items() if not _is_success(text)]
            if failed:
                if verbose:
                    print(f"  自动补跑 {len(failed)} 个失败页: {sorted(failed)}")
                retry_pairs = [(num, img_by_num[num]) for num in failed
                               if num in img_by_num]
                results.update(self._recognize_pass(
                    retry_pairs, verbose=verbose,
                    max_retries=max_retries, retry_base_delay=retry_base_delay,
                ))
        return dict(sorted(results.items()))

    def _recognize_pass(
        self,
        pairs: list[tuple[int, Path]],
        verbose: bool,
        max_retries: int,
        retry_base_delay: float,
    ) -> dict[int, str]:
        """单轮识别：max_concurrency > 1 时线程池并行，否则串行

        各页独立走 _recognize_with_retry（含指数退避），并行时退避等待
        只阻塞本页线程，不再拖住后续所有页。
        """
        workers = self._vision.max_workers
        if workers <= 1 or len(pairs) <= 1:
            return {
                num: self._recognize_with_retry(
                    img, verbose=verbose, max_retries=max_retries,
                    retry_base_delay=retry_base_delay,
                )
                for num, img in pairs
            }

        results: dict[int, str] = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_num = {
                executor.submit(
                    self._recognize_with_retry,
                    img, verbose=verbose, max_retries=max_retries,
                    retry_base_delay=retry_base_delay,
                ): num
                for num, img in pairs
            }
            for future in future_to_num:
                num = future_to_num[future]
                try:
                    results[num] = future.result()
                except Exception as e:
                    # recognize_image 内部已捕获网络/解析异常，这里是兜底
                    logger.warning("第 %d 页识别线程异常: %s", num, e)
                    results[num] = f"[图片识别失败: {e}]"
        return results

    def _recognize_with_retry(
        self,
        img: Path,
        verbose: bool,
        max_retries: int,
        retry_base_delay: float,
    ) -> str:
        """单张识别，空串/错误标记（429/连接失败）时指数退避重试"""
        for attempt in range(max_retries + 1):
            text = self._vision.recognize_image(img)
            # 成功条件见 _is_success：空串/纯空白/错误标记（[图片识别失败: ...]）均重试。
            # 空串不能算成功——真实验证中发现 VLM 偶发返回 ""，放行会静默丢失整页注入。
            if _is_success(text):
                return text
            if attempt < max_retries:
                delay = retry_base_delay * (2 ** attempt)
                if verbose:
                    print(
                        f"  {img.name} 识别失败（{text[:50]}），"
                        f"{delay:.0f}s 后重试（{attempt + 1}/{max_retries}）"
                    )
                time.sleep(delay)
        return text
