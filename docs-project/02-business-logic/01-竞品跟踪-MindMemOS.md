# 竞品跟踪：MindMemOS

**创建时间**：2026-07-16  
**分析来源**：[memosmind/docs-project/01-product-concept/12-竞品分析-MindMemOS.md](../../../../memomind/docs-project/01-product-concept/12-竞品分析-MindMemOS.md)  
**监控策略**：月度检查 + 触发式跟踪

---

## 项目定位

Doc-Knowledge 与 MindMemOS 属于**不同赛道**：

| 维度 | Doc-Knowledge | MindMemOS |
|------|--------------|-----------|
| 核心能力 | 文档转换 + 知识提取 + 导入 MemoMind | Agent 长期记忆系统 |
| 用户 | 个人知识工作者 | AI Agent 开发者 |
| 竞争关系 | **无直接竞争**（互补定位） | - |
| 借鉴价值 | 其 Dreaming 合并思路可参考到文档去重合并 | - |

**跟踪目的**：借鉴其技术方案，非商业竞争。

---

## 快照（2026-07-16）

| 指标 | 值 | 变化 |
|------|-----|------|
| Stars | 240 ⭐ | 基线 |
| Forks | 9 | 基线 |
| 最近 Commit | 未知（首次记录） | 基线 |
| 开源功能 | 基础设施：Qdrant + Neo4j + Kafka + FastAPI | 基线 |
| Benchmark | LoCoMo 93.64 (SOTA) / PersonaMem 69.61 (SOTA) | 基线 |

---

## 月度跟踪记录

| 日期 | Stars | Forks | 版本 | 新增功能 | 评估 |
|------|-------|-------|------|---------|------|
| 2026-07-16 | 240 | 9 | - | 基线 | 项目 3 周，增长快 |

---

## 关注点

### 优先级 🔴 高

- [ ] Dreaming 具体实现代码是否开源（当前 pipeline 中已提及但源码未确认）
- [ ] Benchmark 更新（LoCoMo / PersonaMem / MemoryAgentBench）

### 优先级 🟡 中

- [ ] Skills 系统具体实现
- [ ] Schema Learning 算法细节
- [ ] OpenClaw Plugin 更新

### 优先级 🟢 低

- [ ] 商业化进展（Cloud API 价格 / Pro 功能）
- [ ] 社区活跃度（Issue / PR 数量）
- [ ] 新的跨框架接入（Hermes / Code / OpenHands）

---

## 可借鉴方案

详见：[memosmind/docs-project/03-architecture/04-记忆系统增强设计-Dreaming与Skills闭环.md](../../../../memomind/docs-project/03-architecture/04-记忆系统增强设计-Dreaming与Skills闭环.md)

当前可借鉴的核心思路已在 MemoMind Phase 5 规划中细化，Doc-Knowledge 侧关注的是：

1. **文档去重合并**：Dreaming 的聚类 + 合并思路可应用到 doc-knowledge 的文档去重
2. **知识提纯**：从文档碎片中提取结构化知识（三元组）
