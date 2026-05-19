# Doc-Knowledge Phase 2 详细设计

**创建时间**：2026-05-17
**版本**：v0.1.0

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
