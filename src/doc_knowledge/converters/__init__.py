"""文档转换器包 - 基于 MarkItDown 封装"""

from pathlib import Path
from typing import Optional


def convert_file(
    filepath: Path,
    output_dir: Optional[Path] = None,
    vision_service=None,
    verbose: bool = False,
) -> tuple[str, int, dict[str, str]]:
    """
    使用 MarkItDown 将文件转换为 Markdown
    
    Args:
        filepath: 源文件路径
        output_dir: 输出目录（用于保存图片）
        vision_service: 可选的视觉识别服务
        verbose: 是否输出详细信息
        
    Returns:
        (Markdown 文本, 提取的图片数量, 图片映射 {old_name: new_path})
    """
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(filepath))
    markdown = result.text_content
    
    # 提取图片
    images_extracted = 0
    image_map = {}
    image_paths = []  # 保存提取的图片路径，用于后续识别
    if output_dir is not None:
        ext = filepath.suffix.lower()
        if ext == '.pptx':
            images_extracted, image_map, image_paths = _extract_pptx_images(filepath, output_dir)
        elif ext == '.docx':
            images_extracted, image_map, image_paths = _extract_docx_images(filepath, output_dir)
    
    # 使用大模型识别图片内容（批量 + 过滤 + 并发）
    if vision_service and image_paths:
        if verbose:
            print(f"  开始识别 {len(image_paths)} 张图片（过滤 + 并发）...")
        
        # 批量识别（内部会过滤低价值图片 + 并发处理）
        batch_results = vision_service.recognize_images_batch(image_paths, verbose=verbose)
        
        # 更新 markdown
        for img_path, description in batch_results.items():
            if description and not description.startswith("["):
                # 找到对应的 markdown 引用路径
                ref_name = None
                for old_name, new_path in image_map.items():
                    if new_path.endswith(img_path.name):
                        ref_name = new_path
                        break
                
                if ref_name:
                    markdown = markdown.replace(
                        f"]({ref_name})",
                        f"]({ref_name})\n\n> 📷 **图片识别**: {description}"
                    )
    
    return markdown, images_extracted, image_map


def _extract_pptx_images(filepath: Path, output_dir: Path) -> tuple[int, dict[str, str], list[Path]]:
    """从 PPTX 文件中提取所有图片，每个文件独立的图片目录"""
    try:
        from pptx import Presentation
    except ImportError:
        return 0, {}, []
    
    # 每个文件独立的图片目录：{文件名}.pptx_images/
    images_dir = output_dir / f"{filepath.name}_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    prs = Presentation(str(filepath))
    image_count = 0
    image_map = {}
    image_paths = []  # 实际提取的图片路径列表
    
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
                    
                    # MarkItDown uses .jpg extension in markdown regardless of actual format
                    old_name = f"Picture{j+1}.jpg"
                    image_map[old_name] = f"{filepath.name}_images/{new_name}"
                    image_paths.append(image_path)
                    image_count += 1
                except Exception:
                    pass
    
    return image_count, image_map, image_paths


def _extract_docx_images(filepath: Path, output_dir: Path) -> tuple[int, dict[str, str], list[Path]]:
    """从 DOCX 文件中提取所有图片，每个文件独立的图片目录"""
    import zipfile
    
    # 每个文件独立的图片目录：{文件名}.docx_images/
    images_dir = output_dir / f"{filepath.name}_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    image_count = 0
    image_map = {}
    image_paths = []
    try:
        with zipfile.ZipFile(filepath) as zf:
            media_files = [f for f in zf.namelist() if f.startswith('word/media/')]
            for media_file in media_files:
                image_data = zf.read(media_file)
                image_name = Path(media_file).name
                image_path = images_dir / image_name
                
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                image_map[image_name] = f"{filepath.name}_images/{image_name}"
                image_paths.append(image_path)
                image_count += 1
    except Exception:
        pass
    
    return image_count, image_map, image_paths


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
