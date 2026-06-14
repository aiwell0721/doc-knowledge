# Doc-Knowledge CLI 设计规范

**创建时间**：2026-05-17
**更新日期**：2026-06-15
**版本**：v0.3.0

---

> **2026-06-14 代码组织调整**：CLI 实现从单文件 `cli.py`（724 行）拆分为 `cli/` 包。每个命令一个文件，共享逻辑收敛到 `_helpers.py` 与 `_options.py`。`from doc_knowledge.cli import main` 入口保持不变（通过 `cli/__init__.py` re-export），命令行使用无任何变化。
>
> ```
> src/doc_knowledge/cli/
> ├── __init__.py     # 装配 main group + 注册子命令 + re-export main
> ├── _helpers.py     # console 单例 + _setup_ocr / _run_convert / _run_extract / ...
> ├── _options.py     # 共享 click 装饰器：ocr_options, memomind_options, memomind_post_options
> ├── convert.py
> ├── extract.py
> ├── export.py
> ├── pipeline.py
> └── webui.py
> ```

---

## 1. 命令概览

```bash
doc-knowledge convert <source_dir> [OPTIONS]
doc-knowledge extract <mirror_dir> [OPTIONS]
doc-knowledge export <knowledge_dir> [OPTIONS]
doc-knowledge pipeline <source_dir> [OPTIONS]
```

## 2. convert 命令

```bash
doc-knowledge convert <source_dir> [OPTIONS]

参数:
  source_dir          源文件目录（目录 A）

选项:
  -o, --output DIR    输出目录（目录 B，默认 <source_dir>_mirror）
  --format FORMAT     仅转换指定格式（pdf,pptx,docx,xlsx）
  --recursive         递归子目录（默认开启）
  --overwrite         覆盖已存在的文件
  --dry-run           仅显示将要转换的文件，不实际转换
```

## 3. extract 命令

```bash
doc-knowledge extract <mirror_dir> [OPTIONS]

参数:
  mirror_dir          Markdown 镜像目录（目录 B）

选项:
  -o, --output DIR    输出目录（目录 C，默认 <mirror_dir>_extracted）
  --threshold FLOAT   去重阈值（0.0-1.0，默认 0.85）
  --min-score INT     最低价值评分（0-100，默认 30）
  --keep-deprecated   保留去重的旧版本到 deprecated/ 目录
  --dry-run           仅显示提取计划，不实际执行
```

## 4. export 命令

```bash
doc-knowledge export <knowledge_dir> [OPTIONS]

参数:
  knowledge_dir       知识文档目录（目录 C）

选项:
  -t, --target TYPE   导出目标（obsidian, memomind, markdown）
  --vault DIR         Obsidian Vault 路径
  --api-url URL       MemoMind API 地址
  --api-key KEY       MemoMind API Key
  --db PATH           MemoMind SQLite 数据库路径（MCP 本地模式）
  --workspace NAME    MemoMind 工作区名称
  -o, --output DIR    Markdown 输出目录（当 target=markdown）
  --dedup             导出后运行 MemoMind TF-IDF 语义去重扫描
  --consolidate       导出后运行知识整理建议（主题聚类/合并建议/陈旧检测）
```

## 5. pipeline 命令

```bash
doc-knowledge pipeline <source_dir> [OPTIONS]

参数:
  source_dir          源文件目录（目录 A）

选项:
  -o, --output DIR    最终输出目录
  -t, --target TYPE   导出目标（obsidian, memomind, markdown）
  --vault DIR         Obsidian Vault 路径
  --api-url URL       MemoMind API 地址
  --db PATH           MemoMind SQLite 数据库路径（MCP 本地模式）
  --temp-dir DIR      临时目录（默认系统临时目录）
  --threshold FLOAT   去重阈值（默认 0.85）
  --min-score INT     最低价值评分（默认 30）
  --dedup             导出后运行 MemoMind TF-IDF 语义去重扫描
  --consolidate       导出后运行知识整理建议（主题聚类/合并建议/陈旧检测）
```

## 6. 通用选项

```bash
  -v, --verbose       详细输出
  -q, --quiet         静默模式
  --config FILE       配置文件路径
  --version           显示版本号
  --help              显示帮助
```
