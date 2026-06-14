# Doc-Knowledge Phase 2 详细设计

**创建时间**：2026-05-17
**更新日期**：2026-06-15
**版本**：v0.2.0

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
