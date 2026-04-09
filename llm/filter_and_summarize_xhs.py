"""
小红书笔记 LLM 筛选与总结。
复用 filter_and_summarize.py 的 _call_llm / _parse_json_response / _build_keyword_tiers，
仅改写 prompt 和评分逻辑。
"""

import json
import re

from llm.filter_and_summarize import _call_llm, _parse_json_response, _build_keyword_tiers


def _diversify_with_llm(
    notes: list[dict],
    top_n: int,
    llm_provider: str,
    api_key: str,
    fallback_pool: list[dict] | None = None,
) -> list[dict]:
    """
    话题多样化筛选：让 LLM 从候选笔记中挑选 top_n 篇覆盖不同话题的子集，
    避免多篇内容高度重复的笔记同时出现。

    Args:
        notes: 当前候选池（通常是 above_threshold[:top_n * 2]）
        top_n: 目标推送篇数
        llm_provider: LLM 服务商
        api_key: API key
        fallback_pool: 当 LLM 挑完后篇数不足时，从这里递补（排除已选 + 已丢弃的）

    Returns:
        最终推送的笔记列表（恰好 top_n 篇，或 fallback_pool 耗尽时的最大可能篇数）
    """
    if len(notes) <= 1:
        return notes

    items = []
    for n in notes:
        items.append(
            f'ID: {n["id"]}\n标题：{n["title"]}\n评分：{n.get("score", 0)}\n总结：{n.get("summary_zh", "")}'
        )
    notes_text = "\n\n---\n\n".join(items)

    prompt = f"""你是一位内容策展编辑，负责从候选笔记中挑选出一个多样化的推送列表。

要求：
1. 从下面 {len(notes)} 篇候选笔记中，选出 {top_n} 篇组成最终推送
2. 优先选择**话题不同**的笔记，同一话题的多篇只保留评分最高的 1 篇
3. "同一话题"指围绕同一个产品、项目、功能、事件展开（如多篇都是讲 OpenClaw 4.5 更新的，只留 1 篇；讲 Agent 项目分享的只留 1 篇）
4. 在满足话题多样化的前提下，尽量保留评分高的笔记
5. 最终输出恰好 {top_n} 篇（如果去重后不够 {top_n} 篇，则输出所有非重复的）

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

    # 如果 LLM 返回不够 top_n 篇，从 fallback_pool 递补（排除已选 + 已丢弃的）
    if len(selected) < top_n and fallback_pool:
        selected_ids = {n["id"] for n in selected}
        discarded_ids = {n["id"] for n in notes} - selected_ids  # 被 LLM 判定为重复而丢弃的
        for note in fallback_pool:
            if note["id"] not in selected_ids and note["id"] not in discarded_ids:
                selected.append(note)
                selected_ids.add(note["id"])
            if len(selected) >= top_n:
                break

    return selected[:top_n]


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
    - 构造批量 prompt，包含所有候选笔记的 id / title / content（前 300 字）
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
    try:
        raw = _call_llm(prompt, llm_provider, api_key)
    except Exception as e:
        print(f"      [XHS-LLM] API 调用异常: {e}")
        raw = ""

    results = _parse_json_response(raw)

    # 如果标准解析失败，尝试逐行提取 JSON 对象（兼容 LLM 输出非标准格式）
    if not results and raw:
        print(f"      [XHS-LLM] 标准 JSON 解析失败，尝试逐对象提取...")
        results = _extract_json_objects(raw)

    if results:
        print(f"      [XHS-LLM] 成功解析 {len(results)} 条评分结果")
    else:
        print(f"      [XHS-LLM] JSON 解析完全失败，将使用原始笔记内容作为兜底")
        if raw:
            print(f"      [XHS-LLM] 原始响应前 500 字: {raw[:500]}")

    id_map = {n["id"]: n for n in notes}
    # 同时建立 标题→笔记 的映射，用于 ID 匹配失败时的回退匹配
    title_map = {}
    for n in notes:
        t = (n.get("title") or "").strip()
        if t and t not in title_map:
            title_map[t] = n

    all_scored = []
    matched_count = 0
    for item in results:
        nid = item.get("id")
        note = None
        if nid in id_map:
            note = id_map[nid].copy()
        else:
            # ID 匹配失败，尝试用标题回退匹配
            title_key = (item.get("title") or "").strip()
            if title_key in title_map:
                note = title_map[title_key].copy()
            else:
                print(f"      [XHS-LLM] ID 未匹配: LLM返回 id='{nid}'，不在候选池中")
                continue

        if note:
            note["summary_zh"] = item.get("summary_zh", "")
            note["score"]      = item.get("score", 0)
            all_scored.append(note)
            matched_count += 1

    if results and matched_count == 0:
        print(f"      [XHS-LLM] ⚠ 全部 ID 匹配失败！LLM 返回的 ID 示例: {[r.get('id') for r in results[:3]]}")
        print(f"      [XHS-LLM]   候选池 ID 示例: {[n['id'] for n in notes[:3]]}")
    elif matched_count < len(results):
        print(f"      [XHS-LLM] 匹配 {matched_count}/{len(results)} 条（部分 ID 不在候选池中）")

    all_scored.sort(key=lambda x: (-x.get("score", 0), x.get("id", "")))

    above_threshold = [n for n in all_scored if n.get("score", 0) >= min_score]
    # 话题去重：给 LLM 更多候选（2 倍 top_n），让它挑出 top_n 篇不同话题的
    candidates_for_dedup = (above_threshold if len(above_threshold) >= top_n * 2 else all_scored)[:top_n * 2]
    # fallback_pool: 从 all_scored 剩余候选中递补（排除已入选的，不受 min_score 限制）
    selected_ids_in_dedup = set(candidates_for_dedup[:top_n * 2])
    fallback_pool = [n for n in all_scored if n["id"] not in selected_ids_in_dedup]
    output = _diversify_with_llm(candidates_for_dedup, top_n, llm_provider, api_key, fallback_pool)

    if not output and all_scored:
        output = all_scored[:1]

    # 最终回填：确保恰好返回 top_n 篇（排除已选 + 已丢弃的）
    if len(output) < top_n:
        selected_ids = {n["id"] for n in output}
        # 已丢弃的：进入过 candidates_for_dedup 但未被选中的
        dedup_ids = {n["id"] for n in candidates_for_dedup}
        discarded_ids = dedup_ids - selected_ids
        for note in notes:
            if note["id"] not in selected_ids and note["id"] not in discarded_ids:
                output.append(note)
                selected_ids.add(note["id"])
            if len(output) >= top_n:
                break

    # 兜底：LLM 解析完全失败时，用笔记原始标题/内容生成摘要
    if not output:
        fallback = notes[:top_n]
        for n in fallback:
            n["score"] = 0
            n["summary_zh"] = _generate_fallback_summary(n)
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
            f'ID: {n["id"]}\n标题：{n["title"]}\n正文：{content_preview}'
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
- summary_zh：20-40 字的中文总结，概括笔记的核心内容或观点

**输出格式**（严格 JSON 数组，不要有其他文字，只输出 {top_n} 条）：
[
  {{
    "id": "笔记 ID",
    "score": 相关性评分 (1-10 的整数),
    "summary_zh": "一句话中文总结"
  }},
  ...
]

候选笔记：
{notes_text}
"""


def _extract_json_objects(raw: str) -> list[dict]:
    """
    从 LLM 原始响应中逐个提取 JSON 对象，容错处理非标准输出。

    整体逻辑：
    - 先尝试用正则找所有 {...} 块并逐个解析
    - 只保留包含 "id" 字段的有效对象
    - 适用于 LLM 没有输出标准 JSON 数组，而是混杂了文字说明的情况
    """
    results = []
    for m in re.finditer(r'\{[^{}]*\}', raw):
        try:
            obj = json.loads(m.group())
            if "id" in obj:
                results.append(obj)
        except json.JSONDecodeError:
            continue
    return results


def _generate_fallback_summary(note: dict) -> str:
    """
    LLM 完全失败时，从笔记原始标题/内容截取生成兜底摘要，
    避免在邮件中显示"LLM 解析失败"这种用户不友好的信息。
    """
    title = (note.get("title") or "").strip()
    content = (note.get("content") or "").strip()
    if title:
        return title[:40]
    if content:
        return content[:40]
    return "小红书笔记"
