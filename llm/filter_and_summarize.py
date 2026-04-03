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
- 支持多种 LLM 后端，通过 PROVIDER_REGISTRY 注册表驱动：
  Anthropic SDK（claude、minimax）和 OpenAI 兼容协议（openai、deepseek 等）
  均统一在注册表中配置，config.yml 填写 llm_provider 名称即可切换
"""

import json
import os


def filter_and_summarize_papers(
    papers: list[dict],
    keywords: list[str],
    top_n: int,
    llm_provider: str,
    api_key: str,
) -> list[dict]:
    """
    筛选论文并生成中文总结。

    整体逻辑：
    - 构造批量 prompt，包含所有候选论文的 id / title / abstract
    - 要求 LLM 输出 JSON 列表：[{id, score, summary_zh, detail_zh}, ...]
    - 按 score 降序取 top_n，将 summary_zh / detail_zh 写回对应 paper dict

    Args:
        papers: arxiv_fetcher 返回的候选论文列表
        keywords: 用于告知 LLM 关注方向
        top_n: 最终保留篇数
        llm_provider: config.yml 中的 llm_provider 名称（见 PROVIDER_REGISTRY）
        api_key: 对应的 API key

    Returns:
        筛选后的论文列表（已附加 summary_zh / detail_zh 字段），按相关性排序
    """
    if not papers:
        return []

    prompt = _build_paper_prompt(papers, keywords, top_n)
    raw = _call_llm(prompt, llm_provider, api_key)
    results = _parse_json_response(raw)

    # 建立 id → paper 映射
    id_map = {p["id"]: p for p in papers}
    output = []
    for item in results[:top_n]:
        pid = item.get("id")
        if pid in id_map:
            paper = id_map[pid].copy()
            paper["summary_zh"] = item.get("summary_zh", "")
            paper["detail_zh"]  = item.get("detail_zh", "")
            paper["score"]      = item.get("score", 0)
            output.append(paper)

    # 按 score 降序
    output.sort(key=lambda x: x.get("score", 0), reverse=True)
    return output


# ── Prompt builders ────────────────────────────────────────────

def _build_paper_prompt(papers: list[dict], keywords: list[str], top_n: int) -> str:
    kw_str = "、".join(keywords)
    items = []
    for p in papers:
        items.append(
            f'ID: {p["id"]}\n标题: {p["title"]}\n摘要: {p["abstract"][:400]}'
        )
    papers_text = "\n\n---\n\n".join(items)

    return f"""你是一位 AI 研究领域的论文筛选助手。
关注方向：{kw_str}

下面是从 arxiv 搜索到的 {len(papers)} 篇候选论文。
请从中选出与"{kw_str}"最相关的 {top_n} 篇，并为每篇生成：
1. summary_zh：一句精炼的中文总结（20-40字），用于卡片摘要
2. detail_zh：详细中文解读（100-150字），包含三点：
   - 论文做了什么（研究问题/方法）
   - 核心创新点
   - 主要结论或实验结果

**输出格式**（严格 JSON 数组，不要有其他文字）：
[
  {{
    "id": "论文ID",
    "score": 相关性评分(1-10的整数),
    "summary_zh": "一句中文总结",
    "detail_zh": "详细中文解读..."
  }},
  ...
]

候选论文：
{papers_text}
"""


# ── LLM 提供商注册表 ───────────────────────────────────────────
#
# 设计思路：
# - OpenAI 兼容协议的提供商（绝大多数国产模型）只需在此注册 base_url + model
# - Claude 使用原生 SDK，单独处理
# - 用户在 config.yml 中填写 llm_provider 名称即可切换
# - 新增提供商：在 PROVIDER_REGISTRY 加一行，无需改任何其他代码
#
# 已支持的提供商：
#   openai    - OpenAI GPT 系列（OpenAI SDK）
#   minimax   - MiniMax（Anthropic SDK，api.minimaxi.com/anthropic，minimax-m2.7）
#   claude    - Anthropic Claude（Anthropic SDK，官方地址）
#   deepseek  - DeepSeek（OpenAI SDK）
#   zhipu     - 智谱 GLM（OpenAI SDK）
#   moonshot  - 月之暗面 Kimi（OpenAI SDK）
#   qwen      - 阿里通义千问（OpenAI SDK）
#
# registry 结构：provider_name → (sdk, base_url, model)
#   sdk: "anthropic" 或 "openai"
#   base_url: None 表示使用该 SDK 的官方默认地址

PROVIDER_REGISTRY = {
    "openai":   ("openai",    None,                                         "gpt-4o-mini"),
    "minimax":  ("anthropic", "https://api.minimaxi.com/anthropic",         "minimax-m2.7"),
    "claude":   ("anthropic", None,                                         "claude-haiku-4-5-20251001"),
    "deepseek": ("openai",    "https://api.deepseek.com/v1",                "deepseek-chat"),
    "zhipu":    ("openai",    "https://open.bigmodel.cn/api/paas/v4",       "glm-4-flash"),
    "moonshot": ("openai",    "https://api.moonshot.cn/v1",                 "moonshot-v1-8k"),
    "qwen":     ("openai",    "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
}


def _call_llm(prompt: str, provider: str, api_key: str) -> str:
    """
    统一 LLM 调用入口，由 PROVIDER_REGISTRY 驱动。

    整体逻辑：
    - 从注册表查找 (sdk, base_url, model)
    - sdk == "anthropic" → 走 Anthropic SDK（Claude、MiniMax 等）
    - sdk == "openai"    → 走 OpenAI 兼容协议（OpenAI、DeepSeek 等）
    - 新增提供商只需在 PROVIDER_REGISTRY 加一行，无需修改此函数

    Args:
        prompt: 输入 prompt
        provider: config.yml 中的 llm_provider 名称
        api_key: 对应的 API key

    Raises:
        ValueError: provider 不在注册表
    """
    if provider not in PROVIDER_REGISTRY:
        supported = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"不支持的 llm_provider: '{provider}'，可选：{supported}")

    sdk, base_url, model = PROVIDER_REGISTRY[provider]
    if sdk == "anthropic":
        return _call_anthropic(prompt, api_key, base_url, model)
    else:
        return _call_openai_compatible(prompt, api_key, base_url, model)


def _call_anthropic(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    """
    调用 Anthropic SDK。
    base_url=None 时使用官方地址（Claude），
    传入自定义 base_url 时可对接兼容 Anthropic 协议的第三方（如 MiniMax）。
    """
    import anthropic
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**kwargs)
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    # 推理模型（如 MiniMax M2.7）返回内容含 ThinkingBlock，取第一个 TextBlock
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _call_openai_compatible(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    """
    调用 OpenAI 兼容协议。
    base_url=None 时使用 OpenAI 官方地址。
    """
    from openai import OpenAI
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
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
