# Doc-Knowledge 快速入门

> **5 分钟上手**：从安装到完成第一次文档转换。

---

## 1. 安装

### 基础安装（仅 DOCX/TXT 转换）

```bash
pip install doc-knowledge
```

### 完整安装（支持 PDF/PPTX/XLSX）

```bash
pip install doc-knowledge[full]
```

### 按需安装

```bash
pip install doc-knowledge[pdf]    # 仅 PDF
pip install doc-knowledge[ppt]    # 仅 PPT
pip install doc-knowledge[excel]  # 仅 Excel
```

### 验证安装

```bash
doc-knowledge --version
# 输出：doc-knowledge, version 0.2.0
```

---

## 2. 准备测试文件

创建一个测试目录，放入几个文档：

```bash
mkdir test-docs
# 放入一些 .docx, .pdf, .txt 文件到 test-docs/
```

或者用 Python 快速创建测试文件：

```python
# create_test_files.py
from docx import Document

doc = Document()
doc.add_heading('系统架构设计', level=1)
doc.add_paragraph('本文档描述了系统的整体架构设计。')
doc.add_heading('核心模块', level=2)
doc.add_paragraph('系统包含转换器、提取器和导出器三个核心模块。')
doc.save('test-docs/architecture.docx')
```

---

## 3. 一键转换

```bash
doc-knowledge pipeline test-docs --target markdown -o output
```

**输出**：
```
Doc-Knowledge v0.2.0 — pipeline
源目录: test-docs

Step 1/3: 转换 (A → B)
  转换: architecture.docx
转换: 1, 复制: 0, 跳过: 0, 错误: 0

Step 2/3: 提取 (B → C)
保留: 1, 去重: 0, 低分: 0

Step 3/3: 导出 (C → markdown)
导出 1 个文件到 output

Pipeline 完成！
```

---

## 4. 查看结果

```bash
# 查看输出文件
ls output/
# architecture.docx.md

# 查看内容
cat output/architecture.docx.md
```

**输出示例**：
```markdown
---
title: "architecture"
source: "file:///.../test-docs/architecture.docx"
source_relative: "architecture.docx"
converted_at: "2026-05-17T14:00:00"
original_format: "docx"
conversion_status: "converted"
dk_score: 65
dk_tags: ["design", "architecture", "system"]
---

# 系统架构设计

本文档描述了系统的整体架构设计。

## 核心模块

系统包含转换器、提取器和导出器三个核心模块。
```

---

## 5. 下一步

| 命令 | 说明 |
|------|------|
| `doc-knowledge convert <dir>` | 仅转换（A → B） |
| `doc-knowledge extract <dir>` | 仅提取（B → C） |
| `doc-knowledge export <dir>` | 仅导出（C → 目标） |
| `doc-knowledge pipeline <dir>` | 一键全流程 |

**详细文档**：
- [使用指南](./usage-guide.md) - 完整功能说明
- [CLI 参考](./cli-reference.md) - 所有命令参数
- [故障排查](./troubleshooting.md) - 常见问题
