# Doc-Knowledge Phase 5 开发计划

**创建时间**：2026-06-14
**版本**：v0.1.0
**状态**：📋 待启动

---

## Phase 4 回顾（已完成）

| 指标 | 结果 |
|------|------|
| 多维度测试 | 248 → 255（含 P1/P2 新增） |
| 通过率 | 100% |
| 重大重构 | 7 commits（OCR 统一管道 / cli.py 拆分 / 跨平台 / 阈值修复） |
| 版本 | 0.2.0 → 0.3.0 |

详见 `06-test-docs/05-多维度测试报告.md` 与 git log `25c6556..5526e2e`。

---

## Phase 5 状态：📋 待启动

**预估总用时**：约 8-10h
**核心目标**：清理 P3 杂项 + webui.py 拆分 + API 美化 + 持续质量度量

---

## Phase 5 任务清单

> 优先级标记：🔴 P3-A 高（影响维护）｜🟡 P3-B 中（影响体验）｜🟢 P3-C 低（锦上添花）

### 任务 1 — 🔴 修复 Pillow `getdata` deprecation

**问题**：`src/doc_knowledge/vision.py:72` 使用 `Image.getdata()`，将在 Pillow 14（2027-10-15）移除，当前每次跑测试都产生 13 条 DeprecationWarning。

**改动点**：
- `vision.py:72` `small.getdata()` → `small.get_flattened_data()`（Pillow 11+ 推荐 API）
- 检查 Pillow 最低版本声明（`pyproject.toml` 当前 `Pillow>=10.0.0`）：若新 API 在 11 才有，需要 bump 到 `>=11.0.0`，或 try/except 降级到旧 API

**验证**：
- TDD：`tests/test_vision.py::TestImageFilter::test_solid_color_detection` 仍通过
- `pytest -W error::DeprecationWarning tests/test_vision.py` 不再触发

**预估**：30 min

---

### 任务 2 — 🔴 拆分 webui.py（423 行）

**问题**：`src/doc_knowledge/webui.py` 423 行，结构与拆分前的 `cli.py` 类似（4 个 `do_*` 函数 + 巨型 `with gr.Blocks() as app:` 装配块）。维护性差。

**拆分目标**：
```
src/doc_knowledge/webui/
├── __init__.py        # 装配 + re-export launch_ui
├── _runners.py        # do_convert / do_extract / do_export / do_pipeline + build_cmd
├── tab_convert.py     # Convert 标签页 UI
├── tab_extract.py     # Extract 标签页 UI
├── tab_export.py      # Export 标签页 UI
├── tab_pipeline.py    # Pipeline 标签页 UI
└── theme.py           # gr.themes.Soft 配置
```

**约束**：
- `from doc_knowledge.webui import launch_ui` 入口必须保持工作（被 `cli/webui.py` 调用）
- `app` 全局变量（gr.Blocks）保持可导入（被 `tests/test_webui.py::TestAppImport` 验证）

**风险**：33 个 webui 测试。逐个标签页迁移时分批跑测试，避免一次性破坏。

**验证**：
- 全套 255 测试通过
- 手动启动 `dck webui` 确认 UI 渲染正常（4 个 tab 都能切换）

**预估**：2-3h（含手动验证）

---

### 任务 3 — 🟡 `convert_file` 返回值改 dataclass（P2-#9 延期）

**问题**：`converters/__init__.py:53` 返回 `tuple[str, int, dict[str, str]]`，三个不同含义的位置参数，调用方必须记顺序。

**设计**：
```python
@dataclass
class ConvertResult:
    markdown: str
    images_extracted: int
    image_map: dict[str, str]

def convert_file(...) -> ConvertResult: ...
```

**调用点**：
- `cli/_helpers.py:115` `_run_convert` 解包 tuple
- 7 个测试文件中的 `md, images, image_map = convert_file(...)` 需改为 `result = convert_file(...); result.markdown ...`

**破坏性变更**：是。但 0.3.0 已是 breaking 版本，可以一并做完。等到 0.4.0 反而会引入新一轮兼容期。

**验证**：
- TDD：新增 `test_convert_result_dataclass_fields` 验证结构
- 全套测试更新后通过
- 文档同步：`docs-project/04-detailed-design/02-转换器设计.md` 更新签名

**预估**：1.5h

---

### 任务 4 — 🟡 `_build_image_map` 改用文档流匹配（P2-#7 收尾）

**背景**：P2-#7 已通过"按文件名数字排序"修复 80% 的 DOCX 错位场景，剩余 20%（用户自定义图片命名、非数字序）仍可能错位。

**设计**：
- 用 `python-docx` 遍历 `document.element.iter()` 抓取 `<a:blip r:embed="rId7">` 顺序
- 通过 `document.part.related_parts[rId]` 取 image bytes
- 与 MarkItDown 走的是相同语义顺序

**与 P2-#7 对比**：
| 方案 | 改动 | 覆盖 |
|------|------|------|
| P2-#7 已实现 | ~15 行 | 80% case（imageN.png 自然命名） |
| 任务 4（本项） | ~80 行 + 5 测试 | 100% case（任意命名 + 复杂布局） |

**判断标准**：等用户实际反馈错位 bug 再做。若 Phase 5 期间无人提报，可挪到 Phase 6。

**预估**：3h（含测试）

---

### 任务 5 — 🟡 测试覆盖率持续追踪

**问题**：`docs-project/06-test-docs/04-测试工作流规范.md` 要求覆盖率 ≥ 90%，但目前没有 CI 阻断机制，每次 commit 都得手动跑 `make test-all` 查看。

**方案 A（推荐）**：本地 git pre-push hook
- `scripts/pre-push-coverage`：跑 `pytest --cov` 并检查 ≥ 85% 阈值（不达 90% 但比当前 86% 略高的硬约束）
- 写入 `~/.git/hooks/pre-push`
- 在 `CLAUDE.md` 加一行安装指令

**方案 B**：GitHub Actions
- 需求是否上 GitHub？若是私有项目无此需求可跳过

**方案 C（最简）**：在 `Makefile` 加 `make ci-check` 目标，包含 `pytest --cov-fail-under=85`

**预估**：方案 A 1h，方案 B 2h，方案 C 15 min

---

### 任务 6 — 🟢 文档：补 Phase 1 计划的"已完成"标记

**问题**：`docs-project/05-development-plan/01-Phase1开发计划.md` 内仍存在 "[ ] 待办" 状态项，但 Phase 1 已经远在 2026-05-19 完成。文档与现实脱节。

**改动**：
- `[ ]` → `[x]`，标注完成日期
- 顶部状态从 "🔄 进行中" 改为 "✅ 已完成（2026-05-19）"

**预估**：15 min

---

### 任务 7 — 🟢 README 与文档索引一致性审计

**问题**：项目根 `README.md` 在 P1/P2 期间多次未同步：
- 仍可能提到已移除的 `--vision`
- 版本号、CLI 选项示例可能停留在 0.2.0

**改动**：
- 通读 `README.md` 与 `docs/`（产品文档目录）所有面向用户的文件
- 与现有 CLI（`--ocr cloud/local`）和 0.3.0 版本同步
- 必要时更新 `docs-project/README.md` 索引

**预估**：30 min

---

## 总览

| # | 任务 | 优先级 | 预估 | 类型 | 备注 |
|---|------|--------|------|------|------|
| 1 | Pillow getdata deprecation | 🔴 高 | 30 min | 修复 | 2027 hard deadline |
| 2 | 拆分 webui.py | 🔴 高 | 2-3h | 重构 | 423 行单文件 |
| 3 | convert_file → dataclass | 🟡 中 | 1.5h | API 美化 | P2-#9 延期项 |
| 4 | 图片映射文档流匹配 | 🟡 中 | 3h | 鲁棒性 | P2-#7 收尾，按需触发 |
| 5 | 覆盖率持续追踪 | 🟡 中 | 15min - 2h | 流程 | 三方案择一 |
| 6 | Phase 1 文档收尾 | 🟢 低 | 15 min | 文档 | |
| 7 | README/docs 一致性 | 🟢 低 | 30 min | 文档 | |

**最短路径**（仅红色项 + 文档收尾）：~3-4h
**完整路径**（含蓝紫色）：~8-10h

---

## 成功标准

### 必达（红色项）
- [ ] `pytest -W error::DeprecationWarning` 全套通过
- [ ] `src/doc_knowledge/webui/` 包替代单文件 `webui.py`，33 个 webui 测试不变
- [ ] 手动启动 webui 验证 4 个 tab 渲染正常

### 完成度（含中色项）
- [ ] `convert_file` 返回值改 dataclass，调用点全部迁移
- [ ] 覆盖率持续追踪机制就位（方案 A/B/C 之一）
- [ ] 全套测试保持 255+ 通过、覆盖率 ≥ 85%

### 收尾（绿色项）
- [ ] Phase 1 计划文档完成度更新
- [ ] README 与 0.3.0 当前状态一致

---

## 依赖与风险

| 风险 | 缓解 |
|------|------|
| webui 拆分破坏 33 个 UI 测试 | 逐 tab 迁移，每迁移一个跑 `pytest tests/test_webui.py` |
| dataclass 改动破坏外部调用方 | 若 doc-knowledge 已被外部 import：保留 tuple 解包兼容（`__iter__` 方法） |
| Pillow 新 API 不在 10.x | 用 `try: ... except AttributeError: ... # fallback` |

---

## 执行顺序建议

```
任务 6（15 min，热身，建立 momentum）
   ↓
任务 1（30 min，红色项快速清理）
   ↓
任务 5 方案 C（15 min，加 cov 阈值）
   ↓
任务 3（1.5h，API 美化，破坏性变更趁 0.3.0 一起做）
   ↓
任务 2（2-3h，最大块，留充足时间）
   ↓
任务 7（30 min，最终收尾）
   ↓
[任务 4 按需触发]
```

---

## 团队分工（建议）

| 角色 | 职责 |
|------|------|
| **main** | 任务 2、3 主导（重构）、任务 6/7 文档收尾 |
| **test** | 任务 1（deprecation 修复 + 回归）、任务 5（覆盖率追踪） |
| **review** | 每个 commit 后跑全套测试 + 手动验证 webui |

---

## Phase 6 预告（不在本期）

- 任务 4（图片映射文档流匹配）若用户反馈错位 bug，提至 Phase 6 首项
- `hybrid` OCR 模式真实现（P2-#6 仅做了 [WIP] 标记）
- 端到端性能基准测试（10K 文档级别）
- CHANGELOG.md 体系建立（每次 minor bump 维护）

---

*执行准则：遵循全局法则二（先文档后编码）和法则三（手术刀式修改）。每项任务先更新对应设计文档，再改代码，最后跑测试。*
