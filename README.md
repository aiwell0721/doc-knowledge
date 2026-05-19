# Doc-Knowledge

> 文档知识提取工具：将 Office 文档批量转换为结构化 Markdown 知识库

**功能**：PDF/PPT/DOCX/XLSX → Markdown → 去重提取 → 导出到 Obsidian/MemoMind

**✨ 新版 Web UI**：`doc-knowledge webui` 启动可视化界面

## 快速开始

### Web 界面（推荐）

```bash
# 安装 Web UI
pip install doc-knowledge[webui]

# 启动可视化界面
pip install doc-knowledge[webui]
doc-knowledge webui
```

浏览器自动打开，5 个标签页覆盖全部功能：
- **🚀 一键全流程** — A→B→C→目标，一次搞定
- **🔄 转换** — 文档转 Markdown 镜像
- **🧠 提取** — 去重 + 价值评分 + 自动标签
- **📤 导出** — Obsidian / MemoMind / Markdown
- **📖 指南** — 快速入门文档

### 命令行

## 安装选项

```bash
# 基础版（仅 DOCX/TXT）
pip install doc-knowledge

# Web UI
pip install doc-knowledge[webui]

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
| `webui` | Web 界面 | 启动可视化操作面板（浏览器） |
| `convert` | A→B 文档转换 | 将 Office 文档转为 Markdown 镜像 |
| `extract` | B→C 知识提取 | 去重、合并、价值评分 |
| `export` | C→目标 导出 | 导出到 Obsidian/MemoMind |
| `pipeline` | A→B→C→导出 | 一键完成全流程 |
