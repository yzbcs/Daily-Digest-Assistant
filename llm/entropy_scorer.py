"""
entropy_scorer.py — 基于关键词权重的熵评分筛选

原理：
1. 初筛：必须包含至少一个核心关键词（避免大海捞针）
2. 打分排序：TF-IDF 风格加权，标题命中权重 > 摘要权重
3. 返回 top_k 篇最相关的论文

特点：
- 不依赖 LLM，计算速度快
- 适合精准关键词匹配场景
- 关键词支持权重配置

用法：
  python3 main.py --entropy-only
"""

import re
from typing import List


def _tokenize(text: str) -> List[str]:
    """小写化 + 分词（按非字母数字边界）。"""
    return [tok.lower() for tok in re.findall(r"[a-z0-9]+", text.lower())]


def _phrase_match(text: str, phrase: str) -> int:
    """返回 phrase 在 text 中出现的次数（整体匹配）。"""
    return text.lower().count(phrase.lower())


def score_papers_by_keywords(
    papers: list,
    keyword_weights: dict,
    top_k: int = 10,
) -> List:
    """
    从候选论文中打分排序，返回 top_k 篇最相关的。

    评分规则：
    - 标题中匹配：权重 × 2.0
    - 摘要中匹配：权重 × 1.0
    - 短语整体匹配优先于分词匹配

    Args:
        papers: 论文列表，每篇含 title / abstract
        keyword_weights: 关键词 → 权重映射，如 {'entropy': 3.0, 'LRM': 2.5}
        top_k: 返回数量

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


def entropy_filter_papers(papers: list, keywords: list, top_n: int) -> list:
    """
    入口函数：从候选论文中用熵评分筛选出 top_n 篇。

    关键词权重规则：
    - 多词短语（空格分隔）：权重 × 1.5
    - 单个单词：权重 × 1.0
    - 核心关键词（短且通用）：权重 × 0.8

    初筛条件：至少命中一个关键词（标题或摘要中）

    Args:
        papers: arxiv_fetcher 返回的候选论文列表
        keywords: config.yml 中的关键词列表
        top_n: 最终保留篇数

    Returns:
        筛选后的论文列表（已附加 entropy_score 字段），按熵分降序
    """
    if not papers:
        return []

    # 构建关键词权重
    keyword_weights = {}
    for kw in keywords:
        tokens = kw.strip().split()
        if len(tokens) > 1:
            # 多词短语，权重更高
            keyword_weights[kw] = 1.5
        else:
            # 单词关键词
            keyword_weights[kw] = 1.0

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

    return output
