"""
Markdown 注入器：将转换后的内容写入目录结构
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ConversionStats:
    """转换统计"""
    converted: int = 0          # 成功转换的文件数
    copied: int = 0             # 直接复制的文件数（图片等）
    skipped: int = 0            # 跳过但创建元数据包装的文件数
    errors: int = 0             # 转换失败的文件数
    error_details: list[str] = field(default_factory=list)
    
    @property
    def total(self) -> int:
        return self.converted + self.copied + self.skipped + self.errors
    
    def summary(self) -> str:
        """生成统计摘要"""
        lines = [
            "转换完成！",
            f"  [OK] 成功转换: {self.converted} 个",
            f"  [CP] 直接复制: {self.copied} 个",
            f"  [SK] 无法转换: {self.skipped} 个",
            f"  [ER] 转换失败: {self.errors} 个",
        ]
        if self.error_details:
            lines.append("")
            lines.append("错误详情:")
            for detail in self.error_details:
                lines.append(f"  - {detail}")
        return "\n".join(lines)


# 支持转换的格式
CONVERTIBLE_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".txt", ".md"}

# 直接复制的格式（图片）
COPY_AS_IS_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff"
}


class MarkdownInjector:
    """将转换后的内容注入目录结构
    
    职责:
    1. 保持源目录的相对路径结构
    2. 为可转换文件生成 .md 文件
    3. 为图片文件直接复制
    4. 为不支持的格式创建轻量元数据包装
    5. 生成转换统计报告
    """
    
    def inject(
        self,
        source_dir: Path,
        output_dir: Path,
        content_map: dict[Path, str],
        dry_run: bool = False,
    ) -> ConversionStats:
        """
        将转换后的内容写入输出目录
        
        Args:
            source_dir: 源文件目录
            output_dir: 输出目录
            content_map: {源文件路径: Markdown内容} 映射
            dry_run: 仅统计，不实际写入
            
        Returns:
            转换统计信息
        """
        stats = ConversionStats()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 处理已转换的内容
        for source_file, markdown_content in content_map.items():
            rel_path = source_file.relative_to(source_dir)
            output_file = output_dir / rel_path.parent / self._get_output_name(source_file)
            
            if dry_run:
                stats.converted += 1
                continue
            
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(markdown_content, encoding="utf-8")
            stats.converted += 1
        
        # 处理源目录中的其他文件
        for source_file in source_dir.rglob("*"):
            if source_file.is_dir():
                continue
            if source_file in content_map:
                continue  # 已处理
            
            self._handle_unconverted(source_file, source_dir, output_dir, stats, dry_run)
        
        # 生成统计报告
        if not dry_run:
            report_path = output_dir / "summary.txt"
            report_path.write_text(
                f"Doc-Knowledge 转换报告\n"
                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"源目录: {source_dir}\n"
                f"输出目录: {output_dir}\n\n"
                f"{stats.summary()}\n",
                encoding="utf-8",
            )
        
        return stats
    
    def _get_output_name(self, source_file: Path) -> str:
        """生成输出文件名"""
        ext = source_file.suffix.lower()
        if ext in COPY_AS_IS_EXTENSIONS:
            return source_file.name  # 图片保留原名
        elif ext in CONVERTIBLE_EXTENSIONS:
            return f"{source_file.stem}{ext}.md"
        else:
            return f"{source_file.name}.md"  # 元数据包装
    
    def _handle_unconverted(
        self,
        source_file: Path,
        source_dir: Path,
        output_dir: Path,
        stats: ConversionStats,
        dry_run: bool,
    ) -> None:
        """处理未被转换的文件（图片复制、元数据包装等）"""
        ext = source_file.suffix.lower()
        rel_path = source_file.relative_to(source_dir)
        output_file = output_dir / rel_path
        
        if ext in COPY_AS_IS_EXTENSIONS:
            # 图片直接复制
            if not dry_run:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, output_file)
            stats.copied += 1
            return
        
        if ext in CONVERTIBLE_EXTENSIONS:
            # 本应转换但未转换（可能是转换失败）
            # 这里不处理，让调用者负责
            return
        
        # 其他不支持的格式：复制原文件 + 创建元数据包装
        if not dry_run:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, output_file)
            self._create_metadata_wrapper(source_file, source_dir, output_dir)
        stats.skipped += 1
    
    def _create_metadata_wrapper(
        self,
        source_file: Path,
        source_dir: Path,
        output_dir: Path,
    ) -> None:
        """创建轻量元数据包装文件"""
        from doc_knowledge.utils import make_frontmatter
        
        rel_path = source_file.relative_to(source_dir)
        ext = source_file.suffix.lower()
        file_size = self._format_size(source_file.stat().st_size)
        output_file = output_dir / rel_path
        
        frontmatter = make_frontmatter(
            title=source_file.name,
            source_path=source_file.resolve(),
            source_relative=str(rel_path),
            original_format=ext.lstrip("."),
            conversion_status="skipped",
            file_size=file_size,
        )
        
        wrapper_path = Path(str(output_file) + ".md")
        wrapper_path.write_text(frontmatter, encoding="utf-8")
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
