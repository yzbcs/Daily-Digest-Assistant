"""
entropy_scorer.py — 基于关键词权重的熵评分筛选 + LLM 摘要生成

原理：
1. 初筛：必须包含至少一个核心关键词（避免大海捞针）
2. 打分排序：TF-IDF 风格加权，标题命中权重 > 摘要权重
3. 调用 LLM 生成 summary_zh 和 detail_zh

特点：
- 适合精准关键词匹配场景
- 关键词支持权重配置
- LLM 只负责生成摘要，不做相关性评分（熵分已排序）

用法：
  python3 main.py --entropy-only
"""

import json
import re
from itertools import combinations
from typing import List


def _tokenize(text: str) -> List[str]:
    """小写化 + 分词（按非字母数字边界）。"""
    return [tok.lower() for tok in re.findall(r"[a-z0-9]+", text.lower())]


def _phrase_match(text: str, phrase: str) -> int:
    """返回 phrase 在 text 中出现的次数（整体匹配）。"""
    return text.lower().count(phrase.lower())


def _build_keyword_tiers(keywords: list):
    """从关键词自动衍生两级优先级。"""
    multi  = [k for k in keywords if len(k.split()) > 1]
    singles = [k for k in keywords if len(k.split()) == 1]
    combos = [f"{a} {b}" for a, b in combinations(singles, 2)]
    tier1 = multi + combos + singles
    tier2 = singles
    return tier1, tier2


def score_papers_by_keywords(papers: list, keyword_weights: dict, top_k: int = 10) -> List:
    """
    从候选论文中打分排序，返回 top_k 篇最相关的。

    评分规则：
    - 标题中匹配：权重 × 2.0
    - 摘要中匹配：权重 × 1.0
    - 短语整体匹配优先于分词匹配

    Returns:
        [(paper, score), ...]，按 score 降序
    """
    scored = []

    for paper in papers:
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()

        score = 0.0

        for kw, weight in keyword_weights.items():
            # 短语整体匹配（优先）
            title_phrase_count = _phrase_match(title, kw)
            abstract_phrase_count = _phrase_match(abstract, kw)

            if title_phrase_count > 0 or abstract_phrase_count > 0:
                score += weight * (title_phrase_count * 2.0 + abstract_phrase_count * 1.0)
            else:
                # 分词匹配（备用）
                kw_tokens = _tokenize(kw)
                title_tokens = _tokenize(title)
                abstract_tokens = _tokenize(abstract)

                for tok in kw_tokens:
                    title_tok_count = title_tokens.count(tok)
                    abstract_tok_count = abstract_tokens.count(tok)
                    score += weight * (title_tok_count * 2.0 + abstract_tok_count * 1.0)

        # 额外加分：arxiv 热度分数
        score += paper.get("score", 0) * 0.1

        scored.append((paper, round(score, 2)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _build_entropy_paper_prompt(papers: list, keywords: list) -> str:
    """
    为熵筛选后的论文构造摘要生成 prompt。
    只让 LLM 生成 summary_zh，不做相关性评分（熵分已排序）。
    """
    tier1, tier2 = _build_keyword_tiers(keywords)
    tier1_str = "、".join(f'"{p}"' for p in tier1)
    all_kw_str = "、".join(keywords)

    items = []
    for p in papers:
        items.append(
            f'ID: {p["id"]}\n标题: {p["title"]}\n摘要: {p["abstract"][:400]}'
        )
    papers_text = "\n\n---\n\n".join(items)

    return f"""你是一位 AI 研究领域的论文摘要助手。
关注方向：{all_kw_str}

请严格按以下标准为每篇论文生成中文摘要：

摘要要求：
- summary_zh：一句精炼的中文总结（20-40字），用于卡片摘要
- detail_zh：详细中文解读（100-150字），包含三点：
  - 论文做了什么（研究问题/方法）
  - 核心创新点
  - 主要结论或实验结果

评分参考（与熵分对应，仅参考）：
- 熵分高：标题或摘要核心内容直接涉及 {tier1_str}

输出格式（严格 JSON 数组，不要有其他文字）：
[
  {{
    "id": "论文ID",
    "summary_zh": "一句中文总结",
    "detail_zh": "详细中文解读"
  }},
  ...
]

候选论文：
{papers_text}
"""


def _generate_summaries_with_llm(papers: list, keywords: list, llm_provider: str, api_key: str) -> dict:
    """
    调用 LLM 为论文列表生成 summary_zh 和 detail_zh。
    返回 {id: {summary_zh, detail_zh}} 映射。
    """
    from llm.filter_and_summarize import _call_llm

    prompt = _build_entropy_paper_prompt(papers, keywords)
    raw = _call_llm(prompt, llm_provider, api_key)

    # 解析 JSON
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                results = json.loads(match.group())
            except Exception:
                return {}
        return {}

    return {r.get("id"): {"summary_zh": r.get("summary_zh", ""), "detail_zh": r.get("detail_zh", "")} for r in results}


def entropy_filter_papers(
    papers: list,
    keywords: list,
    top_n: int,
    llm_provider: str = None,
    api_key: str = None,
) -> list:
    """
    入口函数：从候选论文中用熵评分筛选出 top_n 篇，并调用 LLM 生成摘要。

    关键词权重规则：
    - 多词短语（空格分隔）：权重 × 1.5
    - 单个单词：权重 × 1.0

    初筛条件：至少命中一个关键词（标题或摘要中）

    Args:
        papers: arxiv_fetcher 返回的候选论文列表
        keywords: config.yml 中的关键词列表
        top_n: 最终保留篇数
        llm_provider: LLM 提供商（entropy_filter_papers 内部调用）
        api_key: API key

    Returns:
        筛选后的论文列表（已附加 entropy_score / summary_zh / detail_zh），按熵分降序
    """
    if not papers:
        return []

    # 构建关键词权重
    keyword_weights = {}
    for kw in keywords:
        tokens = kw.strip().split()
        keyword_weights[kw] = 1.5 if len(tokens) > 1 else 1.0

    # 初筛：必须包含至少一个关键词
    core_keywords = list(keyword_weights.keys())
    candidates = [
        p for p in papers
        if any(
            kw.lower() in (p.get("title", "") + " " + p.get("abstract", "")).lower()
            for kw in core_keywords
        )
    ]

    if not candidates:
        return []

    # 打分排序
    results = score_papers_by_keywords(candidates, keyword_weights, top_k=top_n)

    # 附加熵分数到论文
    output = []
    for paper, entropy_score in results:
        p = paper.copy()
        p["entropy_score"] = entropy_score
        output.append(p)

    # 调用 LLM 生成摘要（熵分已排序，不做相关性评分）
    if llm_provider and api_key and api_key not in ("dummy", "", "test"):
        summary_map = _generate_summaries_with_llm(output, keywords, llm_provider, api_key)
        for p in output:
            if p["id"] in summary_map:
                p["summary_zh"] = summary_map[p["id"]]["summary_zh"]
                p["detail_zh"] = summary_map[p["id"]]["detail_zh"]

    return output
