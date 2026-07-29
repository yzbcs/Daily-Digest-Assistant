"""
arxiv_fetcher.py — arXiv 论文搜索

按关键词 + 分类构造查询，在指定时间窗口内搜索论文并返回候选列表。
时间窗口由 arxiv_schedule.py 计算（按 arXiv 官方公告批次对齐）。
"""

import time
import arxiv
from datetime import datetime, timezone, timedelta


def fetch_papers(keywords: list[str], categories: list[str], candidate_pool: int,
                 start_time=None, end_time=None) -> list[dict]:
    """
    搜索 arXiv 论文并返回候选列表。

    构造 OR 关键词查询，叠加分类过滤，只保留 [start_time, end_time] 内发表的论文。
    结果按提交时间降序，遇到超出下界即停止迭代。

    Returns:
        list of dict，每项含 id / title / authors / abstract / url / pdf_url /
        published / categories / matched_keywords
    """
    kw_query = " OR ".join(f'(ti:"{kw}" OR abs:"{kw}")' for kw in keywords)

    if categories:
        cat_query = " OR ".join(f"cat:{c}" for c in categories)
        query = f"({kw_query}) AND ({cat_query})"
    else:
        query = kw_query

    if end_time is None:
        end_time = datetime.now(timezone.utc)
    if start_time is None:
        start_time = end_time - timedelta(hours=24)

    client = arxiv.Client(num_retries=5, delay_seconds=10)
    search = arxiv.Search(
        query=query,
        max_results=candidate_pool * 2,  # 多取一些，过滤后仍能满足数量
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    # arXiv API 临时性错误重试（429 限流 / 500/502/503 服务不可用）：最多 5 次，间隔递增
    max_attempts = 5
    wait_times = [30, 60, 120, 180, 300]

    for attempt in range(max_attempts):
        try:
            papers = []
            seen_ids = set()

            for result in client.results(search):
                pub_time = result.published
                if pub_time.tzinfo is None:
                    pub_time = pub_time.replace(tzinfo=timezone.utc)
                if pub_time < start_time:
                    break
                if pub_time > end_time:
                    continue

                paper_id = result.entry_id.split("/abs/")[-1]
                paper_id = paper_id.split("v")[0]

                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                text = (result.title + " " + result.summary).lower()
                matched = [kw for kw in keywords if kw.lower() in text]

                papers.append({
                    "id": paper_id,
                    "title": _clean_latex(result.title),
                    "authors": [a.name for a in result.authors[:5]],
                    "abstract": result.summary.replace("\n", " ").strip(),
                    "url": result.entry_id,
                    "pdf_url": result.pdf_url,
                    "published": result.published.strftime("%Y-%m-%d"),
                    "categories": list(result.categories) if hasattr(result, "categories") else [],
                    "matched_keywords": matched,
                })

                if len(papers) >= candidate_pool:
                    break

            return papers

        except arxiv.HTTPError as e:
            # 429 限流、500/502/503 服务端不可用 均为临时性错误，指数退避重试。
            # 注意：原来只重试 429，遇到 503 会直接 raise，拖垮整个推送（main.py 无 try/except）。
            if e.status in (429, 500, 502, 503) and attempt < max_attempts - 1:
                wait = wait_times[attempt]
                print(f"[arxiv] HTTP {e.status}，等待 {wait}s 后重试（{attempt + 1}/{max_attempts}）...")
                time.sleep(wait)
            else:
                raise

    return []


def _clean_latex(text: str) -> str:
    """清除标题中的 LaTeX 语法，保留可读文字。"""
    import re
    text = re.sub(r'\$([^$]+)\$', lambda m: m.group(1), text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text