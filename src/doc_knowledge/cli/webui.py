"""webui 命令：启动 Gradio Web UI"""

import click

from doc_knowledge import __version__
from doc_knowledge.cli._helpers import console


@click.command("webui")
@click.option("--port", "port", default=7860, show_default=True,
              type=int, help="Web UI 端口")
@click.option("--share", "share", is_flag=True,
              help="生成公开分享链接（Gradio Share）")
def webui(port, share):
    """启动 Web 可视化界面"""
    console.print(f"[bold green]Doc-Knowledge v{__version__} — Web UI[/bold green]")
    console.print(f"端口: [cyan]{port}[/cyan]")
    if share:
        console.print("[yellow]生成公开分享链接...[/yellow]")
    try:
        from doc_knowledge.webui import launch_ui
        console.print("[dim]正在启动浏览器...[/dim]")
        launch_ui(share=share, port=port)
    except ImportError:
        console.print("[red]错误：gradio 未安装。请运行：pip install gradio[/red]")
    except Exception as e:
        console.print(f"[red]错误：{e}[/red]")
