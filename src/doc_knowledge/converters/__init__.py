"""文档转换器包 - 基于 MarkItDown 封装"""

from pathlib import Path
from typing import Optional


_PDF_TEXT_DENSITY_THRESHOLD = 50  # 平均每页字符数阈值


def _pdf_has_text_layer(pdf_path: Path) -> bool:
    """检测 PDF 是否有可提取的文字层（按平均每页字符密度判断）

    旧策略"任意一页 >10 字符即认为有文字"会把扫描件中的页眉/水印误判为文字层。
    新策略：总文字字符数 / 页数 ≥ 50 才认为是真正的文字 PDF。

    阈值依据：典型水印（"Page 1 of 3"、"Confidential"）通常 <30 字符/页；
    正常段落文字通常 >100 字符/页。50 留出足够缓冲。

    导入或读取失败时返回 True（不确定时倾向跳过 OCR，避免无效 API 调用）。
    """
    try:
        import fitz
    except ImportError:
        return True

    try:
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return False
        total_chars = sum(len(page.get_text().strip()) for page in doc)
        doc.close()
        return (total_chars / page_count) >= _PDF_TEXT_DENSITY_THRESHOLD
    except Exception:
        return True


def _render_pdf_pages(pdf_path: Path, output_dir: Path) -> list[Path]:
    """将 PDF 每一页渲染为 PNG 图片，返回图片路径列表"""
    try:
        import fitz
    except ImportError:
        return []

    images = []
    try:
        doc = fitz.open(str(pdf_path))
        images_dir = output_dir / f"{pdf_path.name}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_path = images_dir / f"page{i + 1}.png"
            pix.save(str(img_path))
            images.append(img_path)

        doc.close()
    except Exception:
        pass

    return images


def convert_file(
    filepath: Path,
    output_dir: Optional[Path] = None,
    ocr_service=None,
    verbose: bool = False,
) -> tuple[str, int, dict[str, str]]:
    """
    使用 MarkItDown 将文件转换为 Markdown

    Args:
        filepath: 源文件路径
        output_dir: 输出目录（用于保存图片）
        ocr_service: 可选的 OCR 服务（统一接口，详见 ocr/base.py）
        verbose: 是否输出详细信息

    Returns:
        (Markdown 文本, 提取的图片数量, 图片映射 {ref_name: new_path})
    """
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(filepath))
    markdown = result.text_content

    images_extracted = 0
    image_paths: list[Path] = []

    # 图片型 PDF 处理：MarkItDown 返回空内容时，渲染页面 + OCR
    if filepath.suffix.lower() == '.pdf' and output_dir is not None:
        content_text = markdown.strip()
        # 去掉 frontmatter 等元数据后判断是否为空
        if not content_text or len(content_text) < 50:
            if not _pdf_has_text_layer(filepath):
                pages = _render_pdf_pages(filepath, output_dir)
                if pages:
                    if ocr_service:
                        results = ocr_service.recognize_batch(pages, verbose=verbose)
                        lines = [f"# {filepath.stem}\n"]
                        for i, page_img in enumerate(pages):
                            text = results.get(page_img, "[识别失败]")
                            lines.append(f"## 第 {i + 1} 页\n\n{text}\n")
                        markdown = "\n".join(lines)
                        images_extracted += len(pages)
                    else:
                        lines = [
                            f"# {filepath.stem}\n",
                            "> ⚠️ **图片型 PDF**：此文档为扫描件或图片型 PDF，"
                            "当前未启用 OCR 功能。\n",
                            "> 启用方法：`doc-knowledge convert <dir> --ocr cloud`"
                            " 或配置 `~/.doc-knowledge/config.yaml`\n",
                        ]
                        markdown = "\n".join(lines)
                        images_extracted += len(pages)
                        image_paths.extend(pages)

    # 提取图片（PPTX/DOCX）
    if output_dir is not None:
        ext = filepath.suffix.lower()
        if ext == '.pptx':
            images_extracted, image_paths = _extract_pptx_images(filepath, output_dir)
        elif ext == '.docx':
            images_extracted, image_paths = _extract_docx_images(filepath, output_dir)

    # 按 MarkItDown 实际输出的引用名，按位置匹配构建映射
    # 映射值使用相对于 .md 文件所在目录的路径（B 内自洽）
    image_map = _build_image_map(markdown, image_paths, filepath.name)

    # 嵌入图片识别（PPTX/DOCX）：保留原图引用，追加 blockquote 描述
    # 注意：扫描型 PDF 整页识别在前面已处理，此处仅处理嵌入图片
    if ocr_service and image_paths and filepath.suffix.lower() in {'.pptx', '.docx'}:
        if verbose:
            print(f"  开始识别 {len(image_paths)} 张图片（OCR）...")

        batch_results = ocr_service.recognize_batch(image_paths, verbose=verbose)

        for img_path, description in batch_results.items():
            if description and not description.startswith("["):
                ref_name = None
                for old_name, new_path in image_map.items():
                    if new_path.endswith(img_path.name):
                        ref_name = old_name  # 用 MarkItDown 原始引用名定位
                        break

                if ref_name:
                    markdown = markdown.replace(
                        f"]({ref_name})",
                        f"]({ref_name})\n\n> 📷 **图片识别**: {description}"
                    )

    # 注意：不在这里替换图片引用。调用方（_run_convert）负责替换，
    # 以便根据使用场景（独立 convert / pipeline）选用不同的路径策略。
    return markdown, images_extracted, image_map


def _extract_pptx_images(filepath: Path, output_dir: Path) -> tuple[int, list[Path]]:
    """从 PPTX 文件中提取所有图片，每个文件独立的图片目录"""
    try:
        from pptx import Presentation
    except ImportError:
        return 0, []

    images_dir = output_dir / f"{filepath.name}_images"
    images_dir.mkdir(parents=True, exist_ok=True)

    prs = Presentation(str(filepath))
    image_count = 0
    image_paths = []

    for i, slide in enumerate(prs.slides):
        for j, shape in enumerate(slide.shapes):
            if shape.shape_type == 13:  # Picture
                try:
                    image = shape.image
                    image_bytes = image.blob
                    ext = image.ext or 'png'
                    new_name = f"slide{i+1}_img{j+1}.{ext}"
                    image_path = images_dir / new_name
                    with open(image_path, 'wb') as f:
                        f.write(image_bytes)
                    image_paths.append(image_path)
                    image_count += 1
                except Exception:
                    pass

    return image_count, image_paths


def _extract_docx_images(filepath: Path, output_dir: Path) -> tuple[int, list[Path]]:
    """从 DOCX 文件中提取所有图片，每个文件独立的图片目录

    返回顺序按文件名中的数字部分排序（image1, image2, ..., image10, image11），
    而不是字典序（会得到 image1, image10, image11, image2, ...）。
    Word 写入 media 时通常用 imageN.png 自然命名，数字序与文档流顺序基本一致。
    """
    import re
    import zipfile

    images_dir = output_dir / f"{filepath.name}_images"
    images_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0
    image_paths = []
    try:
        with zipfile.ZipFile(filepath) as zf:
            media_files = [f for f in zf.namelist() if f.startswith('word/media/')]
            media_files.sort(key=_image_sort_key)
            for media_file in media_files:
                image_data = zf.read(media_file)
                image_name = Path(media_file).name
                image_path = images_dir / image_name
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                image_paths.append(image_path)
                image_count += 1
    except Exception:
        pass

    return image_count, image_paths


def _image_sort_key(name: str):
    """图片文件名排序键：优先按数字部分，回退到字典序

    examples:
      "word/media/image1.png"  → (0, 1, "image1.png")
      "word/media/image10.png" → (0, 10, "image10.png")
      "word/media/cover.jpg"   → (1, 0, "cover.jpg")  # 无数字，字典序兜底
    """
    import re
    basename = Path(name).name
    m = re.search(r'(\d+)', basename)
    if m:
        return (0, int(m.group(1)), basename)
    return (1, 0, basename)


def _build_image_map(markdown: str, image_paths: list[Path], source_name: str) -> dict[str, str]:
    """扫描 Markdown 中实际图片引用，按位置与提取的图片路径匹配

    限制：依赖"MarkItDown 输出的图片引用顺序 ≡ 我们从文档提取的图片顺序"。
    PPTX 用 slide→shape 遍历（与 MarkItDown 一致）；
    DOCX 用 image{N}.png 数字序（见 _image_sort_key）。
    若文档使用非数字命名或多图布局复杂，映射可能错位——
    彻底修复需用 python-docx 解析 <a:blip r:embed> 文档流顺序。
    """
    import re

    if not image_paths:
        return {}

    img_refs = re.findall(r'!\[.*?\]\(([^)]+)\)', markdown)
    local_refs = [r for r in img_refs if not r.startswith(('http://', 'https://'))]

    image_map = {}
    for i, ref in enumerate(local_refs):
        if i < len(image_paths):
            image_map[ref] = f"{source_name}_images/{image_paths[i].name}"

    return image_map


def get_supported_extensions() -> list[str]:
    """获取支持的文件扩展名列表"""
    return [
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
        ".html", ".htm", ".epub", ".csv",
        ".txt", ".md",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".mp3", ".wav", ".m4a",
        ".zip", ".msg", ".ipynb",
    ]
