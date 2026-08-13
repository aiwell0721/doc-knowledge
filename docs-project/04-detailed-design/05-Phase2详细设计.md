# Doc-Knowledge Phase 2 详细设计

**创建时间**：2026-05-17
**更新日期**：2026-08-14
**版本**：v0.3.0

---

## 1. MemoMind 导出器设计

### 1.1 HTTP API 模式

```python
class MemoMindExporter:
    """通过 REST API 导出到 MemoMind"""
    
    def __init__(self, api_url: str, api_key: str = "", workspace: str = "default"):
        """初始化 API 连接"""
    
    def export(self, knowledge_dir: Path) -> dict:
        """遍历知识目录，逐条 POST /api/notes"""
```

**错误处理**：API 不可用时抛出 ConnectionError，不静默吞掉。

### 1.2 MCP 本地模式（SQLite 直写）

```python
class MemoMindMCPExporter:
    """通过直接写 SQLite 导出到 MemoMind"""
    
    def export(self, knowledge_dir: Path) -> dict:
        """INSERT 到 notes/tags/note_tags 表"""
```

**CLI 选项**：
- `--target memomind --api-url <url>` （HTTP 模式）
- `--target memomind --db <path>` （MCP 本地模式）
- `--workspace <name>` （工作区名，默认 "default"）

#### Schema 风险与防护（v0.3.0）

**风险**：MCP 本地模式硬编码 4 张表（`workspaces`/`notes`/`tags`/`note_tags`）的 schema。MemoMind 是第三方应用，升级后 schema 变更方向不可预知，当前实现无任何校验：

| 风险 | 触发 | 后果 |
|------|------|------|
| 表/列名变更 | MemoMind 重构 | `OperationalError` 被吞成 error_detail，整体静默失败 |
| 列语义漂移 | 列保留但含义变（如 content Markdown→HTML） | **写入错误数据且零报错**（最危险） |
| 主键假设 | `lastrowid` 依赖 AUTOINCREMENT 整数主键 | note_tags 关联错乱 / FK 违规 |
| 并发直写 | MemoMind 运行中持有连接 | `database is locked` / 磁盘态不一致 |
| 连接泄漏 | `_get_or_create_workspace` 抛错时 conn 未关闭 | 句柄泄漏 |

**防护（v0.3.0 起）**：

1. **写前 schema 自检** `_validate_memomind_schema(conn)`：`export()` 开写前查询 `sqlite_master` + `PRAGMA table_info`，校验 4 表必需列存在；缺失即抛 `MemoMindSchemaError`，消息提示"改用 HTTP 模式（--api-url）或升级 MemoMind"。**原则：要么写对、要么明确失败，不写坏。**
2. **连接保护**：`export()` 在 `sqlite3.connect` 后统一 `try/finally` 关闭连接；workspace/tag 创建纳入保护，杜绝泄漏。
3. **错误区分**：`MemoMindSchemaError` 与单文件错误分开，CLI（export/pipeline）单独 catch 并友好提示，避免 stack trace。
4. **备份提示**：直写前 `logger.warning` 提示先备份 MemoMind 数据库。

**推荐的持久解**：优先使用 HTTP API 模式（`--api-url`，服务端契约由 MemoMind 维护）；SQLite 直写定位为 fallback，依赖 schema 匹配 + 写前自检兜底。

---

## 2. SimHash 大规模去重

### 2.1 算法

```
文本 → 分词（中文 2-gram + 英文单词）
     → 每个 token 计算 MD5 hash
     → 加权向量累加（bit=1 则 +1, bit=0 则 -1）
     → 生成 64 位指纹
     → 汉明距离比较（≤ 3 视为相似）
```

### 2.2 与 TF-IDF 对比

| 维度 | TF-IDF | SimHash |
|------|--------|---------|
| 时间复杂度 | O(n²) | O(n) |
| 适用规模 | < 1K 文件 | 10K+ 文件 |
| 精度 | 高 | 中等 |
| 外部依赖 | 零 | 零 |

---

## 3. 版本合并器

### 3.1 识别策略

按文件名去除版本号后分组：

| 版本模式 | 示例 |
|---------|------|
| `_v1`, `_v2` | `report_v1.md`, `report_v2.md` |
| `v1.`, `v2.` | `doc.v1.md` |
| `_ver1` | `design_ver1.md` |
| `_20260517` | `report_20260517.md` |
| `_final`, `_latest` | `report_final.md` |

### 3.2 选择最优版本

```
score = (文档价值评分, 内容长度, 文件修改时间)
取 max(score)
```

---

## 4. 增量更新

比较源文件与输出文件的 `mtime`，仅处理变更文件。

**限制**：
- 仅对已有输出目录有效
- 首次运行无效
- 不检测内容变更，仅检测时间戳

---

## 5. MemoMind 后处理模块

### 5.1 概述

`memomind_post.py` 提供导出后的智能处理能力，通过 MemoMind Python SDK 直接调用语义服务和知识图谱服务，无需 HTTP API 认证。

### 5.2 功能

| 功能 | 入口函数 | 调用的 MemoMind 服务 |
|------|---------|---------------------|
| 语义去重扫描 | `run_dedup_report()` | `SemanticService.scan_duplicates()` |
| 知识整理建议 | `run_consolidation_report()` | `KnowledgeGraphService.suggest_consolidation()` |

### 5.3 架构

```
doc-knowledge export --dedup --consolidate
  └─ memomind_post.run_dedup_report(db_path)
       └─ MemoMind(db_path)  # SDK 公共 API
            ├─ ._semantic.scan_duplicates()    → TF-IDF + 余弦相似度
            └─ ._kg.suggest_consolidation()    → Jaccard 相似度 + 陈旧检测
```

### 5.4 延迟导入

`memomind_post.py` 使用延迟导入策略：
- 模块级别不 `import memomind`
- 函数内部 `try: from memomind.api.client import MemoMind` + `except ImportError: 友好报错`
- 动机：MemoMind 是可选依赖，未安装时不应阻止正常导出流程

### 5.5 数据库安全

- 后处理仅**读取**笔记数据（扫描去重/整理建议），不执行写入/合并/删除
- `scan_duplicates()` 和 `suggest_consolidation()` 均为只读操作
- 如需实际合并，由用户根据报告手动执行

### 5.6 CLI 集成

```bash
# 导出 + 去重扫描
python -m doc_knowledge export <知识目录> -t memomind --db <路径> --dedup

# 导出 + 整理建议
python -m doc_knowledge export <知识目录> -t memomind --db <路径> --consolidate
```
