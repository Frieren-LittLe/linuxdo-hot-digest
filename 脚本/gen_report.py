# -*- coding: utf-8 -*-
"""组装日报：data/analysis.md（头部+分析）+ data/hot_100.json（Hot 100 表）-> 日报/YYYY-MM-DD.md"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# 仓库根目录（脚本位于 <repo>/脚本/），data/ 与 日报/ 固定落在仓库根下
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
REPORTS = REPO_ROOT / "日报"


def fmt_num(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def parse_dt(s):
    """解析 Discourse ISO 时间（如 2026-10-23T08:37:40.754Z），失败返回 None。"""
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def main():
    # 日期默认取今天，可用参数显式覆盖（用于用历史数据重跑）
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    # 统计窗口：报告日前一日 21:00 至报告日 21:00（滚动 24 小时）
    # 报告日 00:00 往前拨 3 小时即窗口起点
    window_start = datetime.fromisoformat(today) - timedelta(hours=3)

    topics = json.loads((DATA / "hot_100.json").read_text(encoding="utf-8"))
    analysis = (DATA / "analysis.md").read_text(encoding="utf-8").rstrip() + "\n"

    lines = [
        "",
        "## 📊 今日 Hot 100 快速索引表",
        "",
        "> 说明：统计窗口为滚动 24 小时（前一日 21:00 ~ 报告日 21:00）；榜单为 `hot.json` + `top.json?period=daily` 去重合并；",
        "> 📌 为创建于窗口之前的旧帖（浏览/点赞为累计值）；标题超长部分截断，点击直达链接查看原帖。",
        "",
        "| 排名 | 标题 | 分类 | 浏览量 | 点赞数 | 链接 |",
        "| :-- | :-- | :-- | --: | --: | :-- |",
    ]
    for i, t in enumerate(topics, 1):
        title = t["title"].replace("|", "／").replace("\n", " ")
        if len(title) > 42:
            title = title[:42] + "…"
        dt = parse_dt(t["created_at"])
        pinned = "📌" if dt and dt < window_start else ""
        lines.append(
            f"| {i} | {pinned}{title} | {t['category']} | {fmt_num(t['views'])} "
            f"| {fmt_num(t['like_count'])} | [直达]({t['url']}) |"
        )

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{today}.md"
    out.write_text(analysis + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"[ok] report -> {out} ({len(topics)} rows)")


if __name__ == "__main__":
    main()
