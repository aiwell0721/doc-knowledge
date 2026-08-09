# Doc-Knowledge OCR 统一管道设计

**创建时间**：2026-05-27
**更新日期**：2026-08-09
**版本**：v0.2.0

---

> **核心思路**：OCR 能力不局限于 PDF，所有图片（PPTX 内嵌、DOCX 内嵌、PDF 页、独立图片文件）统一走一个管道。四种模式覆盖不同成本/精度需求。
>
> **2026-08-09 新增 slide 模式（v0.2.0）**：面向图表为主的 PPT，实现"文字+图片+空间"三位一体的整页意图识别。与图像级 OCR（cloud/local/hybrid）不同，slide 模式把**整页幻灯片渲染成图片**，让云端 VLM 直接读取页面的图文空间三维信息，输出结构化理解（图表语义、表格结构化、页面主旨）。详见 § 7。

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
            ├── PDF 页        → PyMuPDF page.get_pixmap()  [已有]
            └── 独立图片文件   → 直接路径                   [已有]
            │
            ▼
        ┌──────────────────────────────────────┐
        │         OCR 管道（统一处理）           │
        │                                      │
        │  [云端] 全部 → 云端 VLM API           │
        │  [本地] 全部 → PaddleOCR / Tesseract  │
        │  [混合] 本地 → 过滤 → 仅高价值送云端   │
        │  [幻灯片] 整页渲染 → 云端 VLM 三位一体  │  ← v0.2.0 新增
        └──────────────────────────────────────┘
            │
            ▼
        OCR 文本注入 markdown，图片文件留在 B
```

## 2. 四种模式

| | 云端 OCR | 本地 OCR | 混合 OCR | 幻灯片 OCR（slide） |
|------|------|------|------|------|
| **引擎** | OpenAI 兼容 VLM | PaddleOCR（推荐）/ Tesseract | 本地 + 云端 | LibreOffice 渲染 + 云端 VLM |
| **粒度** | 单张内嵌图片 | 单张内嵌图片 | 单张内嵌图片 | **整页幻灯片**（图文空间一体） |
| **成本** | 按调用计费 | 免费 | 仅高价值图片付费 | 按页计费（免费模型可用） |
| **精度** | 最高（VLM 理解布局） | 中文 95%，英文 94% | 关键图片达 VLM 级 | 最高（图表语义/表格/页面主旨） |
| **依赖** | 无额外依赖 | `paddleocr` 或 `tesseract` | 两者都需 | **LibreOffice** + 云端 VLM |
| **适用** | 少量高质量文档 | 大批量纯文本 | 混合质量、成本敏感 | **图表为主的 PPT**（三位一体意图识别） |

## 3. 配置文件（`~/.doc-knowledge/config.yaml`）

```yaml
ocr:
  enabled: false
  mode: cloud               # cloud | local | slide  （hybrid 尚未实现，见 §4.2）

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

  # slide 模式（方案C：整页渲染 + 云端 VLM 三位一体意图识别）
  # 复用 cloud 的 api_url/api_key/model；此处仅覆盖 slide 专属参数
  slide:
    dpi: 150                # 渲染分辨率
    prompt: ""              # 覆盖默认 slide prompt（见 §7.3）
    libreoffice_path: ""    # 可选，soffice 可执行文件路径；留空自动探测

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

# 幻灯片 OCR — 整页渲染 + 云端 VLM 三位一体（v0.2.0 新增）
doc-knowledge convert <dir> --ocr slide

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

## 7. slide 模式（方案C：幻灯片级三位一体意图识别）★ v0.2.0

### 7.1 定位与动机

**问题**：图表为主的 PPT，单张内嵌图片识别（cloud 模式）无法还原"整页胶片"的表达意图。胶片的意思是靠**文字 + 图片 + 空间位置**三者共同构成的——只识别内嵌图会丢失图文关系与版面逻辑。

**解法**：不识别内嵌图片，而是把**整页幻灯片渲染成图片**，让具备视觉理解能力的云端 VLM 直接读取整页图文空间三维信息，输出结构化理解。

### 7.2 流程

```
① LibreOffice soffice --headless --convert-to pdf  →  input.pptx → temp.pdf
       （完整渲染，效果最好；非内嵌图片的矢量图形、配色、布局全部还原）
② PyMuPDF (fitz) 渲染 PDF 每页                        →  整页 PNG（默认 150dpi）
③ 整页 PNG 批量送云端 VLM                             →  每页结构化输出
       （图表语义 + 表格结构化 + 页面主旨 + 关键图文关系）
④ 按页注入 blockquote                                →  对应幻灯片引用下方
```

**LibreOffice 依赖**：slide 模式是唯一需要 LibreOffice 的模式（`soffice --headless`）。若未安装，启动时给出明确提示并引导安装（Windows: `winget install TheDocumentFoundation.LibreOffice`）。渲染后的临时 PDF 使用后清理，不落盘到 B。

**限流与重试（2026-08-09 实测发现）**：免费视觉模型（如智谱 glm-4.6v-flash）对**并发与请求速率严格限流**——连续请求（即使并发 1）会触发 HTTP 429 / 401 / 连接重置，额度随时间恢复。因此 slide 模式：
- **串行逐张发送**（默认 `max_concurrency=1`，不继承 cloud 并发）；
- 429/连接失败时**指数退避重试**（5s → 10s → 20s，默认最多 3 次），等待额度恢复；
- **空响应也重试**——VLM 偶发返回空字符串，若放行会静默丢失整页注入（真实 PPT 验证中发现，2026-08-09 修复）。

**真实 75 页 PPT 验证**（2026-08-09）：58/75 页（77%）成功输出结构化 JSON，16/75 页（21%）因限流耗尽重试返回错误占位符。免费模型单次连续处理长文档不可靠，**长文档建议换付费 VLM** 或分批处理。

**失败处理与补跑机制（2026-08-09 新增）**：三层防线 + 降级兜底，应对免费模型限流导致的单页失败：

```
三层防线
├── 第1层：单页指数退避重试（_recognize_with_retry，5s→10s→20s，最多3次）  [已有]
├── 第2层：自动二次补跑（recognize_slides 双轮，retry_failed_pass=True 默认开）
│     └── 第一轮全页串行 → 第二轮仅对失败页再识别一轮
│          （第二轮时距第一轮已隔一段时间，额度恢复，成功率显著提升）
└── 第3层：CLI 手动补跑（retry-slide 命令）— 额度恢复后对仍失败页补识别
      └── 重新渲染源 PPTX → 仅识别失败页 → 更新 markdown（不重跑成功页）
兜底：仍失败的页注入降级提示
      > 📊 **整页理解**: ⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留
```

**失败判定（统一）**：`成功 = text.strip() 非空 且 不以 "[" 开头`；空串、纯空白、`[图片识别失败: ...]`、`[图片解析失败: ...]` 均视为失败。

**失败块兼容两种形态（2026-08-09 补充）**：`retry-slide` 解析失败页清单与 `_update_slide_blockquotes` 删除旧块时，需同时匹配两种失败形态——
- 新版降级提示：`> 📊 **整页理解**: ⚠️ 本页图表语义识别失败…`
- 旧版错误堆栈：`> 📊 **整页理解**: [图片识别失败: HTTP Error 429…]`（降级提示功能实现前的 md 遗留）

真实 75 页补跑验证（2026-08-09）：16 个旧格式失败页全部被识别补跑，成功 15 页，仍失败 1 页正确降级，无重复注入。

**CLI retry-slide 用法**（补跑已有 markdown 的失败页）：
```bash
doc-knowledge retry-slide <output.md> --ocr-api-url "https://open.bigmodel.cn/api/paas/v4" \
    --ocr-api-key "${ZHIPU_API_KEY}" --ocr-model "glm-4.6v-flash"
# 流程：解析 frontmatter source → 源 PPTX；解析失败块（⚠️ 降级提示 或 [错误堆栈]）→ 失败页清单；
#       soffice 重新渲染 → 仅识别失败页（含自动二次补跑）→ 替换 blockquote 写回
```

### 7.3 双契约接口（互不污染）

slide 与 cloud/local/hybrid 是两个**独立接口实现层**，避免逻辑耦合：

```python
# 图像级接口（cloud / local / hybrid 共用）
class OCRService(ABC):
    def recognize_batch(self, image_paths: list[Path]) -> dict[Path, str]: ...

# 页面级接口（slide 模式独有）
class SlideFusionService(ABC):
    def recognize_slides(self, page_images: list[Path],
                         retry_failed_pass: bool = True) -> dict[int, str]: ...
    # retry_failed_pass=True：第一轮全页 → 第二轮仅失败页自动补跑（默认开）
    def retry_pages(self, pptx_path: Path, output_dir: Path,
                    page_numbers: list[int]) -> dict[int, str]: ...
    # CLI 补跑用：渲染源 PPTX 后仅识别指定页（复用识别与自动补跑）
```

- `convert_file()` 内部按模式分发：PPTX 且 mode=slide → 走 SlideFusionService（整页），否则走 OCRService（内嵌图）。
- 两者返回结构不同（`Path → text` vs `页码 → text`），注入策略也不同（内嵌图 blockquote 挂在引用下 vs 整页 blockquote 挂在页首）。
- 工厂 `create_ocr_service(cfg)` 按 `mode` 返回对应实现，slide 模式复用 `cloud` 的 VLM 配置（api_url/api_key/model）加上 slide 专属参数（dpi/prompt）。
- 补跑更新用 `_update_slide_blockquotes(md, results)`：替换目标页已有块（单行降级提示）或插入缺失块，非目标页保持原样。

### 7.4 默认 prompt（slide 模式专用）

```text
你正在分析一页 PPT 幻灯片。请输出结构化 JSON：
1. page_summary：本页主旨（1-2 句话）
2. charts：本页的图表列表（类型：柱状/折线/饼图/雷达/散点…；标题；X轴/Y轴含义；
   关键数据点；趋势或结论）
3. tables：本页的表格（转为 Markdown 表格）
4. layout_notes：图文之间的空间关系（如"左图右文，图解释了文字中的市场规模趋势"）
只输出 JSON，不要额外解释。
```

### 7.5 参考 VLM 配置（智谱 GLM-4.6V-Flash，免费）

| 项 | 值 |
|------|------|
| 端点 | `https://open.bigmodel.cn/api/paas/v4` |
| 模型 | `glm-4.6v-flash`（9B，128K 上下文，视觉理解同参数 SOTA） |
| 能力 | 复杂图表问答、版式还原与重构、跨页逻辑理解、文档智能问答 |
| 输入 | base64 图片（`data:image/png;base64,...`），支持思考模式 `thinking.enabled` |
| 成本 | 免费额度 |

```yaml
ocr:
  enabled: true
  mode: slide
  cloud:
    api_url: "https://open.bigmodel.cn/api/paas/v4"
    api_key: "${ZHIPU_API_KEY}"
    model: "glm-4.6v-flash"
```

### 7.6 本地视觉模型评估结论（决策记录，2026-08-09）

曾考虑用**本地视觉模型**（OvisOCR2 0.8B 端到端文档解析 / GLM-5V-Turbo / Tesseract+MobileNet+OpenCV）替代云端 VLM 做三位一体意图识别，结论如下：

| 方案 | 结论 |
|------|------|
| **GLM-5V-Turbo** | 闭源 API-only，**无法本地部署**（无 Ollama 版），已排除 |
| **OvisOCR2 (0.8B)** | 是**文档解析器**（文本/表格/版面 → Markdown），非**推理器**——无法解释图表语义/趋势。对图表为主的 PPT 是净信息损失，且引入 vLLM/GPU 部署负担。**不入默认路径** |
| **Tesseract+MobileNet+OpenCV** | 纯本地轻量，但无语义理解，仅适合作为路由/预处理层 |

**结论**：三位一体意图识别的难点在"图片语义"维度，必须靠真正的 VLM 推理。云端 VLM（默认，如 glm-4.6v-flash 免费）是当前最优解；本地模型仅作为未来可选配置插槽（`slide.input = page_image | parsed_markdown`），本期不实现。

## 8. 依赖管理

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

slide 模式外部依赖：**LibreOffice**（系统级，非 pip），PyMuPDF 已在 pdf-image extras 中。

## 9. 数据流（图片视角）

```
源文件 → 提取图片 ──────┬── _images/ 目录（B）
                       │
                       ├── 云端模式 → VLM API → 文本注入 .md
                       ├── 本地模式 → PaddleOCR → 文本注入 .md
                       ├── 混合模式 → PaddleOCR → 低置信度 → VLM API
                       │                      │
                       │                      └── 高置信度 → 直接注入
                       └── 幻灯片模式 → LibreOffice 整页渲染 → VLM API
                                              │
                                              └── 每页结构化理解注入 .md
```

## 10. 实施计划

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | `OCRService` 抽象基类 + 三种实现 | 已完成 |
| 2 | 配置文件加载（`~/.doc-knowledge/config.yaml`） | 已完成 |
| 3 | `ImageFilter` 扩展（三层分类） | 已完成 |
| 4 | PDF 页转图片（PyMuPDF page.get_pixmap） | 已完成 |
| 5 | `convert_file()` 集成统一 OCR 管道 | 已完成 |
| 6 | CLI `--ocr` 参数 + `--vision` deprecated | 已完成 |
| 7 | `SlideFusionService`（slide 模式，v0.2.0） | 已完成 |
| 8 | `--ocr slide` CLI + 工厂分发 | 已完成 |
| 9 | LibreOffice 探测 + 未安装引导 | 已完成 |
| 10 | 测试（mock OCR 后端 + 真实 PPT 验证） | 已完成（16 测试 + 75 页真实 PPT） |
| 11 | 失败页自动二次补跑（recognize_slides 双轮） | 已完成 |
| 12 | CLI `retry-slide` 补跑命令 + `_update_slide_blockquotes` | 已完成 |
