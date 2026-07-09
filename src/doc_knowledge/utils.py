"""
Doc-Knowledge 工具函数
"""

from datetime import datetime, timezone
from pathlib import Path


def make_frontmatter(
    title: str,
    source_path: Path,
    source_relative: str = "",
    original_format: str = "",
    conversion_status: str = "converted",
    converted_at: str = "",
    file_size: str = "",
    extra: dict | None = None,
) -> str:
    """
    生成 Markdown frontmatter + 提示文本
    
    Args:
        title: 文档标题
        source_path: 源文件绝对路径
        source_relative: 相对于源目录的路径
        original_format: 原始文件格式
        conversion_status: 转换状态 (converted/skipped/error)
        converted_at: 转换时间 (ISO 格式)
        file_size: 文件大小字符串
        extra: 额外字段
        
    Returns:
        frontmatter + 提示文本
    """
    if not converted_at:
        converted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    source_url = f"file:///{source_path.as_posix()}"
    
    lines = [
        "---",
        f'title: "{title}"',
        f'source: "{source_url}"',
    ]
    
    if source_relative:
        lines.append(f'source_relative: "{source_relative}"')
    
    lines.extend([
        f"converted_at: \"{converted_at}\"",
        f'original_format: "{original_format}"',
        f'conversion_status: "{conversion_status}"',
    ])
    
    if file_size:
        lines.append(f'file_size: "{file_size}"')
    
    if extra:
        for key, value in extra.items():
            lines.append(f'{key}: "{value}"')
    
    lines.append("---")
    lines.append("")
    
    # 根据状态添加提示
    if conversion_status == "skipped":
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"> ⚠️ 此文件类型为 `.{original_format}`，暂不支持转换。")
        lines.append(f"> [打开源文件]({source_url})")
    elif conversion_status == "error":
        lines.append(f"# {title}")
        lines.append("")
        lines.append("> ❌ 转换失败。")
    
    return "\n".join(lines)
