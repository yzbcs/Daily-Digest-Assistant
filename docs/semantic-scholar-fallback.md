# Semantic Scholar 匿名备用检索

## 行为

无需申请 API Key，无需新增 GitHub Secret 或安装依赖。正常运行仍先使用 arXiv；抓取抛出异常或返回零候选时自动切换 Semantic Scholar。主流程判断为休息日时，不触发备用检索。

arXiv 关闭 SDK 内部重试，由现有外层统一执行最多 3 轮请求，失败间隔为 10、30 秒。Semantic Scholar 使用 `https://api.semanticscholar.org/graph/v1/paper/search/bulk`，匿名请求、30 秒超时、按发布日期降序；分页间隔为 3 秒。匿名接口自身也可能限流，遇到 HTTP 429 延迟 60 秒重试一次，仍失败或其他 HTTP 错误交给主流程报告。

## 数据范围

- 使用现有关键词做 OR 短语查询，候选数量上限复用 `candidate_pool`。
- 从本次 arXiv 投稿窗口取起止日期，按 Semantic Scholar 的发布日期检索，含首尾日；这不等同于精确的 arXiv 公告批次。
- Semantic Scholar 不提供现有 `cs.AI` 等 arXiv 分类过滤，备用路径不应用该过滤，页面会明确说明。
- 跳过缺少摘要或发布日期的记录。不同来源的收录及时性没有保证。
- 有 arXiv ID 时用无版本号的 arXiv ID 去重，并保留 arXiv/PDF 链接；否则使用 `S2:` 加 Semantic Scholar paperId 作为 ID。
- 同一次抓取按 ID 去重；不新增跨日去重，按日扩展后的相邻日期窗口可能重复包含论文。
- 复用现有 LLM 和渲染流程。页头标明 Semantic Scholar，链接按钮按实际链接标记；缺 PDF 时不显示 PDF 按钮。
- 两个来源都失败时生成含具体状态码的诊断页面，不调用 LLM、不发邮件，并以错误退出。Workflow 仍上传诊断产物，但停止归档和站点同步，保留已有成功页面。

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


## 2026-10-14：线上确认备用源与思考预算问题

[运行 38426331748](https://github.com/yzbcs/Daily-Digest-Assistant/actions/runs/38426331748) 使用提交 `042a3d3`：arXiv 零候选后启用 Semantic Scholar，获取 39 篇候选；GLM-5.3 论文响应 `stop_reason=end_turn`、输出 7999 tokens、文本 2779 字符，解析 10 条并匹配 10 篇，邮件发送 10 篇论文和 10 条笔记。

小红书的 71 条候选触发了确定的输出截断：`stop_reason=max_tokens`，输出 8192 tokens，`content_types=['thinking']`，文本 0 字符。因此该次笔记仍是原文兜底，而非生成摘要。下一修订仅把 GLM-5.3 的输出上限提高至 16384，其他模型仍为 8192；实际消耗以返回 usage 为准。保持 Anthropic 非流式调用，这个上限也在 SDK 默认非流式预算范围内。等待新一轮验证，不声称该预算一定能覆盖所有未来请求。

官方依据：[GLM-5.3 模型说明](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3)：强制开启思考、默认推理强度 max。


预算修订提交 `74fb46a` 的 [运行 38427525928](https://github.com/yzbcs/Daily-Digest-Assistant/actions/runs/38427525928) 遇到 arXiv 零候选、Semantic Scholar 匿名接口 HTTP 429，主流程提前停止，未进入 GLM 调用。这不能用于评价新输出预算。已据此增加一次 60 秒限流重试，第二次仍失败即报告，不申请独立 Key。


## 最终线上验证：2026-10-14 北京时间 00:09–00:15

[运行 38428057746](https://github.com/yzbcs/Daily-Digest-Assistant/actions/runs/38428057746)，代码提交 `ea9a943`，确认以下真实结果：

- arXiv 返回 0 篇后，Semantic Scholar 匿名请求返回 39 篇候选。本次未遇到 429，故仅验证了匿名抓取与零候选换源；60 秒限流重试由单元测试验证，不声称本次实际触发。
- 论文模型调用：`end_turn`，9281 输出 tokens（上限 16384），2654 个文本字符；JSON 解析 10 条、论文 ID 匹配 10 条。
- 小红书：71 条候选；评分调用 `end_turn`，8184 输出 tokens，1292 个文本字符，成功解析 10 条；多样化筛选调用 `end_turn`，5052 输出 tokens，278 个文本字符。
- 日志确认邮件发送成功，内容为 10 篇论文与 10 条笔记；三次调用均返回 thinking 与 text 块，没有出现 thinking-only 截断或解析失败兜底。
- 验证产物：本地 `assets/logs/workflow-38428057746-job.log`、`assets/output/workflow-38428057746/preview.html`。不把 API 的一次成功解释为匿名额度或未来输出预算的保证。

修复提交依次为 `042a3d3`（零候选换源与响应诊断）、`74fb46a`（GLM-5.3 输出预算 16384）、`ea9a943`（匿名 429 延迟重试一次）。相关测试现为 8 项检索流程测试、2 项 Anthropic 响应测试，均在各自改动后通过。


## 归档修订：2026-10-14

📊 现况：成功运行生成 10 篇论文，但索引中的 papers 为 0；失败重跑曾覆盖当天成功页面。站点索引下载失败时原实现会创建空索引，也可能覆盖历史记录。

🧪 修法：论文计数同时识别 arXiv 和 Semantic Scholar；以已归档 HTML 的真实数量修正 2026-10-13 索引。双源失败改为错误退出，诊断产物仍上传，但下游归档与站点同步不执行。站点历史索引无法下载时直接停止同步。

📌 验证：使用真实的成功归档页面执行 workflow 中的索引更新命令，计数必须是 10 篇论文、10 条笔记；双源失败测试要求程序抛出错误且不调用 LLM/邮件。未再次发送邮件。

💡 Insight：抓取失败的诊断页应作为运行产物保留，发布历史则保留上一次有效内容。匿名接口仍有外部限流，项目应明确失败，而不能把失败页面发布成一次成功日报。
