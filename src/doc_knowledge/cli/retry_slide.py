"""retry-slide 命令：补跑已有 markdown 的失败页

slide 模式（整页渲染 + 云端 VLM）受免费模型限流影响，部分页可能重试耗尽仍失败。
额度随时间恢复后，本命令对失败页重新渲染源 PPTX、仅识别失败页、更新 markdown，
不重跑成功页、省额度。
"""

import re
from pathlib import Path

import click

from doc_knowledge.cli._helpers import console
from doc_knowledge.converters import _update_slide_blockquotes
from doc_knowledge.ocr.slide import SlideFusionService


@click.command("retry-slide")
@click.argument("markdown_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--ocr-api-url", default="", help="VLM API 地址（OpenAI 兼容）")
@click.option("--ocr-api-key", default="", help="VLM API Key")
@click.option("--ocr-model", default="glm-4.6v-flash", help="VLM 模型名称")
@click.option("-v", "--verbose", is_flag=True, help="详细输出")
def retry_slide(markdown_path: Path, ocr_api_url: str, ocr_api_key: str,
                ocr_model: str, verbose: bool):
    """对 slide 模式输出 markdown 中限流失败的页补跑识别

    用法：doc-knowledge retry-slide <output.md> --ocr-api-url ... --ocr-api-key ...
    """
    md_text = markdown_path.read_text(encoding="utf-8")

    # 1) 解析 frontmatter source → 源 PPTX 路径
    m = re.search(r'^source: "file:///(.+)"$', md_text, re.M)
    if not m:
        raise click.ClickException("未找到 frontmatter source 字段，无法定位源 PPTX")
    source_path = Path(m.group(1))
    if not source_path.exists():
        raise click.ClickException(f"源文件不存在: {source_path}")

    # 2) 解析失败块 → 失败页清单
    #    新形态：独立行 ⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留
    #    旧形态：> 📊 **整页理解**: ⚠️... 或 > 📊 **整页理解**: [错误堆栈]
    failed_pages = sorted({
        int(n) for n in re.findall(
            r"<!-- Slide number: (\d+) -->\s*\n+\s*"
            r"(?:⚠️ 本页图表语义识别失败（VLM 请求异常），原始文字已保留"
            r"|> 📊 \*\*整页理解\*\*: (?:⚠️|\[[^\r\n]*\]))",
            md_text,
        )
    })
    if not failed_pages:
        console.print("[dim]未找到失败页（无降级提示块），无需补跑[/dim]")
        return

    # 3) 渲染源 PPTX + 仅识别失败页（含自动二次补跑）
    svc = SlideFusionService(api_url=ocr_api_url, api_key=ocr_api_key, model=ocr_model)
    console.print(f"[cyan]补跑 {len(failed_pages)} 个失败页: {failed_pages}[/cyan]")
    results = svc.retry_pages(
        source_path, markdown_path.parent, page_numbers=failed_pages, verbose=verbose,
    )

    # 4) 更新 markdown
    new_md = _update_slide_blockquotes(md_text, results)
    markdown_path.write_text(new_md, encoding="utf-8")

    succeeded = [n for n, t in results.items() if t and not t.startswith("[")]
    console.print(
        f"[bold green]补跑完成：成功 {len(succeeded)} 页[/bold green]，"
        f"仍失败 {len(failed_pages) - len(succeeded)} 页（可稍后再试）"
    )
