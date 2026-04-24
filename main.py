"""
main.py — arxiv-daily 主入口

整体流程：
1. 读取 config.yml 和环境变量（API Keys / 邮箱密码）
2. 计算本次对应的 arXiv 公告日 + 论文提交窗口
3. 抓取 arxiv 候选论文（按提交窗口）
4. LLM 筛选论文 + 生成中文摘要和详细解读
5. [可选] 抓取小红书候选笔记，LLM 筛选 + 生成一句话总结
6. 渲染两列 HTML 邮件
7. SMTP 发送

用法：
  正常运行：  python3 main.py
  预览模式：  python3 main.py --dry-run   （只渲染，不发送，输出到 preview.html）
  补跑指定日：python3 main.py --dry-run --date 2026-04-03
  熵筛选模式：python3 main.py --entropy-only   （熵筛选 + LLM 生成摘要）
"""

import argparse
import os
import sys
import yaml
from datetime import datetime, date

import pytz

from fetchers.arxiv_fetcher import fetch_papers
from fetchers.arxiv_schedule import (
    ET,
    _is_valid_announcement_day,
    get_effective_announcement_date,
    get_submission_window,
    normalize_requested_announcement_date,
)
from fetchers.xhs_fetcher import fetch_xhs_notes
from llm.filter_and_summarize import filter_and_summarize_papers
from llm.filter_and_summarize_xhs import filter_and_summarize_xhs
from llm.entropy_scorer import entropy_filter_papers
from render.email_renderer import render_email
from sender.smtp_sender import send_email


def load_config(path: str = "config.yml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env(key: str, required: bool = True) -> str:
    val = os.environ.get(key, "").strip()
    if required and not val:
        print(f"[ERROR] 环境变量 {key} 未设置", file=sys.stderr)
        sys.exit(1)
    return val


def main(dry_run: bool = False, target_date: date | None = None, entropy_only: bool = False):
    cfg = load_config()

    keywords       = cfg.get("keywords", [])
    categories     = cfg.get("categories", [])
    max_papers     = cfg.get("max_papers", 10)
    candidate_pool = cfg.get("candidate_pool", 50)
    min_score      = cfg.get("min_score", 6)
    smtp_provider  = cfg.get("smtp_provider", "163")
    llm_provider   = cfg.get("llm_provider", "claude")
    custom_llm     = cfg.get("custom_llm") or {}
    xhs_keywords   = cfg.get("xhs_keywords") or keywords
    xhs_pool       = cfg.get("xhs_candidate_pool", 30)

    llm_api_key = get_env("LLM_API_KEY")
    email_user  = get_env("EMAIL_USER", required=not dry_run)
    email_pass  = get_env("EMAIL_PASS", required=not dry_run)
    email_to    = get_env("EMAIL_TO",   required=not dry_run)
    xhs_cookie  = get_env("XHS_COOKIE", required=False)

    # Step 1: 判断今天是否有 arXiv 公告，并抓取候选
    arxiv_rest = False
    papers = []
    candidates = []

    if target_date:
        if _is_valid_announcement_day(target_date):
            ann_date = target_date
        else:
            arxiv_rest = True
            ann_date = None
    else:
        now_et = datetime.now(ET)
        today_et = now_et.date()
        # 总是获取有效的公告日（自动回退到前一个有效日）
        ann_date = get_effective_announcement_date(now_et)
        # 今天不是公告日（周五=4，周六=5）且已经过了 20:00 ET → 标记休息
        # 注意：周五 00:05 ET = 北京时间 12:05，此时周四公告才过了 4 小时，应该继续抓
        # 所以只在"公告已过期"时标记休息：即周六、周日
        if today_et.weekday() in {5, 6}:  # Sat, Sun
            arxiv_rest = True

    if not arxiv_rest:
        WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        print(f"[1/5] 搜索 arxiv 论文，关键词: {keywords}")
        print(f"      公告日(ET): {ann_date.strftime('%m-%d')} {WEEKDAY_NAMES[ann_date.weekday()]}")
        start_time, end_time = get_submission_window(ann_date)
        print(f"      提交窗口(ET): {start_time.astimezone(ET).strftime('%m-%d %H:%M')} ~ "
              f"{end_time.astimezone(ET).strftime('%m-%d %H:%M')}")
        candidates = fetch_papers(keywords, categories, candidate_pool,
                                  start_time=start_time, end_time=end_time)
        print(f"      候选论文: {len(candidates)} 篇")
    else:
        print(f"[1/5] arXiv 今日无公告（休息日），跳过论文抓取")

    # Step 2: 筛选
    if candidates:
        if entropy_only:
            print(f"[2/5] 熵筛选论文 + LLM 生成摘要（provider: {llm_provider}）")
            if dry_run and llm_api_key in ("dummy", "", "test"):
                papers = entropy_filter_papers(candidates, keywords, max_papers)
                for p in papers:
                    p["summary_zh"] = "（dry-run 模式，未调用 LLM）"
                    p["detail_zh"]  = "论文做了什么：提出了一种新的方法解决当前问题。\n核心创新点：引入了全新的模型架构。\n主要结论：在多个基准上超越了现有方法。"
                print(f"      [DRY-RUN] 跳过 LLM，直接取前 {len(papers)} 篇")
            else:
                papers = entropy_filter_papers(candidates, keywords, max_papers,
                                               llm_provider=llm_provider, api_key=llm_api_key, custom_llm=custom_llm)
                print(f"      精选论文: {len(papers)} 篇")
        else:
            print(f"[2/5] LLM 筛选论文（provider: {llm_provider}）")
            if dry_run and llm_api_key in ("dummy", "", "test"):
                papers = candidates[:max_papers]
                for p in papers:
                    p["summary_zh"] = "（dry-run 模式，未调用 LLM）"
                    p["detail_zh"]  = "论文做了什么：提出了一种新的方法解决当前问题。\n核心创新点：引入了全新的模型架构。\n主要结论：在多个基准上超越了现有方法。"
                print(f"      [DRY-RUN] 跳过 LLM，直接取前 {len(papers)} 篇")
            else:
                papers = filter_and_summarize_papers(candidates, keywords, max_papers, llm_provider, llm_api_key, min_score=min_score, custom_llm=custom_llm)
                print(f"      精选论文: {len(papers)} 篇")
    else:
        print(f"[2/5] 无候选论文，跳过筛选")

    # Step 3: 小红书抓取 + 筛选
    print(f"[3/5] 抓取小红书笔记")
    xhs_notes = []
    if target_date:
        print(f"      [SKIP] 回跑模式，小红书无法按历史日期筛选，跳过")
    elif xhs_cookie:
        xhs_candidates = fetch_xhs_notes(xhs_keywords, xhs_pool, xhs_cookie)
        print(f"      候选笔记: {len(xhs_candidates)} 条")
        if xhs_candidates:
            if dry_run and llm_api_key in ("dummy", "", "test"):
                xhs_notes = xhs_candidates[:max_papers]
                for n in xhs_notes:
                    n["summary_zh"] = "（dry-run 模式，未调用 LLM）"
                    n["score"] = 0
                print(f"      [DRY-RUN] 跳过 LLM，直接取前 {len(xhs_notes)} 条")
            else:
                xhs_notes = filter_and_summarize_xhs(xhs_candidates, xhs_keywords, max_papers, llm_provider, llm_api_key, min_score=min_score, custom_llm=custom_llm)
                print(f"      精选笔记: {len(xhs_notes)} 条")
    else:
        print(f"      [SKIP] XHS_COOKIE 未设置，跳过小红书抓取")

    # Step 4: 渲染 HTML
    print(f"[4/5] 渲染 HTML 邮件")
    html = render_email(papers, keywords, xhs_notes=xhs_notes, arxiv_rest=arxiv_rest,
                        display_date=target_date)

    with open("preview.html", "w", encoding="utf-8") as f:
        f.write(html)

    if dry_run:
        print(f"[DRY-RUN] 预览已保存至 preview.html，未发送邮件")
        return

    # Step 5: 发送邮件
    print(f"[5/5] 发送邮件至 {email_to}")
    send_email(html, email_user, email_pass, email_to, smtp_provider)
    print(f"[DONE] 推送完成，共 {len(papers)} 篇论文 + {len(xhs_notes)} 条笔记")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只渲染不发送，输出 preview.html")
    parser.add_argument("--entropy-only", action="store_true", help="熵筛选 + LLM 生成摘要，不用 LLM 做相关性评分")
    parser.add_argument("--date", type=str, default=None,
                        help="手动指定公告日（YYYY-MM-DD），用于补跑历史批次")
    args = parser.parse_args()

    target = None
    if args.date:
        try:
            target = date.fromisoformat(args.date)
        except ValueError:
            print(f"[ERROR] --date 格式错误，应为 YYYY-MM-DD，收到: {args.date}", file=sys.stderr)
            sys.exit(1)

    main(dry_run=args.dry_run, target_date=target, entropy_only=args.entropy_only)
