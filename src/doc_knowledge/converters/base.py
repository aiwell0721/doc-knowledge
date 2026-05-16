"""
Doc-Knowledge 文档转换器基类
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


class BaseConverter(ABC):
    """文档转换器基类
    
    所有具体格式转换器必须继承此类，实现 convert 方法。
    """
    
    # 子类必须定义支持的文件扩展名列表
    supported_extensions: ClassVar[list[str]] = []
    
    @abstractmethod
    def convert(self, filepath: Path) -> str:
        """
        将文件转换为 Markdown 格式
        
        Args:
            filepath: 源文件路径
            
        Returns:
            Markdown 内容字符串（不含 frontmatter）
        """
        pass
    
    def can_handle(self, filepath: Path) -> bool:
        """检查此转换器是否能处理指定文件"""
        return filepath.suffix.lower() in self.supported_extensions
    
    def get_output_filename(self, filepath: Path) -> str:
        """根据源文件名生成输出 Markdown 文件名"""
        return f"{filepath.stem}{filepath.suffix}.md"
