# Doc-Knowledge CLI 参考

> 所有命令和参数的完整参考。

---

## 全局选项

| 选项 | 说明 |
|------|------|
| `--version` | 显示版本号 |
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
| `-o, --output` | 路径 | `<source_dir>_mirror` | 输出目录 |
| `--format` | 多选 | 全部 | 仅转换指定格式（pdf, docx, pptx, xlsx） |
| `--recursive` | 标志 | True | 递归子目录 |
| `--no-recursive` | 标志 | - | 不递归子目录 |
| `--overwrite` | 标志 | False | 覆盖已存在的文件 |
| `--dry-run` | 标志 | False | 仅显示将要转换的文件 |
| `--vision` | 标志 | False | 启用大模型图片识别 |
| `--api-url` | 字符串 | - | 大模型 API 地址 |
| `--api-key` | 字符串 | - | 大模型 API Key |
| `--model` | 字符串 | qwen-vl-plus | 大模型名称 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 基本转换
doc-knowledge convert ./docs

# 启用图片识别
doc-knowledge convert ./docs --vision --api-url https://dashscope.aliyuncs.com/compatible-mode/v1 --api-key $DASHSCOPE_API_KEY

# 使用自定义模型
doc-knowledge convert ./docs --vision --api-url <url> --api-key <key> --model gpt-4o

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
| `-o, --output` | 路径 | `<mirror_dir>_extracted` | 输出目录 |
| `--threshold` | 浮点数 | 0.85 | 去重相似度阈值（0.0-1.0） |
| `--min-score` | 整数 | 30 | 最低价值评分（0-100） |
| `--simhash` | 标志 | False | 使用 SimHash 大规模去重 |
| `--merge` | 标志 | False | 启用版本合并 |
| `--keep-deprecated` | 标志 | False | 保留去重的旧版本 |
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
| `-o, --output` | 路径 | `<source_dir>_knowledge` | 最终输出目录 |
| `-t, --target` | 选择 | markdown | 导出目标（obsidian, markdown, memomind） |
| `--vault` | 路径 | - | Obsidian Vault 路径 |
| `--api-url` | 字符串 | - | MemoMind API 地址 |
| `--api-key` | 字符串 | - | MemoMind API Key |
| `--workspace` | 字符串 | default | MemoMind 工作区名称 |
| `--db` | 路径 | - | MemoMind SQLite 数据库路径 |
| `--temp-dir` | 路径 | 系统临时目录 | 临时目录 |
| `--threshold` | 浮点数 | 0.85 | 去重阈值 |
| `--min-score` | 整数 | 30 | 最低价值评分 |
| `--simhash` | 标志 | False | SimHash 大规模去重 |
| `--merge` | 标志 | False | 版本合并 |
| `--incremental` | 标志 | False | 增量更新 |
| `-v, --verbose` | 标志 | False | 详细输出 |

### 示例

```bash
# 基本全流程
doc-knowledge pipeline ./docs -o ./output

# 全流程 + SimHash + 合并
doc-knowledge pipeline ./docs --simhash --merge -o ./output

# 全流程 + 增量更新
doc-knowledge pipeline ./docs --incremental -o ./output

# 全流程 + 导出到 Obsidian
doc-knowledge pipeline ./docs --target obsidian --vault ~/Vault
```
