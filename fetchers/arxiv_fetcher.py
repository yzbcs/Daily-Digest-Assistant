"""
arxiv_fetcher.py

调用 arxiv 官方 Python SDK，按关键词 + 分类搜索最近论文。

整体逻辑：
1. 对 config 中每个 keyword 分别构造 query，合并去重
2. 按 submittedDate 降序排列，取 candidate_pool 条
3. 过滤掉发布时间超过 48 小时的论文（只推近两天）
4. 过滤掉 sent_ids 中已推过的论文（跨天去重）
5. 返回标准化的 paper dict 列表
"""

import arxiv
import json
import os
from datetime import datetime, timezone, timedelta


def fetch_papers(keywords: list[str], categories: list[str], candidate_pool: int, sent_ids: set, hours: int = 48) -> list[dict]:
    """
    搜索 arxiv 论文并返回候选列表。

    整体逻辑：
    - 构造 OR 关键词查询（在 title/abstract 中命中任一关键词）
    - 可选叠加 category 过滤
    - 过滤发布时间超过 hours 小时的论文（只推近两天内）
    - 过滤已推送 ID，返回去重后的候选论文

    Args:
        keywords: 关键词列表，e.g. ["agent", "skill"]
        categories: arxiv 分类列表，e.g. ["cs.AI", "cs.LG"]，空则不过滤
        candidate_pool: 最多返回多少篇候选
        sent_ids: 已推送的 arxiv ID 集合（用于跨天去重）
        hours: 只保留多少小时内发布的论文，默认 48（两天内）

    Returns:
        list of dict，每个 dict 包含:
            id, title, authors, abstract, url, pdf_url,
            published, categories, matched_keywords
    """
    # 构造关键词查询：title 或 abstract 中命中任一词
    kw_query = " OR ".join(
        f'(ti:"{kw}" OR abs:"{kw}")' for kw in keywords
    )

    # 叠加分类过滤
    if categories:
        cat_query = " OR ".join(f"cat:{c}" for c in categories)
        query = f"({kw_query}) AND ({cat_query})"
    else:
        query = kw_query

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    client = arxiv.Client(num_retries=3, delay_seconds=3)
    search = arxiv.Search(
        query=query,
        max_results=candidate_pool * 2,  # 多取一些，过滤后仍能满足数量
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    seen_ids = set()

    for result in client.results(search):
        # 只保留 48 小时内的论文
        pub_time = result.published
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=timezone.utc)
        if pub_time < cutoff:
            break  # 结果按时间降序，后面的更旧，直接停止

        paper_id = result.entry_id.split("/abs/")[-1]
        paper_id = paper_id.split("v")[0]

        if paper_id in sent_ids or paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        # 判断命中哪些关键词
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


def load_sent_ids(path: str = "data/sent_ids.json") -> set:
    """加载已推送的论文 ID 集合。"""
    if os.path.exists(path):
        with open(path, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(ids: list[str], path: str = "data/sent_ids.json"):
    """
    追加新推送的 ID 并保存，只保留最近 500 条防止文件膨胀。
    """
    existing = load_sent_ids(path)
    merged = list(existing | set(ids))
    merged = merged[-500:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f)


def _clean_latex(text: str) -> str:
    """
    清除论文标题中的 LaTeX 语法，保留可读文字。
    例如：$\texttt{YC-Bench}$ → YC-Bench
         \textbf{AgentBench}  → AgentBench
    """
    import re
    # 去掉 $...$ 包裹，保留内部文字
    text = re.sub(r'\$([^$]+)\$', lambda m: m.group(1), text)
    # 去掉 \cmd{...} 命令，保留花括号内容
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    # 去掉剩余孤立反斜杠命令（如 \times、\to）
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # 清理多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    return text
