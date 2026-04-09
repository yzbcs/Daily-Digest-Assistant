"""
更新 study/data.json 索引文件。

每天的 digest 跑完后调用，将当天记录追加/覆盖到索引中。

幂等操作：同一天重复跑会覆盖已有记录，不会重复追加。
"""

import json
import os
from datetime import date

STUDY_DATA_PATH = "study/data.json"


def load_data() -> dict:
    """读取现有索引，不存在则创建空结构。"""
    if os.path.exists(STUDY_DATA_PATH):
        with open(STUDY_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"notes": []}


def save_data(data: dict) -> None:
    """写入索引文件。"""
    os.makedirs(os.path.dirname(STUDY_DATA_PATH), exist_ok=True)
    with open(STUDY_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_entry(
    today: str,           # e.g. "2026-04-09"
    month: str,           # e.g. "2026/04"
    papers_count: int = 0,
    xhs_count: int = 0,
    keywords: list[str] | None = None,
) -> None:
    """
    追加/覆盖当天记录到 data.json。

    幂等：同一天已存在则覆盖，不重复追加。
    """
    data = load_data()

    today_date = date.today()
    created = today_date.isoformat()

    new_entry = {
        "id": today,
        "title": f"📬 Daily Digest · {today}",
        "path": f"daily/{month}/{today}.html",
        "created": created,
        "tags": ["Daily Digest", "arXiv", "小红书"] + (keywords or []),
    }

    # 幂等：同一天覆盖，不重复追加
    existing = data.get("notes", [])
    updated = [n for n in existing if n.get("id") != today]
    updated.insert(0, new_entry)  # 最新日期排在最前面
    data["notes"] = updated

    save_data(data)
    print(f"  [study] data.json 已更新，当前共 {len(updated)} 条记录")


if __name__ == "__main__":
    import sys
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    month = sys.argv[2] if len(sys.argv) > 2 else f"{today[:4]}/{today[5:7]}"
    papers = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    xhs = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    kws = sys.argv[5].split(",") if len(sys.argv) > 5 else []

    update_entry(today, month, papers, xhs, kws)
