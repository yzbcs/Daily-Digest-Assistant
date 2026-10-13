"""Semantic Scholar 匿名检索：arXiv 请求失败时按发布日期补充候选。"""

import re
import time
from datetime import date

import requests


API_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"


def fetch_semantic_scholar_papers(
    keywords: list[str], candidate_pool: int, start_date: date, end_date: date,
) -> list[dict]:
    """日期范围含首尾日；不等同于 arXiv 投稿窗口，也不提供 arXiv 分类过滤。

    跳过无摘要记录，以免下游 LLM 仅凭标题生成解读。匿名接口限流时直接
    延迟 60 秒重试一次；仍失败则抛出 HTTPError，由主流程展示失败。
    """
    terms = [kw.strip() for kw in keywords if kw.strip()]
    if not terms or candidate_pool <= 0:
        return []
    params = {
        "query": " | ".join('"' + kw.replace('"', ' ') + '"' for kw in terms),
        "publicationDateOrYear": f"{start_date.isoformat()}:{end_date.isoformat()}",
        "sort": "publicationDate:desc",
        "fields": "title,abstract,authors,externalIds,publicationDate,url,openAccessPdf",
    }
    papers = []
    seen_ids = set()
    with requests.Session() as session:
        session.headers.update({
            "User-Agent": "Daily-Digest-Assistant/1.0 (https://github.com/yzbcs/Daily-Digest-Assistant)",
        })
        while True:
            response = session.get(API_URL, params=params, timeout=30)
            if response.status_code == 429:
                print("      [Semantic Scholar] HTTP 429，等待 60s 后重试一次", flush=True)
                time.sleep(60)
                response = session.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            for item in data["data"]:
                abstract = (item.get("abstract") or "").strip()
                published = item.get("publicationDate")
                if not abstract or not published:
                    continue
                if not start_date.isoformat() <= published <= end_date.isoformat():
                    continue
                arxiv_id = (item.get("externalIds") or {}).get("ArXiv")
                arxiv_id = re.sub(r"v\d+$", "", arxiv_id) if arxiv_id else None
                paper_id = arxiv_id or f"S2:{item['paperId']}"
                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)
                title = " ".join(item["title"].split())
                text = (title + " " + abstract).lower()
                papers.append({
                    "id": paper_id,
                    "title": title,
                    "authors": [a["name"] for a in item.get("authors", [])[:5]],
                    "abstract": " ".join(abstract.split()),
                    "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else item["url"],
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else
                               (item.get("openAccessPdf") or {}).get("url"),
                    "published": published,
                    "categories": [],
                    "matched_keywords": [kw for kw in terms if kw.lower() in text],
                    "source": "Semantic Scholar",
                    "link_label": "arXiv" if arxiv_id else "Semantic Scholar",
                })
                if len(papers) >= candidate_pool:
                    return papers
            token = data.get("token")
            if not token:
                return papers
            params["token"] = token
            time.sleep(3)
