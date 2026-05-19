"""
Doc-Knowledge Web UI — Gradio 界面

可视化操作面板，覆盖 4 个命令：
- Convert（文档 → Markdown）
- Extract（去重 + 评分 + 标签）
- Export（Obsidian / MemoMind）
- Pipeline（一键全流程）
"""

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import gradio as gr

from doc_knowledge import __version__

# ────────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────────

def run_command(cmd: list[str], log_lines: list[str]) -> str:
    """后台执行 CLI 命令，实时收集日志"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log_lines.append(line)
        proc.wait()
        return f"✅ 完成（退出码 {proc.returncode}）"
    except Exception as e:
        return f"❌ 错误：{e}"


def find_python() -> str:
    """找到当前 Python 解释器路径"""
    return sys.executable


def build_cmd(base_cmd: list[str]) -> list[str]:
    return [find_python(), "-m", "doc_knowledge"] + base_cmd


# ────────────────────────────────────────────────────
# Convert 页面
# ────────────────────────────────────────────────────

def do_convert(source, output, format_filter, recursive, overwrite, dry_run,
               vision, api_url, api_key, model, verbose):
    log_lines = []
    cmd = build_cmd(["convert", source])

    if output:
        cmd += ["-o", output]
    if format_filter:
        for fmt in format_filter.split(","):
            fmt = fmt.strip()
            if fmt:
                cmd += ["--format", fmt]
    if not recursive:
        cmd += ["--no-recursive"]
    if overwrite:
        cmd += ["--overwrite"]
    if dry_run:
        cmd += ["--dry-run"]
    if vision:
        cmd += ["--vision"]
        if api_url:
            cmd += ["--api-url", api_url]
        if api_key:
            cmd += ["--api-key", api_key]
        cmd += ["--model", model or "qwen-vl-plus"]
    if verbose:
        cmd += ["-v"]

    status = run_command(cmd, log_lines)
    return status, "\n".join(log_lines)


# ────────────────────────────────────────────────────
# Extract 页面
# ────────────────────────────────────────────────────

def do_extract(mirror_dir, output, threshold, min_score, simhash, merge,
               keep_deprecated, dry_run, verbose):
    log_lines = []
    cmd = build_cmd(["extract", mirror_dir])

    if output:
        cmd += ["-o", output]
    cmd += ["--threshold", str(threshold)]
    cmd += ["--min-score", str(min_score)]
    if simhash:
        cmd += ["--simhash"]
    if merge:
        cmd += ["--merge"]
    if keep_deprecated:
        cmd += ["--keep-deprecated"]
    if dry_run:
        cmd += ["--dry-run"]
    if verbose:
        cmd += ["-v"]

    status = run_command(cmd, log_lines)
    return status, "\n".join(log_lines)


# ────────────────────────────────────────────────────
# Export 页面
# ────────────────────────────────────────────────────

def do_export(knowledge_dir, target, vault_path, output_dir,
              api_url, api_key, workspace, db_path):
    log_lines = []
    cmd = build_cmd(["export", knowledge_dir])

    cmd += ["-t", target]
    if target == "obsidian" and vault_path:
        cmd += ["--vault", vault_path]
    elif target == "markdown" and output_dir:
        cmd += ["-o", output_dir]
    elif target == "memomind":
        if api_url:
            cmd += ["--api-url", api_url]
        if api_key:
            cmd += ["--api-key", api_key]
        if workspace:
            cmd += ["--workspace", workspace]
        if db_path:
            cmd += ["--db", db_path]

    status = run_command(cmd, log_lines)
    return status, "\n".join(log_lines)


# ────────────────────────────────────────────────────
# Pipeline 页面
# ────────────────────────────────────────────────────

def do_pipeline(source, output, target, vault_path, api_url, api_key, workspace, db_path,
                threshold, min_score, simhash, merge, incremental,
                vision, vision_api_url, vision_api_key, vision_model,
                verbose):
    log_lines = []
    cmd = build_cmd(["pipeline", source])

    if output:
        cmd += ["-o", output]
    cmd += ["-t", target]
    if target == "obsidian" and vault_path:
        cmd += ["--vault", vault_path]
    if target == "memomind":
        if api_url:
            cmd += ["--api-url", api_url]
        if api_key:
            cmd += ["--api-key", api_key]
        if workspace:
            cmd += ["--workspace", workspace]
        if db_path:
            cmd += ["--db", db_path]
    cmd += ["--threshold", str(threshold)]
    cmd += ["--min-score", str(min_score)]
    if simhash:
        cmd += ["--simhash"]
    if merge:
        cmd += ["--merge"]
    if incremental:
        cmd += ["--incremental"]
    if vision:
        cmd += ["--vision"]
        if vision_api_url:
            cmd += ["--vision-api-url", vision_api_url]
        if vision_api_key:
            cmd += ["--vision-api-key", vision_api_key]
        if vision_model:
            cmd += ["--vision-model", vision_model]
    if verbose:
        cmd += ["-v"]

    status = run_command(cmd, log_lines)
    return status, "\n".join(log_lines)


# ────────────────────────────────────────────────────
# UI 构建
# ────────────────────────────────────────────────────

theme = gr.themes.Soft(
    primary_hue="emerald",
    secondary_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
)

with gr.Blocks(title=f"Doc-Knowledge v{__version__}") as app:
    gr.Markdown(f"# 📚 Doc-Knowledge v{__version__}")
    gr.Markdown("文档知识提取工具 — 将 Office 文档批量转换为结构化 Markdown 知识库")

    with gr.Tabs():
        # ── Tab 1: Pipeline（一键全流程）──
        with gr.Tab("🚀 一键全流程"):
            gr.Markdown("### A → B → C → 目标系统，一次搞定")
            with gr.Row():
                with gr.Column(scale=1):
                    pipe_source = gr.Textbox(label="📂 源文档目录", placeholder="D:\\docs\\source", lines=1)
                    pipe_output = gr.Textbox(label="📤 最终输出目录（可选）", placeholder="留空则自动生成", lines=1)
                    pipe_target = gr.Dropdown(
                        label="🎯 导出目标", choices=["markdown", "obsidian", "memomind"],
                        value="markdown",
                    )
                    pipe_vault = gr.Textbox(label="📓 Obsidian Vault 路径", placeholder="D:\\ObsidianVault", lines=1, visible=False)
                    pipe_api_url = gr.Textbox(label="🔗 MemoMind API URL", placeholder="http://localhost:8000", lines=1, visible=False)
                    pipe_api_key = gr.Textbox(label="🔑 MemoMind API Key", lines=1, visible=False)
                    pipe_workspace = gr.Textbox(label="📁 MemoMind 工作区", value="default", lines=1, visible=False)
                    pipe_db_path = gr.Textbox(label="🗄️ MemoMind SQLite 路径", placeholder="memomind.db", lines=1, visible=False)

                with gr.Column(scale=1):
                    pipe_threshold = gr.Slider(label="去重阈值", minimum=0, maximum=1, value=0.85, step=0.05)
                    pipe_min_score = gr.Slider(label="最低价值评分", minimum=0, maximum=100, value=30, step=5)
                    pipe_simhash = gr.Checkbox(label="SimHash 大规模去重（10K+ 文件）")
                    pipe_merge = gr.Checkbox(label="版本合并（多版本→最优版）")
                    pipe_incremental = gr.Checkbox(label="增量更新（仅处理变更）")
                    pipe_vision = gr.Checkbox(label="图片 OCR 识别")
                    pipe_vision_api_url = gr.Textbox(label="OCR API URL", placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1", lines=1, visible=False)
                    pipe_vision_api_key = gr.Textbox(label="OCR API Key", type="password", lines=1, visible=False)
                    pipe_vision_model = gr.Textbox(label="OCR 模型", value="qwen-vl-plus", lines=1, visible=False)
                    pipe_verbose = gr.Checkbox(label="详细日志")

            pipe_btn = gr.Button("🚀 开始全流程", variant="primary", size="lg")
            pipe_status = gr.Textbox(label="状态", interactive=False)
            pipe_log = gr.Textbox(label="运行日志", lines=15, interactive=False, max_lines=100)

            def toggle_pipe_target(target):
                return (
                    gr.update(visible=target == "obsidian"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                )
            pipe_target.change(toggle_pipe_target, pipe_target, [pipe_vault, pipe_api_url, pipe_api_key, pipe_workspace, pipe_db_path])

            def toggle_vision(v):
                return [gr.update(visible=v)] * 3
            pipe_vision.change(toggle_vision, pipe_vision, [pipe_vision_api_url, pipe_vision_api_key, pipe_vision_model])

            pipe_btn.click(
                do_pipeline,
                [pipe_source, pipe_output, pipe_target, pipe_vault, pipe_api_url, pipe_api_key,
                 pipe_workspace, pipe_db_path, pipe_threshold, pipe_min_score, pipe_simhash,
                 pipe_merge, pipe_incremental, pipe_vision, pipe_vision_api_url,
                 pipe_vision_api_key, pipe_vision_model, pipe_verbose],
                [pipe_status, pipe_log],
            )

        # ── Tab 2: Convert ──
        with gr.Tab("🔄 转换"):
            gr.Markdown("### A → B：文档转 Markdown 镜像")
            with gr.Row():
                with gr.Column(scale=1):
                    cvt_source = gr.Textbox(label="📂 源文档目录", placeholder="D:\\docs\\source", lines=1)
                    cvt_output = gr.Textbox(label="📤 输出目录（可选）", placeholder="留空则自动生成 _mirror", lines=1)
                    cvt_format = gr.Textbox(label="格式过滤（逗号分隔，可选）", placeholder="pdf,docx,pptx", lines=1)
                    cvt_recursive = gr.Checkbox(label="递归子目录", value=True)
                    cvt_overwrite = gr.Checkbox(label="覆盖已存在文件")
                    cvt_dry = gr.Checkbox(label="Dry Run（仅预览）")

                with gr.Column(scale=1):
                    cvt_vision = gr.Checkbox(label="图片 OCR 识别")
                    cvt_api_url = gr.Textbox(label="OCR API URL", placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1", lines=1, visible=False)
                    cvt_api_key = gr.Textbox(label="OCR API Key", type="password", lines=1, visible=False)
                    cvt_model = gr.Textbox(label="OCR 模型", value="qwen-vl-plus", lines=1, visible=False)
                    cvt_verbose = gr.Checkbox(label="详细日志")

            cvt_btn = gr.Button("🔄 开始转换", variant="primary")
            cvt_status = gr.Textbox(label="状态", interactive=False)
            cvt_log = gr.Textbox(label="运行日志", lines=12, interactive=False)

            cvt_vision.change(toggle_vision, cvt_vision, [cvt_api_url, cvt_api_key, cvt_model])

            cvt_btn.click(
                do_convert,
                [cvt_source, cvt_output, cvt_format, cvt_recursive, cvt_overwrite,
                 cvt_dry, cvt_vision, cvt_api_url, cvt_api_key, cvt_model, cvt_verbose],
                [cvt_status, cvt_log],
            )

        # ── Tab 3: Extract ──
        with gr.Tab("🧠 提取"):
            gr.Markdown("### B → C：去重 + 价值评分 + 自动标签")
            with gr.Row():
                with gr.Column(scale=1):
                    ext_mirror = gr.Textbox(label="📂 Markdown 镜像目录", placeholder="D:\\docs\\mirror", lines=1)
                    ext_output = gr.Textbox(label="📤 输出目录（可选）", placeholder="留空则自动生成 _extracted", lines=1)
                    ext_threshold = gr.Slider(label="去重阈值", minimum=0, maximum=1, value=0.85, step=0.05)
                    ext_min_score = gr.Slider(label="最低价值评分", minimum=0, maximum=100, value=30, step=5)
                    ext_dry = gr.Checkbox(label="Dry Run（仅预览）")

                with gr.Column(scale=1):
                    ext_simhash = gr.Checkbox(label="SimHash 大规模去重")
                    ext_merge = gr.Checkbox(label="版本合并")
                    ext_keep_dep = gr.Checkbox(label="保留去重版本到 deprecated/")
                    ext_verbose = gr.Checkbox(label="详细日志")

            ext_btn = gr.Button("🧠 开始提取", variant="primary")
            ext_status = gr.Textbox(label="状态", interactive=False)
            ext_log = gr.Textbox(label="运行日志", lines=12, interactive=False)

            ext_btn.click(
                do_extract,
                [ext_mirror, ext_output, ext_threshold, ext_min_score, ext_simhash,
                 ext_merge, ext_keep_dep, ext_dry, ext_verbose],
                [ext_status, ext_log],
            )

        # ── Tab 4: Export ──
        with gr.Tab("📤 导出"):
            gr.Markdown("### C → 目标系统（Obsidian / MemoMind / Markdown）")
            with gr.Row():
                with gr.Column(scale=1):
                    exp_knowledge = gr.Textbox(label="📂 知识目录", placeholder="D:\\docs\\knowledge", lines=1)
                    exp_target = gr.Dropdown(
                        label="🎯 导出目标", choices=["markdown", "obsidian", "memomind"],
                        value="markdown",
                    )
                    exp_vault = gr.Textbox(label="📓 Obsidian Vault 路径", lines=1, visible=False)
                    exp_output = gr.Textbox(label="📤 输出目录", placeholder="D:\\docs\\exported", lines=1)
                    exp_api_url = gr.Textbox(label="🔗 MemoMind API URL", lines=1, visible=False)
                    exp_api_key = gr.Textbox(label="🔑 MemoMind API Key", lines=1, visible=False)
                    exp_workspace = gr.Textbox(label="📁 MemoMind 工作区", value="default", lines=1, visible=False)
                    exp_db = gr.Textbox(label="🗄️ MemoMind SQLite 路径", lines=1, visible=False)

            exp_btn = gr.Button("📤 开始导出", variant="primary")
            exp_status = gr.Textbox(label="状态", interactive=False)
            exp_log = gr.Textbox(label="运行日志", lines=12, interactive=False)

            def toggle_exp_target(target):
                return (
                    gr.update(visible=target == "obsidian"),
                    gr.update(visible=target == "markdown"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                    gr.update(visible=target == "memomind"),
                )
            exp_target.change(toggle_exp_target, exp_target,
                              [exp_vault, exp_output, exp_api_url, exp_api_key, exp_workspace, exp_db])

            exp_btn.click(
                do_export,
                [exp_knowledge, exp_target, exp_vault, exp_output,
                 exp_api_url, exp_api_key, exp_workspace, exp_db],
                [exp_status, exp_log],
            )

        # ── Tab 5: 快速开始指南 ──
        with gr.Tab("📖 指南"):
            gr.Markdown("""
## 快速开始

### 流程说明

```
源文档 (A) ──convert──→ Markdown 镜像 (B) ──extract──→ 知识库 (C) ──export──→ 目标系统
   PDF/DOCX/PPTX/XLSX         .md 文件                去重+评分+标签       Obsidian/MemoMind
```

### 最简单用法

1. 切换到 **🚀 一键全流程** 标签
2. 填写 **源文档目录**（你的 PDF/DOCX/PPTX 文件夹）
3. 选择 **导出目标**（默认 Markdown）
4. 点击 **🚀 开始全流程**

### 进阶选项

| 选项 | 说明 |
|------|------|
| SimHash 去重 | 适合 10K+ 大规模文件，O(n) 算法 |
| 版本合并 | 自动识别 v1/v2/final 等版本，保留最优版 |
| 增量更新 | 仅处理变更过的文件，节省时间 |
| 图片 OCR | 启用大模型识别文档中的图片内容 |

### 支持的格式

- **完整转换**: DOCX, PDF, PPTX, XLSX, TXT
- **图片复制**: PNG, JPG, JPEG, GIF, BMP, WebP, SVG
- **其他格式**: 自动包装为 Markdown 元数据

### 命令行参考

```bash
# 安装完整版
pip install doc-knowledge[full]

# 一键全流程
doc-knowledge pipeline D:\\docs --target markdown

# 导出到 Obsidian
doc-knowledge pipeline D:\\docs --target obsidian --vault D:\\Vault

# 导出到 MemoMind
doc-knowledge pipeline D:\\docs --target memomind --api-url http://localhost:8000
```
            """)


def launch_ui(share: bool = False, port: int = 7860):
    """启动 Web UI"""
    app.launch(server_name="127.0.0.1", server_port=port, share=share, inbrowser=True, theme=theme)


if __name__ == "__main__":
    launch_ui()
