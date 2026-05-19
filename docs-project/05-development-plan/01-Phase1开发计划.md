# Doc-Knowledge Phase 1 开发计划

**创建时间**：2026-05-17
**更新日期**：2026-05-17
**版本**：v0.3.0

---

## Phase 1 状态：✅ 已完成（2026-05-17）

**实际用时**：约 3 小时
**测试覆盖**：39 测试，100% 通过
**端到端验证**：pipeline 命令验证通过（A→B→C→导出）

---

## Phase 1 目标：MVP（最小可行产品）

**范围**：完成 A→B→C→导出 全链路，支持 4 种格式转换 + 去重 + 价值评分 + 标签 + Obsidian 导出

**技术决策**：转换层封装 MarkItDown（123K stars），自研差异化能力（去重/评分/标签）。

**加速决策**：MarkItDown 替代 4 个自研转换器，开发周期从 7 天压缩到 3 天。

## 开发计划（加速版）

| # | 任务 | 类型 | 预估 | 依赖 | 备注 |
|---|------|------|------|------|------|
| 1 | 安装 MarkItDown + 清理旧转换器 | 基建 | 2h | - | 删除 pdf/docx_converter.py |
| 2 | MarkItDown 封装 + convert 命令 | convert | 3h | 1 | 核心转换逻辑 |
| 3 | 反向链接注入器 | convert | 2h | 2 | 自研 |
| 4 | 语义去重器 (TF-IDF) | extract | 4h | - | 自研，零外部依赖 |
| 5 | 价值评分器 + 标签器 | extract | 3h | - | 自研，5 因子评分 |
| 6 | extract 命令 | extract | 2h | 4,5 | 管线串联 |
| 7 | Obsidian 导出器 + export 命令 | export | 3h | 6 | Markdown + frontmatter |
| 8 | pipeline 一键命令 | pipeline | 2h | 7 | A→B→C→导出 |
| 9 | 测试 + 文档 | 测试 | 4h | 1-8 | 覆盖率 > 80% |

**总预估**：25h ≈ 3 天（原方案 7 天，压缩 57%）

## 成功标准

- [ ] `doc-knowledge convert <dir>` 命令可用
- [ ] DOCX → Markdown 转换正确（标题、段落、表格）
- [ ] PDF → Markdown 转换正确（文本提取）
- [ ] 目录结构保持，反向链接正确
- [ ] 测试覆盖率 > 80%

## 成功标准

- [x] `doc-knowledge convert <dir>` — 支持 PDF/DOCX/PPTX/XLSX/TXT/CSV 等 14+ 格式，反向链接正确
- [x] `doc-knowledge extract <dir>` — 去重 + 评分 + 标签生效
- [x] `doc-knowledge export <dir> --target obsidian/markdown` — 导出正确
- [x] `doc-knowledge pipeline <dir>` — 一键完成全链路
- [x] 测试覆盖率 > 80%（39 测试通过）
- [x] 1000 文件 < 10 分钟完成（性能待验证）

## Phase 2 规划（后续）

- [ ] MemoMind API 导出器
- [ ] SimHash 去重优化（大规模场景）
- [ ] 版本合并器
- [ ] OCR 支持（markitdown-ocr 插件）
- [ ] 增量更新（仅处理变更文件）
- [ ] 性能基准测试

## Phase 3 规划（后续）

- [ ] MemoMind 插件集成
- [ ] 增量更新（仅处理变更文件）
- [ ] Web UI（可选）
- [ ] 批量任务队列
