# exp3_openclaw-github 实验推进历程

> 本实验为开源项目仓库完善与迭代实验，目标是通过参考高 star 开源项目的最佳实践，持续提升本仓库的专业度、功能性和社区影响力。

---

## 实验推进历程

### Round 1 — 高 star 仓库对标分析与 TODO 制定

**设计动机**

仓库目前功能已基本可用（每日 arXiv + 小红书推送），但距离高质量开源项目仍有较大差距。通过参考 TrendRadar（54.9k⭐）等高 star 仓库，系统梳理差距，制定可执行的改进路线图。

**具体方案与关键参数**

- 参考仓库：[sansan0/TrendRadar](https://github.com/sansan0/TrendRadar)（54.9k stars，AI 舆情监控与热点推送工具）
- 分析维度：项目呈现、工程化架构、功能扩展、用户体验、社区运营、安全稳定性
- 输出产物：`docs/todo.md`（47 项改进清单，分 5 个优先级）

**结果数据**

产出文件：
- `docs/todo.md` — 47 项改进清单，按 P0-P5 优先级分组
- `docs/README.md` — 本实验文档（即此文件）
- `docs/todo_visual.html` — 可视化 TODO 看板（交互式 HTML）

**核心发现**

1. **项目门面差距最大**：无 LICENSE、无 Badge、无更新日志，这些是 5 分钟就能补完但影响第一印象的关键项。
2. **推送渠道单一**：仅支持 SMTP 邮件，而 TrendRadar 支持 9+ 渠道（飞书/钉钉/企业微信/Telegram/Slack/ntfy/Bark/邮件/Webhook）。
3. **无数据持久化**：没有 SQLite 或任何数据库，去重仅靠内存判断，无法支持历史检索和趋势分析。
4. **工程化程度低**：无 pyproject.toml、无 Docker、无测试、无 setup 脚本，非技术用户上手门槛高。
5. **AI 能力浅层**：只做简单摘要，没有做跨论文关联分析、趋势洞察、情感倾向等深度分析。

**推导出的下一步洞察**

- 先做 P0（基础设施）+ Quick Wins，低成本高回报，能立即提升仓库专业度。
- 第一个 Major Feature 建议选择「多推送渠道」或「SQLite 数据持久化」，这两项能直接扩大用户群体。
- 需定期（如每季度）重新对标高 star 仓库，保持迭代方向不落后。

---

## 未来计划

1. **近期（1-2 周）**：完成 P0 基础设施 + Quick Wins（LICENSE、Badge、CHANGELOG、pyproject.toml、日志替换、演示截图）
2. **中期（1-2 月）**：实现第一个 Major Feature（多推送渠道 或 SQLite 存储）
3. **长期（3-6 月）**：AI 趋势分析、可视化配置编辑器、Web 服务器、社区运营体系

---

## 产出文件索引

| 文件 | 说明 |
|------|------|
| `docs/todo.md` | 详细的 47 项改进清单 |
| `docs/todo_visual.html` | 可视化交互式 TODO 看板 |
| `docs/README.md` | 本实验推进历程文档 |

