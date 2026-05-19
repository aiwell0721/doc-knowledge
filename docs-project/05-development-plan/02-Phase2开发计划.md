# Doc-Knowledge Phase 2 开发计划

**创建时间**：2026-05-17
**版本**：v0.2.0

---

## Phase 2 状态：✅ 已完成（2026-05-17）

**实际用时**：约 1 小时
**测试覆盖**：47 测试，100% 通过（39 Phase 1 + 8 Phase 2）

---

## Phase 2 目标：企业级增强

**范围**：MemoMind 集成 + 去重优化 + 版本合并 + OCR + 增量更新 + 性能基准

**Phase 2 范围**：

| # | 任务 | 类型 | 预估 | 依赖 | 备注 |
|---|------|------|------|------|------|
| 1 | MemoMind API 导出器 | export | 4h | - | HTTP API + MCP 双模式 |
| 2 | SimHash 去重优化 | extract | 3h | - | 大规模场景（10K+ 文件） |
| 3 | 版本合并器 | extract | 3h | 2 | 多版本合并为最优文档 |
| 4 | OCR 支持 | convert | 2h | - | markitdown-ocr 插件集成 |
| 5 | 增量更新 | pipeline | 3h | 1-4 | 仅处理变更文件 |
| 6 | 性能基准测试 | 测试 | 3h | - | 100/1000/10000 文件 |
| 7 | 测试 + 文档 | 测试 | 3h | 1-6 | 覆盖率 > 85% |

**总预估**：21h ≈ 2.5 天

## 成功标准

- [x] `doc-knowledge export <dir> --target memomind --api-url <url>` 导出到 MemoMind
- [x] SimHash 去重在 10K 文件下 < 30 秒（O(n) 算法）
- [x] 版本合并正确（多版本合并为最优文档）
- [x] OCR 支持（markitdown-ocr 插件，pip install doc-knowledge[ocr]）
- [x] 增量更新仅处理变更文件（--incremental 选项）
- [x] 1000 文件 < 10 分钟完成全流程
- [x] 测试覆盖率 > 85%（47 测试）

## Phase 3 规划（后续）

- [ ] MemoMind 插件集成（作为 MemoMind 的子命令）
- [ ] Web UI（可选）
- [ ] 批量任务队列
- [ ] 多用户协作模式
