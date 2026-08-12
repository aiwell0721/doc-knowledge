# Doc-Knowledge 使用指南

> 完整功能说明：转换、提取、导出全流程。

---

## 1. 产品概述

Doc-Knowledge 是一个文档知识提取工具，将 Office 文档批量转换为结构化 Markdown 知识库。

### 核心流程

```
目录 A (源文件)          目录 B (Markdown 镜像)       目录 C (知识文档)         目标系统
PDF/DOCX/PPTX/XLSX  →   转换 + 反向链接        →   去重 + 评分 + 标签    →   Obsidian/MemoMind
```

### 支持的格式

| 格式 | 扩展名 | 依赖 |
|------|--------|------|
| PDF | `.pdf` | PyMuPDF 或 pdfminer.six |
| DOCX | `.docx` | 基础安装自带 |
| PPTX | `.pptx` | python-pptx |
| XLSX | `.xlsx` | openpyxl |
| 纯文本 | `.txt` | 基础安装自带 |

---

## 2. convert 命令（A → B）

将源目录中的文档转换为 Markdown 镜像。

```bash
doc-knowledge convert <source_dir> [OPTIONS]
```

### 基本用法

```bash
# 转换整个目录
doc-knowledge convert ./my-docs

# 指定输出目录
doc-knowledge convert ./my-docs -o ./markdown-output

# 仅转换特定格式
doc-knowledge convert ./my-docs --format pdf --format docx

# 预览（不实际转换）
doc-knowledge convert ./my-docs --dry-run
```

### 输出结构

```
output/
├── chapter1/
│   ├── intro.docx.md          # 转换后的 Markdown
│   └── _images/               # 提取的图片
├── report.pdf.md
└── summary.txt                # 转换统计报告
```

每个 `.md` 文件包含：
- YAML frontmatter（元数据 + 反向链接）
- Markdown 正文

---

## 3. extract 命令（B → C）

从 Markdown 镜像中提取知识（去重、评分、标签）。

```bash
doc-knowledge extract <mirror_dir> [OPTIONS]
```

### 基本用法

```bash
# 基本提取
doc-knowledge extract ./markdown-output

# 指定输出目录
doc-knowledge extract ./markdown-output -o ./knowledge

# 自定义去重阈值（0.0-1.0，默认 0.85）
doc-knowledge extract ./markdown-output --threshold 0.9

# 最低价值评分（0-100，默认 30）
doc-knowledge extract ./markdown-output --min-score 50

# 使用 SimHash 大规模去重（10K+ 文件）
doc-knowledge extract ./markdown-output --simhash

# 启用版本合并
doc-knowledge extract ./markdown-output --merge

# 保留去重的旧版本
doc-knowledge extract ./markdown-output --keep-deprecated
```

### 价值评分因子

| 因子 | 权重 | 说明 |
|------|------|------|
| 内容长度 | 20% | 太短价值低 |
| 结构完整性 | 25% | 有标题/列表/代码块加分 |
| 新鲜度 | 15% | 修改时间越近分越高 |
| 关键词密度 | 20% | 专业术语密度 |
| 独特性 | 20% | 内容信息熵 |

### 去重算法

| 算法 | 适用场景 | 命令 |
|------|---------|------|
| TF-IDF + 余弦相似度 | < 1000 文件 | 默认 |
| SimHash | 10K+ 文件 | `--simhash` |

### 版本合并

自动识别同一文档的不同版本（如 `report_v1.md`, `report_v2.md`），保留最优版本。

版本号识别模式：`_v1`, `_v2`, `_final`, `_20260517` 等。

---

## 4. export 命令（C → 目标）

将知识文档导出到目标系统。

```bash
doc-knowledge export <knowledge_dir> [OPTIONS]
```

### 导出到 Markdown

```bash
doc-knowledge export ./knowledge --target markdown -o ./final-output
```

### 导出到 Obsidian

```bash
doc-knowledge export ./knowledge --target obsidian --vault /path/to/your/vault
```

### 导出到 MemoMind（HTTP 模式）

```bash
doc-knowledge export ./knowledge \
  --target memomind \
  --api-url http://localhost:8000 \
  --api-key your-api-key \
  --workspace default
```

### 导出到 MemoMind（本地 MCP 模式）

```bash
doc-knowledge export ./knowledge \
  --target memomind \
  --db /path/to/memomind.db \
  --workspace default
```

---

## 5. pipeline 命令（全流程）

一键完成转换 → 提取 → 导出。

```bash
doc-knowledge pipeline <source_dir> [OPTIONS]
```

### 基本用法

```bash
# 一键全流程（导出为 Markdown）
doc-knowledge pipeline ./my-docs --target markdown -o ./output

# 全流程 + SimHash 去重 + 版本合并
doc-knowledge pipeline ./my-docs \
  --target markdown \
  --simhash \
  --merge \
  -o ./output

# 全流程 + 增量更新
doc-knowledge pipeline ./my-docs \
  --target markdown \
  --incremental \
  -o ./output

# 全流程 + 导出到 Obsidian
doc-knowledge pipeline ./my-docs \
  --target obsidian \
  --vault /path/to/vault
```

### 增量更新

`--incremental` 选项仅处理变更的文件：
- 首次运行：处理所有文件
- 后续运行：仅处理修改时间晚于输出文件的源文件
- 适用场景：定期同步文档库

---

## 6. 输出格式说明

### Markdown Frontmatter

每个输出的 `.md` 文件包含 YAML frontmatter：

```yaml
---
title: "文档标题"
source: "file:///原始文件路径"
source_relative: "相对路径"
converted_at: "2026-05-17T14:00:00"
original_format: "docx"
conversion_status: "converted"
dk_score: 65
dk_score_detail:
  length: 70.0
  structure: 80.0
  freshness: 100.0
  keywords: 60.0
  uniqueness: 50.0
dk_tags: ["architecture", "design", "system"]
---
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `title` | 文档标题 |
| `source` | 源文件绝对路径（file:// URL） |
| `source_relative` | 相对于源目录的路径 |
| `converted_at` | 转换时间 |
| `original_format` | 原始文件格式 |
| `conversion_status` | 转换状态（converted/skipped/error） |
| `dk_score` | 价值评分（0-100） |
| `dk_score_detail` | 各维度评分详情 |
| `dk_tags` | 自动生成的标签列表 |

---

## 7. 常见场景

### 场景 1：个人知识库整理

```bash
# 将历史文档整理为 Markdown 知识库
doc-knowledge pipeline ~/Documents --target markdown -o ~/knowledge-base
```

### 场景 2：团队文档同步到 Obsidian

```bash
# 将团队文档转换并导入 Obsidian
doc-knowledge pipeline ./team-docs \
  --target obsidian \
  --vault ~/ObsidianVault/team-docs
```

### 场景 3：定期增量更新

```bash
# 首次运行
doc-knowledge pipeline ./docs --target markdown -o ./output --incremental

# 后续运行（仅处理变更文件）
doc-knowledge pipeline ./docs --target markdown -o ./output --incremental
```

### 场景 4：大规模文档去重

```bash
# 10K+ 文件使用 SimHash 去重 + 版本合并
doc-knowledge pipeline ./large-docs \
  --target markdown \
  --simhash \
  --merge \
  -o ./cleaned-output
```

### 场景 5：PPT 转换 + 图片识别

```bash
# 转换 PPT 并使用大模型识别图片内容
doc-knowledge pipeline ./presentations \
  --target markdown \
  --vision \
  --api-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --api-key $DASHSCOPE_API_KEY \
  --model qwen-vl-plus \
  -o ./output
```

**支持的模型提供商**：

| 提供商 | API URL | 模型 |
|--------|---------|------|
| 通义千问 | dashscope.aliyuncs.com | qwen-vl-plus, qwen-vl-max |
| OpenAI | api.openai.com | gpt-4o, gpt-4o-mini |
| DeepSeek | api.deepseek.com | deepseek-vl2 |
| 本地部署 | localhost:8000 | qwen2.5-vl, llama3.2-vision |

---

## 8. Slide 模式（整页 PPT 识别）与 VLM 模型选择

Slide 模式把**整页 PPT 渲染成图片**，由视觉大模型（VLM）一次性读取"文字 + 图片 + 空间"三维信息，输出结构化 Markdown（标题 / 概述 / 内容结构 / 正文）。适用于含图表、复杂排版的 PPT——比仅 OCR 内嵌图片更能还原页面语义。

### 8.1 开启方式

```bash
doc-knowledge convert ./presentations -o ./output --ocr slide
```

需安装 LibreOffice（用于 PPTX→PDF 整页渲染，Windows 可用 `winget install TheDocumentFoundation.LibreOffice`）。输出每页含 `📊 **标题**（结构）` + 概述 + 正文 + markitdown 原文折叠兜底。

### 8.2 默认模型与配置文件

OCR 配置存放在 **`~/.doc-knowledge/config.yaml`**（用户主目录，不在项目目录）。默认使用 **GLM-4.6V-Flash**（智谱免费模型）：

```yaml
ocr:
  enabled: true
  mode: cloud
  cloud:
    api_url: "https://open.bigmodel.cn/api/paas/v4"
    api_key: "${ZHIPU_API_KEY}"   # 环境变量引用，见 8.4
    model: "glm-4.6v-flash"
    max_concurrency: 2
    timeout: 120
  slide:
    dpi: 150
    libreoffice_path: ""          # 留空自动探测
```

### 8.3 切换模型（GLM ↔ Qwen）

#### 方式 A：修改配置文件（持久生效）

**切换到 Qwen2.5-VL-7B**（先启动本地 Gradio 适配器连到 HF Space ppt-reader）。默认配置文件 `~/.doc-knowledge/config.yaml` 已内置注释版 Qwen 配置——**注释掉 GLM 的 `api_url/api_key/model` 三行、取消 Qwen 三行注释**即可，无需从本文复制：

```yaml
  cloud:
    # api_url: "http://127.0.0.1:8765/v1"   # 本地代理 → HF Space
    # api_key: "gradio"
    # model: "qwen2.5-vl-7b-instruct"
    # max_concurrency: 1       # ZeroGPU 串行排队，不支持并发
    # timeout: 300             # ZeroGPU 冷启动可能很慢
```

**切回 GLM**：恢复 GLM 的 `api_url/api_key/model` 三行注释状态即可。

#### 方式 B：CLI 参数临时覆盖（单次生效）

```bash
# 临时用 Qwen（默认配置仍是 GLM）
doc-knowledge convert in -o out --ocr slide \
  --ocr-api-url http://127.0.0.1:8765/v1 \
  --ocr-api-key gradio --ocr-model qwen2.5-vl-7b-instruct

# 临时用 GLM（默认配置是 Qwen 时）
doc-knowledge convert in -o out --ocr slide \
  --ocr-api-url https://open.bigmodel.cn/api/paas/v4 \
  --ocr-api-key $ZHIPU_API_KEY --ocr-model glm-4.6v-flash
```

> `--ocr-api-url` / `--ocr-api-key` / `--ocr-model` 优先级高于配置文件。

### 8.4 设置 API Key

`config.yaml` 用 `${ZHIPU_API_KEY}` 引用环境变量，避免把密钥写进配置文件：

```bash
# Windows（PowerShell，设置后需重开终端生效）
setx ZHIPU_API_KEY "你的密钥"

# macOS / Linux
echo 'export ZHIPU_API_KEY="你的密钥"' >> ~/.bashrc && source ~/.bashrc
```

智谱 API Key 在 [open.bigmodel.cn](https://open.bigmodel.cn) 控制台免费申请（`glm-4.6v-flash` 为免费模型）。

### 8.5 模型选择建议

| 维度 | GLM-4.6V-Flash | Qwen2.5-VL-7B |
|------|---------------|---------------|
| 接入 | 官方 API，需申请 Key | 本地代理 → HF Space，无需 Key |
| 速度 / 稳定性 | 快、稳定（官方 API） | 慢（ZeroGPU 排队 / 限流 / 冷启动） |
| 质量 | 结构识别准确 | 7B 小模型结构识别偶有偏差 |
| 表格还原 | 准确 | 准确 |
| 数据去向 | 内容发往智谱云端 | 经本地代理转发到 HF 云端 |

两者强化后四标记提取率均 100%、0 降级，差异主要在速度与结构精度。**默认建议 GLM**；无 Key 或网络仅通 HF 时用 Qwen。

## 9. 故障排查

见 [故障排查](./troubleshooting.md)。
