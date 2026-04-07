"""
小红书笔记 LLM 筛选与总结。
复用 filter_and_summarize.py 的 _call_llm / _parse_json_response / _build_keyword_tiers，
仅改写 prompt 和评分逻辑。
"""

import json
import re

from llm.filter_and_summarize import _call_llm, _parse_json_response, _build_keyword_tiers

# 标题停用词，去除这些词再比对关键词重叠率
_STOPWORDS = {"的", "了", "是", "在", "和", "与", "或", "之", "这", "那", "个", "一", "上", "下", "中", "来", "去", "着", "过", "到", "把", "被", "用", "对", "为", "有", "就", "也", "都", "吗", "呢", "吧", "啊", "哦", "嗯", "我", "你", "他", "她", "它", "们", "什", "怎么", "如何", "为什么"}


def _title_keywords(title: str) -> set[str]:
    """提取标题中的有效关键词（去停用词、标点、数字）。"""
    words = re.findall(r'[\w]+', title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _deduplicate_by_topic(notes: list[dict]) -> list[dict]:
    """
    基于标题关键词重叠率去重，重叠率超过 0.5 的只保留分数最高的。
    保持原顺序（已按分数降序排列）。
    """
    if len(notes) <= 1:
        return notes
    result = []
    for note in notes:
        kept = True
        n_keywords = _title_keywords(note.get("title", ""))
        for kept_note in result:
            k_keywords = _title_keywords(kept_note.get("title", ""))
            if _jaccard(n_keywords, k_keywords) > 0.5:
                kept = False
                break
        if kept:
            result.append(note)
    return result


def filter_and_summarize_xhs(
    notes: list[dict],
    keywords: list[str],
    top_n: int,
    llm_provider: str,
    api_key: str,
    min_score: int = 6,
) -> list[dict]:
    """
    筛选小红书笔记并生成中文总结。

    整体逻辑：
    - 构造批量 prompt，包含所有候选笔记的 id / title / content（前300字）
    - 要求 LLM 输出 JSON 列表：[{id, score, summary_zh}, ...]
    - 按 score 降序、id 次级排序（保证结果稳定）
    - 过滤掉 score < min_score 的笔记，不强制凑满 top_n
    - 若全部低于门槛，兜底返回最高分 1 篇

    Args:
        notes: xhs_fetcher.fetch_xhs_notes() 返回的候选笔记列表
        keywords: 用于告知 LLM 关注方向
        top_n: 最终保留篇数上限
        llm_provider: config.yml 中的 llm_provider 名称
        api_key: 对应的 API key
        min_score: 最低相关性门槛，默认 6

    Returns:
        筛选后的笔记列表（已附加 summary_zh / score 字段），按相关性排序
    """
    if not notes:
        return []

    prompt = _build_xhs_prompt(notes, keywords, top_n)
    raw = _call_llm(prompt, llm_provider, api_key)
    results = _parse_json_response(raw)

    id_map = {n["id"]: n for n in notes}
    all_scored = []
    for item in results:
        nid = item.get("id")
        if nid in id_map:
            note = id_map[nid].copy()
            note["summary_zh"] = item.get("summary_zh", "")
            note["score"]      = item.get("score", 0)
            all_scored.append(note)

    all_scored.sort(key=lambda x: (-x.get("score", 0), x.get("id", "")))

    output = [n for n in all_scored if n.get("score", 0) >= min_score][:top_n]
    # 话题去重：标题关键词重叠率超过 50% 的只保留分数最高的
    output = _deduplicate_by_topic(output)

    if not output and all_scored:
        output = all_scored[:1]

    if not output:
        fallback = notes[:top_n]
        for n in fallback:
            n["score"] = 0
            n["summary_zh"] = "（LLM 解析失败，请检查 API 响应）"
        output = fallback

    return output


def _build_xhs_prompt(notes: list[dict], keywords: list[str], top_n: int) -> str:
    tier1, tier2 = _build_keyword_tiers(keywords)
    tier1_str = "、".join(f'"{p}"' for p in tier1)
    tier2_str = "、".join(f'"{w}"' for w in tier2)
    all_kw_str = "、".join(keywords)

    items = []
    for n in notes:
        content_preview = (n.get("content") or "")[:300]
        items.append(
            f'ID: {n["id"]}\n标题: {n["title"]}\n正文: {content_preview}'
        )
    notes_text = "\n\n---\n\n".join(items)

    return f"""你是一位信息筛选助手，负责从小红书笔记中挑选与指定主题高度相关的内容。
关注方向：{all_kw_str}

评分标准（严格按此执行，score 为 1-10 整数）：
- score=9-10：笔记核心内容直接涉及高优先级组合 {tier1_str}（如详细实践、产品评测、工具对比）
- score=7-8：笔记明确以 {tier2_str} 为核心话题（不是顺带提及）
- score=4-6：笔记泛泛涉及上述关键词，但核心话题是其他内容
- score=1-3：几乎无关，仅因关键词宽泛被召回

筛选规则：
1. 只输出评分最高的 {top_n} 篇，其余不输出
2. 优先选取有实质内容的笔记（有经验分享、操作步骤、对比分析），避免纯广告或无内容图片笔记

下面是从小红书搜索到的 {len(notes)} 条候选笔记。
请为每条在心里打分，然后**只输出**评分最高的 {top_n} 条，并生成一句话总结：
- summary_zh：20-40字的中文总结，概括笔记的核心内容或观点

**输出格式**（严格 JSON 数组，不要有其他文字，只输出 {top_n} 条）：
[
  {{
    "id": "笔记ID",
    "score": 相关性评分(1-10的整数),
    "summary_zh": "一句话中文总结"
  }},
  ...
]

候选笔记：
{notes_text}
"""
