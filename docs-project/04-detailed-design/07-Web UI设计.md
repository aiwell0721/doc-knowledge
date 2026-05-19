# Doc-Knowledge Web UI 设计

**创建时间**：2026-05-19  
**版本**：v0.1.0  
**状态**：✅ 已实现（事后补文档）

---

## 1. 设计目标

### 1.1 问题定义

CLI 界面功能强大但对非技术用户门槛高。需要提供一个可视化操作面板，让不熟悉命令行的用户也能完成完整的文档知识提取流程。

### 1.2 成功标准

| 指标 | 目标 |
|------|------|
| 覆盖全部 CLI 命令 | ✅ 4 个命令全部有对应界面 |
| 一键全流程 | ✅ Pipeline 命令作为主标签 |
| 动态表单 | ✅ 根据选择自动显/隐相关字段 |
| 实时日志 | ✅ 后台执行，实时输出 |
| 零依赖启动 | ✅ `doc-knowledge webui` 一条命令 |

### 1.3 技术选型

| 方案 | 选型 | 理由 |
|------|------|------|
| Web 框架 | **Gradio** | Python 原生、零前端代码、自动表单生成 |
| 替代方案（未选） | Streamlit | 表单交互不如 Gradio 灵活 |
| 替代方案（未选） | Flask + HTML | 需要写前端代码，违反极简原则 |

### 1.4 依赖管理

```toml
[project.optional-dependencies]
webui = [
    "gradio>=5.0.0",
]
```

作为可选依赖安装：`pip install doc-knowledge[webui]`

---

## 2. 页面架构

### 2.1 整体结构

```
┌──────────────────────────────────────────────┐
│  📚 Doc-Knowledge v0.2.0                     │
│  文档知识提取工具                             │
├──────────────────────────────────────────────┤
│  [🚀 一键] [🔄 转换] [🧠 提取] [📤 导出] [📖 指南] │
├──────────────────────────────────────────────┤
│                                              │
│              当前标签页内容                    │
│                                              │
├──────────────────────────────────────────────┤
│  [开始按钮]                                   │
│  状态：___                                    │
│  日志：___                                    │
└──────────────────────────────────────────────┘
```

### 2.2 5 个标签页

| 序号 | 标签 | 对应 CLI 命令 | 定位 |
|------|------|---------------|------|
| 1 | 🚀 一键全流程 | `pipeline` | **主推荐**，一次完成 A→B→C→导出 |
| 2 | 🔄 转换 | `convert` | 仅做文档 → Markdown 转换 |
| 3 | 🧠 提取 | `extract` | 仅做去重 + 评分 + 标签 |
| 4 | 📤 导出 | `export` | 仅做导出到目标系统 |
| 5 | 📖 指南 | - | 使用说明文档 |

---

## 3. 各标签页详细设计

### 3.1 🚀 一键全流程（核心标签）

#### 左侧输入区

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 源文档目录 | 文本框 | ✅ | 源文件路径（支持 Windows/Unix） |
| 最终输出目录 | 文本框 | ❌ | 留空自动生成 |
| 导出目标 | 下拉 | ✅ | markdown / obsidian / memomind |
| Obsidian Vault 路径 | 文本框 | 条件 | target=obsidian 时显示 |
| MemoMind API URL | 文本框 | 条件 | target=memomind 时显示 |
| MemoMind API Key | 密码框 | 条件 | target=memomind 时显示 |
| MemoMind 工作区 | 文本框 | 条件 | target=memomind 时显示，默认 default |
| MemoMind SQLite 路径 | 文本框 | 条件 | target=memomind 时显示（MCP 模式） |

#### 右侧配置区

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 去重阈值 | 滑动条 (0-1) | 0.85 | TF-IDF 去重阈值 |
| 最低价值评分 | 滑动条 (0-100) | 30 | 低于此分被淘汰 |
| SimHash 大规模去重 | 复选框 | 关 | 适合 10K+ 文件 |
| 版本合并 | 复选框 | 关 | 多版本→最优版 |
| 增量更新 | 复选框 | 关 | 仅处理变更文件 |
| 图片 OCR 识别 | 复选框 | 关 | 启用大模型视觉 |
| OCR API URL | 文本框 | 条件 | OCR 开启时显示 |
| OCR API Key | 密码框 | 条件 | OCR 开启时显示 |
| OCR 模型 | 文本框 | qwen-vl-plus | OCR 开启时显示 |
| 详细日志 | 复选框 | 关 | 输出详细日志 |

#### 动态行为

```
导出目标变化 → 
  obsidian  → 显示 Vault 路径，隐藏 MemoMind 字段
  memomind  → 显示 API URL/Key/工作区/DB，隐藏 Vault
  markdown  → 隐藏所有目标专属字段

图片 OCR 变化 →
  开启 → 显示 API URL/Key/模型
  关闭 → 隐藏上述字段
```

### 3.2 🔄 转换

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 源文档目录 | 文本框 | - | 必填 |
| 输出目录 | 文本框 | 自动 | 可选 |
| 格式过滤 | 文本框 | - | 逗号分隔，如 pdf,docx |
| 递归子目录 | 复选框 | 开启 | - |
| 覆盖已存在 | 复选框 | 关 | - |
| Dry Run | 复选框 | 关 | 仅预览 |
| 图片 OCR | 复选框 | 关 | 开启后显示 API 配置 |
| 详细日志 | 复选框 | 关 | - |

### 3.3 🧠 提取

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| Markdown 镜像目录 | 文本框 | - | 必填 |
| 输出目录 | 文本框 | 自动 | 可选 |
| 去重阈值 | 滑动条 (0-1) | 0.85 | - |
| 最低价值评分 | 滑动条 (0-100) | 30 | - |
| SimHash 大规模去重 | 复选框 | 关 | - |
| 版本合并 | 复选框 | 关 | - |
| 保留去重版本 | 复选框 | 关 | 存到 deprecated/ |
| Dry Run | 复选框 | 关 | 仅预览 |
| 详细日志 | 复选框 | 关 | - |

### 3.4 📤 导出

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 知识目录 | 文本框 | - | 必填 |
| 导出目标 | 下拉 | markdown | obsidian/memomind/markdown |
| Obsidian Vault 路径 | 文本框 | - | target=obsidian 时显示 |
| 输出目录 | 文本框 | 自动 | target=markdown 时显示 |
| MemoMind API URL | 文本框 | - | target=memomind 时显示 |
| MemoMind API Key | 文本框 | - | target=memomind 时显示 |
| MemoMind 工作区 | 文本框 | default | target=memomind 时显示 |
| MemoMind SQLite 路径 | 文本框 | - | target=memomind 时显示 |

### 3.5 📖 指南

静态 Markdown 页面，包含：
- 流程说明（A→B→C→导出流程图）
- 最简单用法
- 进阶选项说明
- 支持格式列表
- 命令行参考

---

## 4. 技术实现

### 4.1 文件结构

```
src/doc_knowledge/
├── webui.py          # Web UI 主文件（Gradio Blocks）
├── __main__.py       # python -m doc_knowledge 入口
├── cli.py            # CLI（新增 webui 子命令）
└── ...
```

### 4.2 CLI 集成

```python
@main.command()
@click.option("--port", default=7860, type=int, help="Web UI 端口")
@click.option("--share", is_flag=True, help="生成公开分享链接")
def webui(port, share):
    """启动 Web 可视化界面"""
    launch_ui(share=share, port=port)
```

### 4.3 命令执行机制

```python
def run_command(cmd: list[str], log_lines: list[str]) -> str:
    """后台执行 CLI 命令，实时收集日志"""
    proc = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, ...)
    for line in proc.stdout:
        log_lines.append(line.rstrip())
    proc.wait()
    return f"✅ 完成（退出码 {proc.returncode}）"
```

- 使用 `subprocess.Popen` 后台执行，不阻塞 UI
- 实时读取 stdout/stderr，追加到日志框
- 完成后返回状态码

### 4.4 动态表单实现

使用 Gradio 的 `visible` 参数 + `change` 事件监听：

```python
def toggle_pipe_target(target):
    return (
        gr.update(visible=target == "obsidian"),
        gr.update(visible=target == "memomind"),
        ...
    )
pipe_target.change(toggle_pipe_target, pipe_target, [pipe_vault, ...])
```

### 4.5 主题

```python
theme = gr.themes.Soft(
    primary_hue="emerald",    # 翡翠绿（知识/文档感）
    secondary_hue="slate",    # 石板灰（工具感）
    font=gr.themes.GoogleFont("Inter"),
)
```

---

## 5. 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| 文件选择器 | Gradio TextBox 需手动输入路径，无文件浏览器 | 低 |
| Windows 路径 | 用户需输入完整路径（如 D:\docs） | 低 |
| 并发执行 | 不支持同时执行多个任务 | 低 |
| 进度条 | 实时日志文本，无可视化进度条 | 中 |

---

## 6. Phase 4 规划（后续）

- [ ] 文件浏览器组件（支持目录选择）
- [ ] 可视化进度条
- [ ] 任务队列（多任务排队执行）
- [ ] 历史记录（查看最近执行的任务）
- [ ] 配置保存/加载（预设常用参数）

---

## 7. 变更记录

| 日期 | 变更 | 版本 |
|------|------|------|
| 2026-05-19 | 初始设计文档（事后补录） | v0.1.0 |
