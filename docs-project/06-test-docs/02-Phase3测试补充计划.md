# Doc-Knowledge Phase 3 测试补充计划

**创建时间**：2026-05-17
**版本**：v0.1.0

---

## 问题识别

| 维度 | Phase 1+2 现状 | 缺口 |
|------|---------------|------|
| E2E 测试 | 4 个（仅 .txt，命令能跑） | ❌ 缺真实 DOCX/PDF 文件全流程 |
| 错误处理 | 无专门测试 | ❌ 缺损坏文件/权限错误/磁盘满 |
| 性能测试 | 无 | ❌ 缺 100+ 文件性能基准 |
| MemoMind HTTP | 无 | ❌ 仅 SQLite 直写有测试 |
| 边界条件 | 部分 | ❌ 缺系统化补充 |
| 覆盖率验证 | 没跑过 | ❌ 需 pytest-cov 验证 |

---

## 新增测试清单

### 1. E2E 全流程测试（test_e2e_full_pipeline.py）

| 测试 | 说明 |
|------|------|
| `test_e2e_docx_full_pipeline` | 真实 DOCX → convert → extract → export |
| `test_e2e_pdf_full_pipeline` | 真实 PDF → convert → extract → export |
| `test_e2e_mixed_formats` | DOCX+PDF+TXT+PPTX 混合目录 |
| `test_e2e_subdirectory_preservation` | 子目录结构保持 |
| `test_e2e_backlinks` | 反向链接正确注入 |
| `test_e2e_dedup_and_merge` | 去重+版本合并 E2E |
| `test_e2e_incremental` | 增量更新 E2E |

### 2. 错误处理测试（test_error_handling.py）

| 测试 | 说明 |
|------|------|
| `test_corrupted_docx` | 损坏的 DOCX 文件 |
| `test_corrupted_pdf` | 损坏的 PDF 文件 |
| `test_empty_directory` | 空目录 |
| `test_nonexistent_directory` | 不存在的目录 |
| `test_very_large_file` | 超大文件处理 |
| `test_special_characters_in_filename` | 文件名含特殊字符 |
| `test_read_only_output` | 输出目录只读 |
| `test_memoMind_connection_error` | MemoMind API 不可达 |

### 3. 性能测试（test_performance.py）

| 测试 | 说明 |
|------|------|
| `test_convert_100_files` | 100 文件转换性能 |
| `test_extract_1000_files` | 1000 文件去重性能 |
| `test_simhash_1000_files` | SimHash 大规模去重性能 |
| `test_pipeline_memory` | 全流程内存占用 |

### 4. MemoMind 导出测试（test_memomind_export.py）

| 测试 | 说明 |
|------|------|
| `test_memomind_http_export_success` | HTTP 导出成功（mock） |
| `test_memomind_http_export_failure` | HTTP 导出失败（mock） |
| `test_memomind_mcp_export_multiple_files` | MCP 多文件导出 |
| `test_memomind_tag_creation` | 标签自动创建 |

### 5. 边界条件测试（test_boundaries.py）

| 测试 | 说明 |
|------|------|
| `test_scorer_empty_vs_whitespace` | 空内容 vs 纯空格 |
| `test_scorer_very_long_content` | 超长内容评分 |
| `test_deduplicator_all_identical` | 全部相同的文档 |
| `test_deduplicator_all_different` | 全部不同的文档 |
| `test_tagger_max_tags_edge` | 标签数边界 |
| `test_merger_no_versions` | 无版本号的文档 |
| `test_converter_unsupported_format` | 不支持的格式 |

---

## 成功标准

- [ ] 新增 25+ 测试
- [ ] 总测试数 > 70
- [ ] pytest-cov 覆盖率 > 85%
- [ ] 所有 E2E 测试通过
- [ ] 所有错误处理测试通过
- [ ] 性能基准达标（100 文件 < 2 分钟）
