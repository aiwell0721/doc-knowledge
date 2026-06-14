# Doc-Knowledge OCR 统一管道设计

**创建时间**：2026-05-27
**版本**：v0.1.0

---

> **核心思路**：OCR 能力不局限于 PDF，所有图片（PPTX 内嵌、DOCX 内嵌、PDF 页、独立图片文件）统一走一个管道。三种模式覆盖不同成本/精度需求。

---

## 1. 架构总览

```
convert_file() —— 所有格式
    │
    ├── MarkItDown → 文本 markdown
    │
    └── 提取图片（统一入口）
            │
            ├── PPTX 内嵌图   → python-pptx shape.image    [已有]
            ├── DOCX 内嵌图   → zipfile word/media/        [已有]
            ├── PDF 页        → PyMuPDF page.get_pixmap()  [新增]
            └── 独立图片文件   → 直接路径                   [新增]
            │
            ▼
        ┌──────────────────────────────────────┐
        │         OCR 管道（统一处理）           │
        │                                      │
        │  [云端] 全部 → 云端 VLM API           │
        │  [本地] 全部 → PaddleOCR / Tesseract  │
        │  [混合] 本地 → 过滤 → 仅高价值送云端   │
        └──────────────────────────────────────┘
            │
            ▼
        OCR 文本注入 markdown，图片文件留在 B
```

## 2. 三种模式

| | 云端 OCR | 本地 OCR | 混合 OCR |
|------|------|------|------|
| **引擎** | OpenAI 兼容 VLM | PaddleOCR（推荐）/ Tesseract | 本地 + 云端 |
| **成本** | 按调用计费 | 免费 | 仅高价值图片付费 |
| **精度** | 最高（VLM 理解布局） | 中文 95%，英文 94% | 关键图片达 VLM 级 |
| **依赖** | 无额外依赖 | `paddleocr` 或 `tesseract` | 两者都需 |
| **适用** | 少量高质量文档 | 大批量纯文本 | 混合质量、成本敏感 |

## 3. 配置文件（`~/.doc-knowledge/config.yaml`）

```yaml
ocr:
  enabled: false
  mode: cloud               # cloud | local  （hybrid 尚未实现，见 §4.2）

  cloud:
    api_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
    max_concurrency: 5
    timeout: 60

  local:
    engine: paddleocr       # paddleocr | tesseract
    lang: "ch"              # ch | en | ch+en
    gpu: false

  # [WIP] 混合模式配置（当前未生效，CLI 也不接受 --ocr hybrid）
  hybrid:
    first_pass: local       # 第一阶段引擎
    confidence_threshold: 0.6
    max_cloud_calls: 50
    filter:
      min_size_kb: 10
      min_resolution: 100x100
      skip_solid_color: true
```

### 3.1 环境变量

`api_key` 支持 `${ENV_VAR}` 语法，运行时从环境变量读取，避免明文密钥写死。

## 4. CLI 接口

```bash
# 云端 OCR（复用已有的 --vision 概念，统一为 --ocr）
doc-knowledge convert <dir> --ocr cloud

# 本地 OCR
doc-knowledge convert <dir> --ocr local

# 混合 OCR — [WIP] 尚未实现，CLI 当前会拒绝该值
# doc-knowledge convert <dir> --ocr hybrid

# 覆盖配置文件中的 API 参数
doc-knowledge convert <dir> --ocr cloud \
    --ocr-api-url "https://dashscope.aliyuncs.com/compatible-mode/v1" \
    --ocr-api-key "sk-xxx" \
    --ocr-model "qwen-vl-plus"
```

### 4.1 旧 `--vision` 选项（2026-06-14 已移除）

历史上 `--vision/--api-url/--api-key/--model` 与 `--ocr*` 并存，造成两条平行路径。
0.3.0 起 `--vision` 系列被完全移除，请使用 `--ocr cloud` 系列。详见
[02-转换器设计.md](./02-转换器设计.md) 的"2026-06-14 vision/ocr 概念合并"说明。

### 4.2 hybrid 模式当前状态（[WIP]）

`hybrid` 在配置类（`HybridOCRConfig`）和文档示例中预留，但**当前未实现**：

- CLI 层：`--ocr hybrid` 会被 click `Choice` 拒绝，返回非零退出码
- API 层：`create_ocr_service(cfg)` 传入 `mode="hybrid"` 会抛 `NotImplementedError`，提示改用 cloud / local

未来实现时计划的策略见 § 5（已存的设计文档），但本节列出的 `ImageFilter` 三层决策当前仅作用于 `CloudOCRService` 内部的图片过滤，不构成混合策略。

## 5. 图片价值过滤器（混合模式核心）

已有的 `ImageFilter`（纯色/过小/低分辨率检测）扩展为三层决策：

```
图片 → ImageFilter
    │
    ├── 丢弃层：纯色 / <10KB / <100px
    │     → 不保存到 B，不 OCR
    │
    ├── 本地层：清晰文字 / 规则表格
    │     → 本地 OCR 结果写入 .md
    │
    └── 云端层：低置信度（< threshold）/ 复杂布局 / 图表
          → 加入云端队列 → 批量 VLM 识别
```

### 5.1 置信度判断

PaddleOCR 返回每个文本块的置信度分数。混合模式下：

- 整体置信度 = 所有文本块的平均置信度
- < `confidence_threshold`（默认 0.6）→ 标记为"建议云端"
- 有复杂布局特征（表格、不规则排版）→ 即使置信度高也建议云端复核

## 6. 本地 OCR 引擎选型

| 维度 | PaddleOCR（推荐） | Tesseract（备选） |
|------|------|------|
| 安装 | `pip install paddlepaddle paddleocr` | 系统安装 exe + `pip install pytesseract` |
| 磁盘 | ~500MB–1GB | ~200MB |
| 中文精度 | 95–98% | 78–89% |
| GPU | 支持 CUDA/TensorRT | 不支持 |

**推荐 PaddleOCR**，理由：项目面向中文文档，10–20% 精度优势决定性。Tesseract 作为 `--ocr-engine tesseract` 的备选，满足轻量部署场景。

## 7. 依赖管理

```toml
[project.optional-dependencies]
# 本地 OCR（PaddleOCR 推荐）
ocr = [
    "paddlepaddle>=3.0.0",
    "paddleocr>=2.7.0",
]

# 备选引擎
ocr-tesseract = [
    "pytesseract>=0.3.10",
]

# PDF 页转图片
pdf-image = [
    "PyMuPDF>=1.23.0",   # 已有，PDF 页 → pixmap
]
```

## 8. 数据流（图片视角）

```
源文件 → 提取图片 ──────┬── _images/ 目录（B）
                       │
                       ├── 云端模式 → VLM API → 文本注入 .md
                       ├── 本地模式 → PaddleOCR → 文本注入 .md
                       └── 混合模式 → PaddleOCR → 低置信度 → VLM API
                                          │
                                          └── 高置信度 → 直接注入
```

## 9. 实施计划

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1 | `OCRService` 抽象基类 + 三种实现 | 核心 |
| 2 | 配置文件加载（`~/.doc-knowledge/config.yaml`） | 基建 |
| 3 | `ImageFilter` 扩展（三层分类） | 混合模式前提 |
| 4 | PDF 页转图片（PyMuPDF page.get_pixmap） | 图片型 PDF |
| 5 | `convert_file()` 集成统一 OCR 管道 | 串联 |
| 6 | CLI `--ocr` 参数 + `--vision` deprecated | 接口 |
| 7 | 测试（mock OCR 后端 + 真实样本） | 验证 |
