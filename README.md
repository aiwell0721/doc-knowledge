# Doc-Knowledge

> 文档知识提取工具：将 Office 文档批量转换为结构化 Markdown 知识库

**功能**：PDF/PPT/DOCX/XLSX → Markdown → 去重提取 → 导出到 Obsidian/MemoMind

## 快速开始

```bash
# 安装（完整版）
pip install doc-knowledge[full]

# 转换文档（A→B）
doc-knowledge convert D:\docs\source --output D:\docs\mirror

# 提取知识（B→C）
doc-knowledge extract D:\docs\mirror --output D:\docs\knowledge

# 一键管道（A→B→C→导出）
doc-knowledge pipeline D:\docs\source --output D:\docs\knowledge --target obsidian --vault D:\ObsidianVault
```

## 安装选项

```bash
# 基础版（仅 DOCX/TXT）
pip install doc-knowledge

# 按需安装
pip install doc-knowledge[pdf]    # PDF 支持
pip install doc-knowledge[ppt]    # PPT 支持
pip install doc-knowledge[excel]  # Excel 支持
pip install doc-knowledge[ocr]    # 图片 OCR

# 完整版
pip install doc-knowledge[full]
```

## 命令概览

| 命令 | 功能 | 说明 |
|------|------|------|
| `convert` | A→B 文档转换 | 将 Office 文档转为 Markdown 镜像 |
| `extract` | B→C 知识提取 | 去重、合并、价值评分 |
| `export` | C→目标 导出 | 导出到 Obsidian/MemoMind |
| `pipeline` | A→B→C→导出 | 一键完成全流程 |
