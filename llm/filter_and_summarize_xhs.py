"""
小红书笔记 LLM 筛选与总结。
复用 filter_and_summarize.py 的 _call_llm / _parse_json_response / _build_keyword_tiers，
仅改写 prompt 和评分逻辑。
"""

import json

from llm.filter_and_summarize import _call_llm, _parse_json_response, _build_keyword_tiers


def _diversify_with_llm(notes: list[dict], llm_provider: str, api_key: str) -> list[dict]:
    """
    话题多样化筛选：让 LLM 从候选笔记中挑选覆盖不同话题的子集，
    避免多篇内容高度重复的笔记同时出现。
    """
    if len(notes) <= 1:
        return notes

    items = []
    for n in notes:
        items.append(
            f'ID: {n["id"]}\n标题: {n["title"]}\n评分: {n.get("score", 0)}\n总结: {n.get("summary_zh", "")}'
        )
    notes_text = "\n\n---\n\n".join(items)

    prompt = f"""你是一位内容策展编辑，负责从候选笔记中挑选出一个多样化的推送列表。

要求：
1. 从下面 {len(notes)} 篇候选笔记中，选出组成最终推送的子集
2. 优先选择**话题不同**的笔记，同一话题的多篇只保留评分最高的 1 篇
3. "同一话题"指围绕同一个产品、项目、功能、事件展开（如多篇都是讲 OpenClaw 4.5 更新的，只留 1 篇；讲 Agent 项目分享的只留 1 篇）
4. 在满足话题多样化的前提下，尽量保留评分高的笔记
5. 最终输出不超过 {len(notes)} 篇的 ID 列表

**输出格式**（严格 JSON，只输出 id 列表，不要其他文字）：
{{
  "kept_ids": ["id1", "id2", ...]
}}

候选笔记：
{notes_text}
"""
    raw = _call_llm(prompt, llm_provider, api_key)

    # 解析 JSON
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        kept_ids = set(result.get("kept_ids", []))
    except (json.JSONDecodeError, Exception):
        # 解析失败，降级返回原列表
        return notes

    if not kept_ids:
        return notes

    id_to_note = {n["id"]: n for n in notes}
    selected = [id_to_note[iid] for iid in kept_ids if iid in id_to_note]
    # 保持原分数降序排列
    selected.sort(key=lambda x: -x.get("score", 0))
    return selected


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
    - 过滤掉 score < min_score 的笔记
    - 再次调用 LLM 做话题多样化筛选，同一话题只保留评分最高的 1 篇
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
    # 话题去重：交给 LLM 判断，保留话题多样化的高分笔记
    output = _diversify_with_llm(output, llm_provider, api_key)

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
