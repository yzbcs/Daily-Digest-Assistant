# Semantic Scholar 匿名备用检索

## 行为

无需申请 API Key，无需新增 GitHub Secret 或安装依赖。正常运行仍先使用 arXiv；只有抓取抛出异常才自动切换 Semantic Scholar。arXiv 正常返回空列表、或主流程判断为休息日时，不触发备用检索。

arXiv 关闭 SDK 内部重试，由现有外层统一执行最多 3 轮请求，失败间隔为 10、30 秒。Semantic Scholar 使用 `https://api.semanticscholar.org/graph/v1/paper/search/bulk`，匿名请求、30 秒超时、按发布日期降序；分页间隔为 3 秒。匿名接口自身也可能限流，HTTP 错误直接交给主流程报告，不继续叠加重试。

## 数据范围

- 使用现有关键词做 OR 短语查询，候选数量上限复用 `candidate_pool`。
- 从本次 arXiv 投稿窗口取起止日期，按 Semantic Scholar 的发布日期检索，含首尾日；这不等同于精确的 arXiv 公告批次。
- Semantic Scholar 不提供现有 `cs.AI` 等 arXiv 分类过滤，备用路径不应用该过滤，页面会明确说明。
- 跳过缺少摘要或发布日期的记录。不同来源的收录及时性没有保证。
- 有 arXiv ID 时用无版本号的 arXiv ID 去重，并保留 arXiv/PDF 链接；否则使用 `S2:` 加 Semantic Scholar paperId 作为 ID。
- 同一次抓取按 ID 去重；不新增跨日去重，按日扩展后的相邻日期窗口可能重复包含论文。
- 复用现有 LLM 和渲染流程。页头标明 Semantic Scholar，链接按钮按实际链接标记；缺 PDF 时不显示 PDF 按钮。
- 两个来源都失败时生成含具体状态码的占位页面，不调用 LLM、不发邮件，也不再承诺“明日自动恢复”。

## 改动位置

- `fetchers/semantic_scholar_fetcher.py`：匿名 bulk search、分页、字段映射及去重。
- `fetchers/arxiv_fetcher.py`：缩短重试预算。
- `main.py`：异常后调用备用源，并向渲染器传递来源和日期范围。
- `render/email_renderer.py`、`templates/email.html`：显示真实来源和链接标签。
- `tests/test_paper_sources.py`：7 项行为测试。

## 2026-10-13 验证结果

执行 `/opt/homebrew/bin/python3.11 -m unittest discover -s tests -p 'test_paper_sources.py' -v`，7 项测试通过，覆盖字段映射、分页、去重、缺摘要过滤、候选数量上限、匿名接口 429 不重试、arXiv 重试预算、备用结果进入 LLM/渲染流程、主源空结果不换源及双源失败停止推送。

真实匿名请求使用远端运行中的五个关键词：`LLM Agent`、`Self-Evolving Agent`、`Coding agent`、`agent harness`、`RSI`。发布日期范围为 2026-10-09 至 2026-10-12，候选上限 80。最终得到 38 篇有摘要的候选，其中 26 篇带 arXiv 链接；返回记录的发布日期为 10 月 9 日至 10 月 10 日。这只证明本地匿名抓取和字段映射成功，不证明已完整收录目标日期范围内的全部论文。

实测候选保存于 `assets/output/semantic-scholar/papers.json`，未调用 LLM 的检索预览保存于 `assets/output/semantic-scholar/preview.html`。未发送邮件、未触发 GitHub Actions，线上验证结果将在运行后补充。

参考：[Semantic Scholar 官方 API 教程](https://webflow.semanticscholar.org/product/api/tutorial)。
