# Semantic Scholar 匿名备用检索

## 行为

无需申请 API Key，无需新增 GitHub Secret 或安装依赖。正常运行仍先使用 arXiv；抓取抛出异常或返回零候选时自动切换 Semantic Scholar。主流程判断为休息日时，不触发备用检索。

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


## 线上运行记录

检索改动已通过提交 `7cd87a6a9f554e60cf43844bf244925fa6fed9df` 推送至 main，并在该提交上触发 [workflow 38424653097](https://github.com/yzbcs/Daily-Digest-Assistant/actions/runs/38424653097)。两个 jobs 均完成，归档及站点同步步骤成功；日报日志报告邮件发送成功，内容为 0 篇论文和 10 条小红书笔记。

arXiv 第一次返回 HTTP 429，第二次返回 HTTP 503，第三轮返回 0 篇候选，没有向主流程抛异常。因此按当前设计未触发 Semantic Scholar，不能声称匿名备用源已在线上跑通。0 篇是窗口过滤后的候选数量，现有日志不足以区分检索原始返回为空和全部被窗口过滤。

小红书检索返回 70 条候选，但 LLM JSON 解析完全失败，最终使用原始笔记内容兜底选出 10 条。这次运行没有验证 GLM 正常生成摘要。未自动扩大备用源触发条件，也未重复运行以免重复发送邮件。


## 零候选与 GLM 响应诊断修订

根据上述线上结果，arXiv 零候选也会启用备用源。Anthropic 响应合并全部 text 块，日志记录模型、stop_reason、输出 token 数、块类型及文本长度，不记录 thinking 内容；论文筛选同时记录解析结果数和匹配论文数。Workflow 使用无缓冲输出，保留各阶段真实日志时间。GLM 空响应的具体原因仍待新一轮线上日志确认。
