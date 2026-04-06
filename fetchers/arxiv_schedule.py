"""
arxiv_schedule.py — arXiv 公告批次时间计算

arXiv 每天美东时间 20:00 发布论文（周五、周六除外），截稿时间为 14:00 ET。
本模块根据当前时间计算应抓取的公告日及其对应论文提交窗口。

公告日 → 提交窗口映射：
  周日 → 上周四 14:00 ~ 上周五 14:00
  周一 → 上周五 14:00 ~ 本周一 14:00（跨周末）
  周二 → 本周一 14:00 ~ 本周二 14:00
  周三 → 本周二 14:00 ~ 本周三 14:00
  周四 → 本周三 14:00 ~ 本周四 14:00
"""

import pytz
from datetime import date, datetime, timedelta

ET = pytz.timezone("America/New_York")

ANNOUNCE_HOUR = 20  # arXiv 每日公告时间（ET）
CUTOFF_HOUR   = 14  # arXiv 每日截稿时间（ET）

# 有效公告日的 weekday 集合（Python weekday: Mon=0 ... Sun=6）
ANNOUNCEMENT_WEEKDAYS = {6, 0, 1, 2, 3}  # Sun, Mon, Tue, Wed, Thu

# 按公告日 weekday → (start_delta, end_delta)，相对公告日的天数偏移
# 偏移应用于公告日当天日期，时刻固定为 CUTOFF_HOUR
WINDOW_DAY_DELTAS = {
    6: (-3, -2),  # Sun: Thu→Fri
    0: (-3,  0),  # Mon: Fri→Mon (跨周末)
    1: (-1,  0),  # Tue: Mon→Tue
    2: (-1,  0),  # Wed: Tue→Wed
    3: (-1,  0),  # Thu: Wed→Thu
}

# arXiv 2026 年节假日（美东时间，这些日期不发布论文）
HOLIDAYS: set[date] = {
    date(2026,  1,  1),  # New Year's Day
    date(2026,  1, 19),  # MLK Day
    date(2026,  6, 19),  # Juneteenth
    date(2026,  7,  3),  # Independence Day (observed)
    date(2026,  9,  7),  # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
    date(2026, 12, 29),  # Extra holiday
    date(2026, 12, 31),  # New Year's Eve
}


def _is_valid_announcement_day(d: date, holidays: set[date] = HOLIDAYS) -> bool:
    """判断 d 是否为有效公告日（正确的 weekday 且不在节假日名单中）。"""
    return d.weekday() in ANNOUNCEMENT_WEEKDAYS and d not in holidays


def get_effective_announcement_date(now_et: datetime, holidays: set[date] = HOLIDAYS) -> date:
    """
    返回本次运行对应的 arXiv 公告日。

    工作流在北京时间 12:00 运行（= 美东 00:00），hour < 20，
    因此永远回退到前一个有效公告日，正好对应当天北京 08:00 已发布的那批论文。
    如需在美东 20:00 之后手动触发，也能正确识别当天公告日。
    """
    today = now_et.date()
    if _is_valid_announcement_day(today, holidays) and now_et.hour >= ANNOUNCE_HOUR:
        return today

    # 向前回退，找最近的有效公告日
    d = today - timedelta(days=1)
    for _ in range(14):  # 最多回退14天，避免极端情况死循环
        if _is_valid_announcement_day(d, holidays):
            return d
        d -= timedelta(days=1)

    raise RuntimeError("无法在 14 天内找到有效公告日，请检查节假日配置")


def get_submission_window(announcement_date: date) -> tuple[datetime, datetime]:
    """根据公告日返回对应的论文提交窗口（UTC datetime 区间）。"""
    wd = announcement_date.weekday()
    if wd not in WINDOW_DAY_DELTAS:
        raise ValueError(f"日期 {announcement_date} 的 weekday={wd} 不是有效公告日")

    start_delta, end_delta = WINDOW_DAY_DELTAS[wd]

    def _et_cutoff(d: date, delta: int) -> datetime:
        target = d + timedelta(days=delta)
        naive = datetime(target.year, target.month, target.day, CUTOFF_HOUR, 0, 0)
        return ET.localize(naive).astimezone(pytz.utc)

    start_utc = _et_cutoff(announcement_date, start_delta)
    end_utc   = _et_cutoff(announcement_date, end_delta)
    return start_utc, end_utc


def normalize_requested_announcement_date(d: date, holidays: set[date] = HOLIDAYS) -> date:
    """
    将用户手动指定的日期（--date）规范化为有效公告日。
    如果指定日期不是有效公告日，向后顺延到下一个有效公告日。
    """
    for _ in range(14):
        if _is_valid_announcement_day(d, holidays):
            return d
        d += timedelta(days=1)

    raise RuntimeError(f"从 {d} 起 14 天内找不到有效公告日，请检查节假日配置")


def get_previous_announcement_date(ann_date: date, holidays: set[date] = HOLIDAYS) -> date:
    """返回指定公告日的前一个有效公告日（供补推上一批使用）。"""
    d = ann_date - timedelta(days=1)
    for _ in range(14):
        if _is_valid_announcement_day(d, holidays):
            return d
        d -= timedelta(days=1)

    raise RuntimeError("无法在 14 天内找到前一个有效公告日，请检查节假日配置")
