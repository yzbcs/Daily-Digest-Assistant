"""
main.py — arxiv-daily 主入口

整体流程：
1. 读取 config.yml 和环境变量（API Keys / 邮箱密码）
2. 计算本次对应的 arXiv 公告日 + 论文提交窗口
3. 抓取 arxiv 候选论文（按提交窗口）
4. LLM 筛选论文 + 生成中文摘要和详细解读
5. 渲染 HTML 邮件
6. SMTP 发送

用法：
  正常运行：  python3 main.py
  预览模式：  python3 main.py --dry-run   （只渲染，不发送，输出到 preview.html）
  补跑指定日：python3 main.py --dry-run --date 2026-04-03
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
    get_effective_announcement_date,
    get_submission_window,
    normalize_requested_announcement_date,
)
from llm.filter_and_summarize import filter_and_summarize_papers
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


def main(dry_run: bool = False, target_date: date | None = None):
    cfg = load_config()

    keywords       = cfg.get("keywords", [])
    categories     = cfg.get("categories", [])
    max_papers     = cfg.get("max_papers", 10)
    candidate_pool = cfg.get("candidate_pool", 50)
    min_score      = cfg.get("min_score", 6)
    smtp_provider  = cfg.get("smtp_provider", "163")
    llm_provider   = cfg.get("llm_provider", "claude")

    llm_api_key = get_env("LLM_API_KEY")
    email_user  = get_env("EMAIL_USER", required=not dry_run)
    email_pass  = get_env("EMAIL_PASS", required=not dry_run)
    email_to    = get_env("EMAIL_TO",   required=not dry_run)

    # Step 1: 抓取 arxiv 候选（按 arXiv 公告批次对应的提交窗口）
    print(f"[1/4] 搜索 arxiv 论文，关键词: {keywords}")

    # 计算公告日和对应提交窗口
    if target_date:
        ann_date = normalize_requested_announcement_date(target_date)
    else:
        now_et = datetime.now(ET)
        ann_date = get_effective_announcement_date(now_et)
    start_time, end_time = get_submission_window(ann_date)

    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    print(f"      公告日(ET): {ann_date.strftime('%m-%d')} {weekday_names[ann_date.weekday()]}")
    print(f"      提交窗口(ET): {start_time.astimezone(ET).strftime('%m-%d %H:%M')} ~ "
          f"{end_time.astimezone(ET).strftime('%m-%d %H:%M')}")

    candidates = fetch_papers(keywords, categories, candidate_pool,
                              start_time=start_time, end_time=end_time)
    print(f"      候选论文: {len(candidates)} 篇")

    # Step 2: LLM 筛选 + 生成摘要和详细解读
    print(f"[2/4] LLM 筛选论文（provider: {llm_provider}）")
    if dry_run and llm_api_key in ("dummy", "", "test"):
        papers = candidates[:max_papers]
        for p in papers:
            p["summary_zh"] = "（dry-run 模式，未调用 LLM）"
            p["detail_zh"]  = "论文做了什么：提出了一种新的方法解决当前问题。\n核心创新点：引入了全新的模型架构。\n主要结论：在多个基准上超越了现有方法。"
        print(f"      [DRY-RUN] 跳过 LLM，直接取前 {len(papers)} 篇")
    else:
        papers = filter_and_summarize_papers(candidates, keywords, max_papers, llm_provider, llm_api_key, min_score=min_score)
        print(f"      精选论文: {len(papers)} 篇")

    # Step 3: 渲染 HTML
    print(f"[3/4] 渲染 HTML 邮件")
    html = render_email(papers, keywords)

    if dry_run:
        out_path = "preview.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[DRY-RUN] 预览已保存至 {out_path}，未发送邮件")
        return

    # Step 4: 发送邮件
    print(f"[4/4] 发送邮件至 {email_to}")
    send_email(html, email_user, email_pass, email_to, smtp_provider)
    print(f"[DONE] 推送完成，共 {len(papers)} 篇")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只渲染不发送，输出 preview.html")
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

    main(dry_run=args.dry_run, target_date=target)
