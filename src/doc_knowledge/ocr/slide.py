"""幻灯片级 OCR 服务 — 整页渲染 + 云端 VLM 三位一体意图识别（方案C）

与图像级 OCR（OCRService 系列：cloud/local/hybrid）不同，slide 模式把
**整页幻灯片渲染成图片**，让具备视觉理解能力的云端 VLM 直接读取
"文字 + 图片 + 空间"三维信息，输出结构化理解（图表语义、表格结构化、页面主旨）。

流程：soffice PPTX→PDF（完整渲染）→ fitz 整页 PNG → 云端 VLM → {页码: 文本}
"""

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from doc_knowledge.vision import LLMVisionService


DEFAULT_SLIDE_PROMPT = (
    "你正在分析一页 PPT 幻灯片。请输出结构化 JSON：\n"
    "1. page_summary：本页主旨（1-2 句话）\n"
    "2. charts：本页的图表列表（类型：柱状/折线/饼图/雷达/散点…；标题；X轴/Y轴含义；"
    "关键数据点；趋势或结论）\n"
    "3. tables：本页的表格（转为 Markdown 表格）\n"
    "4. layout_notes：图文之间的空间关系（如\"左图右文，图解释了文字中的市场规模趋势\"）\n"
    "只输出 JSON，不要额外解释。"
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


def _is_success(text: str) -> bool:
    """识别成功判定：非空且非错误标记（[图片识别失败: ...]）"""
    return bool(text.strip()) and not text.startswith("[")


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
                "你是幻灯片内容理解助手。请严格按照用户要求的 JSON 结构输出，"
                "不输出多余内容。"
            ),
            user_text=self.prompt,
            timeout=timeout,
            max_workers=max_concurrency,
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
        """逐张送云端 VLM，返回 {页码: 结构化文本}

        串行发送（免费 VLM 对并发/速率限流）；429/连接失败/空响应时
        按 5s → 10s → 20s 指数退避重试，等待额度恢复。

        retry_failed_pass=True（默认）：第一轮全页识别后，对失败页再补跑一轮。
        第二轮时距第一轮已隔一段时间，限流额度恢复，失败页补跑成功率显著提升。

        页码从文件名 page{N}.png 提取；非该命名时按传入顺序兜底。
        """

        results: dict[int, str] = {}
        fallback = 0
        img_by_num: dict[int, Path] = {}
        for img in sorted(page_images, key=_page_num):
            num = _page_num(img)
            img_by_num.setdefault(num, img)
            text = self._recognize_with_retry(
                img, verbose=verbose, max_retries=max_retries,
                retry_base_delay=retry_base_delay,
            )
            if num:
                results[num] = text
            else:
                fallback += 1
                results[fallback] = text

        # 自动二次补跑：仅对失败页再来一轮
        if retry_failed_pass:
            failed = [num for num, text in results.items() if not _is_success(text)]
            if failed:
                if verbose:
                    print(f"  自动补跑 {len(failed)} 个失败页: {sorted(failed)}")
                for num in failed:
                    img = img_by_num.get(num)
                    if img is not None:
                        results[num] = self._recognize_with_retry(
                            img, verbose=verbose, max_retries=max_retries,
                            retry_base_delay=retry_base_delay,
                        )
        return dict(sorted(results.items()))

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
