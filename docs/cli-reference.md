# Doc-Knowledge CLI 参考

> 所有命令和参数的完整参考。

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--version` | 显示版本号 |
| `--log-level` | 日志级别（debug/info/warning/error），默认 `warning`，输出到 stderr |
| `--help` | 显示帮助信息 |

---

## convert

将文档转换为 Markdown 镜像（A → B）。

```bash
doc-knowledge convert <source_dir> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_dir` | 路径 | ✅ | 源文件目录 |

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `-o, --output` | 路径 | `<source_dir>_mirror` | 输出目录（目录 B） |
| `--format` | 多选 | 全部 | 仅转换指定格式，如 `--format pdf --format docx` |
| `--recursive/--no-recursive` | 标志 | True | 是否递归子目录 |
| `--overwrite` | 标志 | False | 覆盖已存在的文件 |
| `--dry-run` | 标志 | False | 仅显示将要转换的文件，不实际转换 |
| `--with-layout` | 标志 | False | 解析 PPTX 时注入版式/结构标注（shape 角色 + 相对区域） |
| `--ocr` | 选择 | - | OCR 模式：`cloud` 云端 VLM \| `local` 本地 OCR \| `slide` 整页渲染+云端 VLM |
| `--ocr-api-url` | 字符串 | - | OCR API 地址（OpenAI 兼容） |
| `--ocr-api-key` | 字符串 | - | OCR API Key |
| `--ocr-model` | 字符串 | - | OCR 模型名称 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 基本转换
doc-knowledge convert ./docs

# 启用云端 VLM 图片识别
doc-knowledge convert ./docs --ocr cloud \
  --ocr-api-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --ocr-api-key $DASHSCOPE_API_KEY --ocr-model qwen-vl-plus

# 使用自定义模型
doc-knowledge convert ./docs --ocr cloud \
  --ocr-api-url <url> --ocr-api-key <key> --ocr-model gpt-4o

# PPTX 版式标注（非 OCR 模式）
doc-knowledge convert ./presentations --with-layout

# 指定输出
doc-knowledge convert ./docs -o ./markdown

# 仅转换 PDF
doc-knowledge convert ./docs --format pdf

# 预览
doc-knowledge convert ./docs --dry-run
```

---

## extract

从 Markdown 镜像提取知识（B → C）。

```bash
doc-knowledge extract <mirror_dir> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mirror_dir` | 路径 | ✅ | Markdown 镜像目录 |

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `-o, --output` | 路径 | `<mirror_dir>_extracted` | 输出目录（目录 C） |
| `--threshold` | 浮点数 | 0.85 | 去重相似度阈值（0.0-1.0） |
| `--min-score` | 整数 | 30 | 最低价值评分（0-100） |
| `--simhash` | 标志 | False | 使用 SimHash 去重（适合 10K+ 文件） |
| `--merge` | 标志 | False | 启用版本合并（将同一文档的多版本合并为最优版） |
| `--keep-deprecated` | 标志 | False | 保留去重的旧版本到 deprecated/ 目录 |
| `--dry-run` | 标志 | False | 仅显示提取计划 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 基本提取
doc-knowledge extract ./markdown

# 严格去重
doc-knowledge extract ./markdown --threshold 0.95

# 高质量过滤
doc-knowledge extract ./markdown --min-score 50

# 大规模去重
doc-knowledge extract ./markdown --simhash

# 版本合并
doc-knowledge extract ./markdown --merge

# 预览
doc-knowledge extract ./markdown --dry-run
```

---

## export

导出知识文档到目标系统（C → 目标）。

```bash
doc-knowledge export <knowledge_dir> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `knowledge_dir` | 路径 | ✅ | 知识文档目录 |

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `-t, --target` | 选择 | markdown | 导出目标（obsidian, markdown, memomind） |
| `--vault` | 路径 | - | Obsidian Vault 路径（target=obsidian 时必填） |
| `-o, --output` | 路径 | `<knowledge_dir>/exported` | 输出目录（target=markdown 时） |
| `--api-url` | 字符串 | - | MemoMind API 地址（target=memomind 时） |
| `--api-key` | 字符串 | - | MemoMind API Key |
| `--workspace` | 字符串 | default | MemoMind 工作区名称 |
| `--db` | 路径 | - | MemoMind SQLite 数据库路径（MCP 本地模式） |
| `--consolidate` | 标志 | False | 导出后运行知识整理建议（主题聚类/合并/陈旧检测） |
| `--dedup` | 标志 | False | 导出后运行 TF-IDF 语义去重扫描 |

> `--dedup` / `--consolidate` 仅在 target=memomind 且指定 `--db` 时生效。

### 示例

```bash
# 导出为 Markdown
doc-knowledge export ./knowledge --target markdown -o ./final

# 导出到 Obsidian
doc-knowledge export ./knowledge --target obsidian --vault ~/ObsidianVault

# 导出到 MemoMind（HTTP）
doc-knowledge export ./knowledge \
  --target memomind \
  --api-url http://localhost:8000

# 导出到 MemoMind（本地）
doc-knowledge export ./knowledge \
  --target memomind \
  --db ~/.memomind/memomind.db

# 导出到 MemoMind 本地 + 后处理（去重 + 知识整理）
doc-knowledge export ./knowledge \
  --target memomind \
  --db ~/.memomind/memomind.db \
  --dedup --consolidate
```

---

## pipeline

一键完成全流程（A → B → C → 导出）。

```bash
doc-knowledge pipeline <source_dir> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_dir` | 路径 | ✅ | 源文件目录 |

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `-o, --output` | 路径 | `<source_dir>_knowledge` | 最终输出目录（target=markdown 时） |
| `-t, --target` | 选择 | markdown | 导出目标（obsidian, markdown, memomind） |
| `--vault` | 路径 | - | Obsidian Vault 路径 |
| `--api-url` | 字符串 | - | MemoMind API 地址 |
| `--api-key` | 字符串 | - | MemoMind API Key |
| `--workspace` | 字符串 | default | MemoMind 工作区名称 |
| `--db` | 路径 | - | MemoMind SQLite 数据库路径 |
| `--consolidate` | 标志 | False | 导出后运行知识整理建议 |
| `--dedup` | 标志 | False | 导出后运行 TF-IDF 语义去重扫描 |
| `--temp-dir` | 路径 | 系统临时目录 | 临时目录 |
| `--threshold` | 浮点数 | 0.85 | 去重阈值 |
| `--min-score` | 整数 | 30 | 最低价值评分 |
| `--simhash` | 标志 | False | SimHash 大规模去重 |
| `--merge` | 标志 | False | 版本合并 |
| `--incremental` | 标志 | False | 增量更新（仅处理变更文件） |
| `--ocr` | 选择 | - | OCR 模式：`cloud` 云端 VLM \| `local` 本地 OCR \| `slide` 整页渲染+云端 VLM |
| `--ocr-api-url` | 字符串 | - | OCR API 地址（OpenAI 兼容） |
| `--ocr-api-key` | 字符串 | - | OCR API Key |
| `--ocr-model` | 字符串 | - | OCR 模型名称 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 基本全流程
doc-knowledge pipeline ./docs -o ./output

# 全流程 + SimHash + 合并
doc-knowledge pipeline ./docs --simhash --merge -o ./output

# 全流程 + 增量更新
doc-knowledge pipeline ./docs --incremental -o ./output

# 全流程 + OCR（云端 VLM 识别图片）
doc-knowledge pipeline ./docs --ocr cloud \
  --ocr-api-url <url> --ocr-api-key <key> --ocr-model qwen-vl-plus -o ./output

# 全流程 + 导出到 Obsidian
doc-knowledge pipeline ./docs --target obsidian --vault ~/Vault
```

---

## retry-slide

补跑 slide 模式输出 markdown 中限流失败的页（不重跑成功页、省额度）。

```bash
doc-knowledge retry-slide <markdown_path> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `markdown_path` | 文件 | ✅ | slide 模式输出的 .md 文件（需含 frontmatter source 指向源 PPTX） |

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--ocr-api-url` | 字符串 | - | VLM API 地址（OpenAI 兼容） |
| `--ocr-api-key` | 字符串 | - | VLM API Key |
| `--ocr-model` | 字符串 | glm-4.6v-flash | VLM 模型名称 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 补跑失败页（额度恢复后）
doc-knowledge retry-slide ./output/slides.md \
  --ocr-api-url https://open.bigmodel.cn/api/paas/v4 \
  --ocr-api-key $ZHIPU_API_KEY --ocr-model glm-4.6v-flash
```

---

## webui

启动 Gradio Web 可视化界面。

```bash
doc-knowledge webui [OPTIONS]
```

### 选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--port` | 整数 | 7860 | Web UI 端口 |
| `--share` | 标志 | False | 生成公开分享链接（Gradio Share） |

### 示例

```bash
# 启动本地 Web UI
doc-knowledge webui

# 指定端口 + 生成公开分享链接
doc-knowledge webui --port 8080 --share
```
