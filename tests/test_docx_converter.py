"""测试 DOCX 转换器"""

import pytest
from pathlib import Path
from docx import Document
from doc_knowledge.converters.docx_converter import DocxConverter


@pytest.fixture
def docx_converter():
    return DocxConverter()


@pytest.fixture
def sample_docx(tmp_path):
    """创建一个包含各种元素的测试 DOCX"""
    doc = Document()
    
    # 标题
    doc.add_heading("测试文档", level=1)
    doc.add_heading("第一章", level=2)
    
    # 普通段落
    doc.add_paragraph("这是一个普通段落。")
    
    # 粗体和斜体
    p = doc.add_paragraph()
    run_bold = p.add_run("这是粗体")
    run_bold.bold = True
    p.add_run(" 普通文本 ")
    run_italic = p.add_run("这是斜体")
    run_italic.italic = True
    
    # 列表（通过段落模拟）
    doc.add_paragraph("• 项目一")
    doc.add_paragraph("• 项目二")
    
    # 表格
    table = doc.add_table(rows=3, cols=3)
    headers = ["姓名", "年龄", "城市"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    
    data = [
        ["张三", "25", "北京"],
        ["李四", "30", "上海"],
    ]
    for row_idx, row_data in enumerate(data):
        for col_idx, cell_data in enumerate(row_data):
            table.rows[row_idx + 1].cells[col_idx].text = cell_data
    
    filepath = tmp_path / "test.docx"
    doc.save(str(filepath))
    return filepath


def test_converter_handles_docx(docx_converter, sample_docx):
    """测试 DOCX 转换器识别 .docx 文件"""
    assert docx_converter.can_handle(sample_docx) is True


def test_convert_contains_heading(docx_converter, sample_docx):
    """测试转换结果包含标题"""
    result = docx_converter.convert(sample_docx)
    assert "# 测试文档" in result


def test_convert_contains_table(docx_converter, sample_docx):
    """测试转换结果包含表格"""
    result = docx_converter.convert(sample_docx)
    assert "| 姓名 | 年龄 | 城市 |" in result
    assert "| 张三 | 25 | 北京 |" in result


def test_convert_contains_paragraph(docx_converter, sample_docx):
    """测试转换结果包含段落"""
    result = docx_converter.convert(sample_docx)
    assert "这是一个普通段落" in result


def test_convert_supported_extensions():
    """测试支持的扩展名"""
    assert ".docx" in DocxConverter.supported_extensions


def test_convert_empty_docx(tmp_path, docx_converter):
    """测试空 DOCX 文件"""
    doc = Document()
    filepath = tmp_path / "empty.docx"
    doc.save(str(filepath))
    
    result = docx_converter.convert(filepath)
    assert result == ""
