"""
entropy_scorer.py — SLTF-Entropy 熵评分筛选 + LLM 摘要生成

原理（参考 techrxiv 论文）：
  Score(d,q) = (1/E_d) × Σ_{t∈q∩d} log(1 + TF_title(t,d)×2 + TF_abstract(t,d)×1)

  E_d：文档 d 中所有 term 的 Shannon 熵
  熵越高 → term 分布越均匀 → 区分度越强 → 论文质量越高
  log(1+TF)：压缩高频 term，防止一个词出现多次就压制其他词

特点：
  - 熵归一化，对文档长度鲁棒
  - 标题命中双倍权重
  - 适合精准关键词匹配场景

用法：
  python3 main.py --entropy-only
"""

import json
import math
import re
from itertools import combinations
from typing import Dict, List, Tuple


def _tokenize(text: str) -> List[str]:
    """小写化 + 分词（按非字母数字边界）。"""
    return [tok.lower() for tok in re.findall(r"[a-z0-9]+", text.lower())]


def _build_tf(text: str) -> Dict[str, int]:
    """统计 text 中每个 term 的频次（TF）。"""
    tokens = _tokenize(text)
    tf = {}
    for tok in tokens:
        tf[tok] = tf.get(tok, 0) + 1
    return tf


def _compute_shannon_entropy(tf: Dict[str, int]) -> float:
    """
    计算文档的 Shannon 熵。

    E_d = -Σ p_i log2(p_i)，其中 p_i = TF(t_i) / Σ TF(t_j)

    熵越高说明 term 分布越均匀，区分度越强。
    """
    total = sum(tf.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in tf.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def _score_single_paper(
    title: str,
    abstract: str,
    keyword_weights: Dict[str, float],
) -> float:
    """
    对单篇论文计算 SLTF-Entropy 分数。

    公式：Score = (1/E_d) × Σ_{t∈q∩d} log(1 + TF_title(t)×2 + TF_abstract(t)×1)

    Args:
        title: 论文标题
        abstract: 论文摘要
        keyword_weights: 关键词 → 权重映射

    Returns:
        SLTF-Entropy 分数（越高越相关）
    """
    # 合并 title + abstract 计算熵和 TF
    combined_text = title + " " + abstract
    tf_combined = _build_tf(combined_text)

    entropy = _compute_shannon_entropy(tf_combined)
    if entropy == 0:
        return 0.0

    # 标题和摘要分别统计 TF
    tf_title = _build_tf(title)
    tf_abstract = _build_tf(abstract)

    sltf = 0.0
    for kw, weight in keyword_weights.items():
        kw_tokens = _tokenize(kw)

        if len(kw_tokens) > 1:
            # 多词短语：按整体在 title / abstract 中计数
            title_count = title.lower().count(kw.lower())
            abstract_count = abstract.lower().count(kw.lower())
            combined_count = title_count + abstract_count
        else:
            # 单词关键词：直接用 TF
            tok = kw_tokens[0]
            title_count = tf_title.get(tok, 0)
            abstract_count = tf_abstract.get(tok, 0)
            combined_count = title_count + abstract_count

        if combined_count > 0:
            # log(1 + 标题TF×2 + 摘要TF×1) × 关键词权重
            sltf += weight * math.log(1 + title_count * 2 + abstract_count * 1)

    return (sltf / entropy) if entropy > 0 else 0.0


def score_papers_by_sltf_entropy(
    papers: list,
    keyword_weights: Dict[str, float],
    top_k: int = 10,
) -> List[Tuple[dict, float]]:
    """
    从候选论文中用 SLTF-Entropy 评分，返回 top_k 篇最相关的。

    Args:
        papers: 论文列表，每篇含 title / abstract
        keyword_weights: 关键词 → 权重映射
        top_k: 返回数量

    Returns:
        [(paper, sltf_score), ...]，按分数降序
    """
    scored = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")

        score = _score_single_paper(title, abstract, keyword_weights)

        # 额外加分：arxiv 热度分数
        score += paper.get("score", 0) * 0.1

        scored.append((paper, round(score, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _build_keyword_tiers(keywords: list) -> Tuple[List[str], List[str]]:
    """从关键词自动衍生两级优先级（供 LLM prompt 使用）。"""
    multi  = [k for k in keywords if len(k.split()) > 1]
    singles = [k for k in keywords if len(k.split()) == 1]
    combos = [f"{a} {b}" for a, b in combinations(singles, 2)]
    tier1 = multi + combos + singles
    tier2 = singles
    return tier1, tier2


def _build_entropy_paper_prompt(papers: list, keywords: list) -> str:
    """
    为熵筛选后的论文构造摘要生成 prompt。
    只让 LLM 生成 summary_zh，不做相关性评分（熵分已排序）。
    """
    tier1, _ = _build_keyword_tiers(keywords)
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


def _generate_summaries_with_llm(
    papers: list,
    keywords: list,
    llm_provider: str,
    api_key: str,
    custom_llm: dict | None = None,
) -> dict:
    """
    调用 LLM 为论文列表生成 summary_zh 和 detail_zh。
    返回 {id: {summary_zh, detail_zh}} 映射。
    """
    from llm.filter_and_summarize import _call_llm

    prompt = _build_entropy_paper_prompt(papers, keywords)
    raw = _call_llm(prompt, llm_provider, api_key, custom_llm)

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

    return {
        r.get("id"): {
            "summary_zh": r.get("summary_zh", ""),
            "detail_zh": r.get("detail_zh", ""),
        }
        for r in results
    }


def entropy_filter_papers(
    papers: list,
    keywords: list,
    top_n: int,
    llm_provider: str = None,
    api_key: str = None,
    custom_llm: dict | None = None,
) -> list:
    """
    入口函数：用 SLTF-Entropy 筛选出 top_n 篇最相关的论文，并调用 LLM 生成摘要。

    公式：Score = (1/E_d) × Σ_{t∈q∩d} log(1 + TF_title(t)×2 + TF_abstract(t)×1)

    关键词权重：
    - 多词短语（空格分隔）：权重 × 1.5
    - 单词关键词：权重 × 1.0

    初筛条件：至少命中一个关键词（标题或摘要中）

    Args:
        papers: arxiv_fetcher 返回的候选论文列表
        keywords: config.yml 中的关键词列表
        top_n: 最终保留篇数
        llm_provider: LLM 提供商名称
        api_key: API key
        custom_llm: config.yml 中的自定义 LLM 配置（可选）

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

    # SLTF-Entropy 评分排序
    results = score_papers_by_sltf_entropy(candidates, keyword_weights, top_k=top_n)

    # 附加熵分数到论文
    output = []
    for paper, sltf_score in results:
        p = paper.copy()
        p["entropy_score"] = sltf_score
        output.append(p)

    # 调用 LLM 生成摘要
    if llm_provider and api_key and api_key not in ("dummy", "", "test"):
        summary_map = _generate_summaries_with_llm(output, keywords, llm_provider, api_key, custom_llm)
        for p in output:
            if p["id"] in summary_map:
                p["summary_zh"] = summary_map[p["id"]]["summary_zh"]
                p["detail_zh"] = summary_map[p["id"]]["detail_zh"]

    return output
