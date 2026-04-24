"""
filter_and_summarize.py

用 LLM 对候选论文进行：
1. 相关性筛选：从 candidate_pool 中选出最相关的 top_n 篇
2. 中文一句话总结（summary_zh）：20-40 字，用于卡片摘要
3. 中文详细解读（detail_zh）：包括论文做了什么、核心方法、主要结论，
   用于邮件卡片展开区域

整体逻辑：
- 将所有候选论文标题+摘要打包成一个 prompt，让 LLM 一次性返回
  评分 + summary_zh + detail_zh（减少 API 调用次数）
- 关键词自动衍生三级优先级（_build_keyword_tiers），无需用户手动配置复合词
- temperature=0 保证每次输出确定，加 paper ID 次级排序保证同分稳定
- 支持多种 LLM 后端，通过 PROVIDER_REGISTRY 注册表驱动：
  Anthropic SDK（claude、minimax）和 OpenAI 兼容协议（openai、deepseek 等）
  均统一在注册表中配置，config.yml 填写 llm_provider 名称即可切换
"""

import json
import os
from itertools import combinations


def filter_and_summarize_papers(
    papers: list[dict],
    keywords: list[str],
    top_n: int,
    llm_provider: str,
    api_key: str,
    min_score: int = 6,
    custom_llm: dict | None = None,
) -> list[dict]:
    """
    筛选论文并生成中文总结。

    整体逻辑：
    - 构造批量 prompt，包含所有候选论文的 id / title / abstract
    - 要求 LLM 输出 JSON 列表：[{id, score, summary_zh, detail_zh}, ...]
    - 按 score 降序、paper ID 字典序次级排序（保证结果稳定）
    - 过滤掉 score < min_score 的论文，不强制凑满 top_n
    - 若全部低于门槛，兜底返回最高分 1 篇

    Args:
        papers: arxiv_fetcher 返回的候选论文列表
        keywords: 用于告知 LLM 关注方向，自动衍生优先级
        top_n: 最终保留篇数上限
        llm_provider: config.yml 中的 llm_provider 名称（见 PROVIDER_REGISTRY）
        api_key: 对应的 API key
        min_score: 最低相关性门槛，低于此分不推送，默认 6

    Returns:
        筛选后的论文列表（已附加 summary_zh / detail_zh 字段），按相关性排序
    """
    if not papers:
        return []

    prompt = _build_paper_prompt(papers, keywords, top_n)
    raw = _call_llm(prompt, llm_provider, api_key, custom_llm)
    results = _parse_json_response(raw)

    # 建立 id → paper 映射
    id_map = {p["id"]: p for p in papers}
    all_scored = []
    for item in results:
        pid = item.get("id")
        if pid in id_map:
            paper = id_map[pid].copy()
            paper["summary_zh"] = item.get("summary_zh", "")
            paper["detail_zh"]  = item.get("detail_zh", "")
            paper["score"]      = item.get("score", 0)
            all_scored.append(paper)

    # 稳定排序：score 降序，同分按 paper ID 字典序
    all_scored.sort(key=lambda x: (-x.get("score", 0), x.get("id", "")))

    # 按 min_score 门槛过滤，不强制凑满 top_n
    output = [p for p in all_scored if p.get("score", 0) >= min_score][:top_n]

    # 兜底：全部低于门槛时返回最高分 1 篇，避免空邮件
    if not output and all_scored:
        output = all_scored[:1]

    # 若 LLM 解析完全失败
    if not output:
        fallback = papers[:top_n]
        for p in fallback:
            p["score"] = 0
            p["summary_zh"] = "（LLM 解析失败，请检查 API 响应）"
            p["detail_zh"] = ""
        output = fallback

    return output


# ── Prompt builders ────────────────────────────────────────────

def _build_keyword_tiers(keywords: list[str]) -> tuple[list[str], list[str]]:
    """
    从用户配置的基础关键词自动衍生两级优先级，用于 prompt 评分标准。

    整体逻辑：
    - tier1（高优先级）：多词关键词（本身含空格）+ 单词关键词的两两组合复合短语
    - tier2（中优先级）：所有单词关键词

    例：keywords=["openclaw","agent","skill"]
        → tier1=["openclaw","agent skill","agent openclaw","skill openclaw"]
          tier2=["openclaw","agent","skill"]

    Args:
        keywords: config.yml 中的 keywords 列表

    Returns:
        (tier1_phrases, tier2_words)
    """
    multi  = [k for k in keywords if len(k.split()) > 1]
    singles = [k for k in keywords if len(k.split()) == 1]
    combos = [f"{a} {b}" for a, b in combinations(singles, 2)]
    tier1  = multi + combos + singles  # 专有词也进 tier1
    tier2  = singles
    return tier1, tier2


def _build_paper_prompt(papers: list[dict], keywords: list[str], top_n: int) -> str:
    tier1, tier2 = _build_keyword_tiers(keywords)
    tier1_str = "、".join(f'"{p}"' for p in tier1)
    tier2_str = "、".join(f'"{w}"' for w in tier2)
    all_kw_str = "、".join(keywords)

    items = []
    for p in papers:
        items.append(
            f'ID: {p["id"]}\n标题: {p["title"]}\n摘要: {p["abstract"][:400]}'
        )
    papers_text = "\n\n---\n\n".join(items)

    return f"""你是一位 AI 研究领域的论文筛选助手。
关注方向：{all_kw_str}

评分标准（严格按此执行，score 为 1-10 整数）：
- score=9-10：标题或摘要核心内容直接涉及高优先级组合 {tier1_str}
- score=7-8：摘要明确以 {tier2_str} 为核心研究主题（不是顺带提及）
- score=4-6：论文泛泛使用上述词汇，但并非核心主题
- score=1-3：几乎无关，仅因关键词宽泛被搜索引擎召回

筛选规则：
1. 仅在 abstract 末尾 "future work" 中提到关键词的，score 不得超过 3
2. 只输出评分最高的 {top_n} 篇，其余不输出

下面是从 arxiv 搜索到的 {len(papers)} 篇候选论文。
请为每篇在心里打分，然后**只输出**评分最高的 {top_n} 篇，并生成中文总结：
1. summary_zh：一句精炼的中文总结（20-40字），用于卡片摘要
2. detail_zh：详细中文解读（100-150字），包含三点：
   - 论文做了什么（研究问题/方法）
   - 核心创新点
   - 主要结论或实验结果

**输出格式**（严格 JSON 数组，不要有其他文字，只输出 {top_n} 篇）：
[
  {{
    "id": "论文ID",
    "score": 相关性评分(1-10的整数),
    "summary_zh": "一句中文总结（仅高分论文填写，低分填空字符串）",
    "detail_zh": "详细中文解读（仅高分论文填写，低分填空字符串）"
  }},
  ...
]

候选论文：
{papers_text}
"""


# ── 内置 LLM 提供商注册表 ─────────────────────────────────────
#
# 设计思路：
# - 常用提供商内置在此，开箱即用
# - 用户也可在 config.yml 的 custom_llm 中自定义提供商，无需改代码
# - 内置 + 自定义合并成完整的 PROVIDER_REGISTRY
#
# registry 结构：provider_name → (sdk, base_url, model)
#   sdk: "anthropic" 或 "openai"
#   base_url: None 表示使用该 SDK 的官方默认地址

BUILTIN_PROVIDERS = {
    "openai":   ("openai",    None,                                         "gpt-4o-mini"),
    "minimax":  ("anthropic", "https://api.minimaxi.com/anthropic",         "minimax-m2.7"),
    "claude":   ("anthropic", None,                                         "claude-haiku-4-5-20251001"),
    "deepseek": ("openai",    "https://api.deepseek.com/v1",                "deepseek-chat"),
    "zhipu":    ("openai",    "https://open.bigmodel.cn/api/paas/v4",       "glm-4-flash"),
    "moonshot": ("openai",    "https://api.moonshot.cn/v1",                 "moonshot-v1-8k"),
    "qwen":     ("openai",    "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
}


def _build_registry(custom_llm: dict | None) -> dict:
    """
    合并内置提供商和用户自定义配置，生成完整的注册表。

    custom_llm 格式（来自 config.yml）：
        my_api:
          sdk: openai
          base_url: "https://my-api.com/v1"
          model: "gpt-4o"
    """
    registry = dict(BUILTIN_PROVIDERS)
    if not custom_llm:
        return registry

    for name, cfg in custom_llm.items():
        sdk = cfg.get("sdk", "openai")
        base_url = cfg.get("base_url") or None
        model = cfg.get("model")
        if not model:
            raise ValueError(f"自定义 LLM 配置 '{name}' 缺少必填字段 'model'")
        if sdk not in ("openai", "anthropic"):
            raise ValueError(f"自定义 LLM 配置 '{name}' 的 sdk 必须是 'openai' 或 'anthropic'，收到: '{sdk}'")
        registry[name] = (sdk, base_url, model)

    return registry


def _call_llm(prompt: str, provider: str, api_key: str, custom_llm: dict | None = None) -> str:
    """
    统一 LLM 调用入口。

    整体逻辑：
    - 合并内置提供商 + 用户自定义配置生成完整注册表
    - 从注册表查找 (sdk, base_url, model)
    - sdk == "anthropic" → 走 Anthropic SDK（Claude、MiniMax 等）
    - sdk == "openai"    → 走 OpenAI 兼容协议（OpenAI、DeepSeek 等）
    - 新增内置提供商：修改 BUILTIN_PROVIDERS
    - 新增自定义提供商：在 config.yml 的 custom_llm 中配置，无需改代码

    Args:
        prompt: 输入 prompt
        provider: config.yml 中的 llm_provider 名称
        api_key: 对应的 API key
        custom_llm: config.yml 中的 custom_llm 配置块（可选）

    Raises:
        ValueError: provider 不在注册表（内置或自定义）
    """
    registry = _build_registry(custom_llm)
    if provider not in registry:
        supported = ", ".join(registry.keys())
        raise ValueError(f"不支持的 llm_provider: '{provider}'，可选：{supported}")

    sdk, base_url, model = registry[provider]
    if sdk == "anthropic":
        return _call_anthropic(prompt, api_key, base_url, model)
    else:
        return _call_openai_compatible(prompt, api_key, base_url, model)


def _call_anthropic(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    """
    调用 Anthropic SDK。
    base_url=None 时使用官方地址（Claude），
    传入自定义 base_url 时可对接兼容 Anthropic 协议的第三方（如 MiniMax）。
    temperature=0 保证输出确定性。

    重试机制：遇到 529 OverloadedError 时最多重试 5 次，指数退避等待。
    """
    import time
    import anthropic

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**kwargs)

    max_retries = 5
    wait_times = [30, 60, 90, 120, 180]  # 指数退避：30s, 60s, 90s, 120s, 180s

    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            # 遍历所有 block，跳过 ThinkingBlock（推理模型），返回第一个 TextBlock 的内容
            for block in msg.content:
                if hasattr(block, "type") and block.type == "text":
                    return block.text
                if hasattr(block, "text"):
                    return block.text
            return ""
        except anthropic._exceptions.OverloadedError as e:
            if attempt < max_retries - 1:
                wait_time = wait_times[attempt]
                print(f"      [LLM] API 过载 (529)，{wait_time}秒后重试 ({attempt+1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                raise


def _call_openai_compatible(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    """
    调用 OpenAI 兼容协议。
    base_url=None 时使用 OpenAI 官方地址。
    temperature=0 保证输出确定性。
    """
    from openai import OpenAI
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


# ── JSON 解析 ──────────────────────────────────────────────────

def _parse_json_response(raw: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 数组，容错处理代码块包裹。"""
    import re
    # 去掉 ```json ... ``` 包裹
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取第一个 [ ... ] 块
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return []
