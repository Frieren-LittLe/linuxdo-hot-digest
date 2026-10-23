# -*- coding: utf-8 -*-
"""组装日报：data/analysis.md（头部+分析）+ data/hot_100.json（Hot 100 表）-> reports/YYYY-MM-DD.md"""
import json
import sys
from datetime import date
from pathlib import Path

# 仓库根目录（脚本位于 <repo>/脚本/），data/ 与 reports/ 固定落在仓库根下
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
REPORTS = REPO_ROOT / "reports"


def fmt_num(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def main():
    # 日期默认取今天，可用参数显式覆盖（用于用历史数据重跑）
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

    topics = json.loads((DATA / "hot_100.json").read_text(encoding="utf-8"))
    analysis = (DATA / "analysis.md").read_text(encoding="utf-8").rstrip() + "\n"

    lines = [
        "",
        "## 📊 今日 Hot 100 快速索引表",
        "",
        "> 说明：榜单为 `hot.json` + `top.json?period=daily` 去重合并结果；📌 为置顶旧帖（累计数据）；",
        "> 标题超长部分截断，点击直达链接查看原帖。",
        "",
        "| 排名 | 标题 | 分类 | 浏览量 | 点赞数 | 链接 |",
        "| :-- | :-- | :-- | --: | --: | :-- |",
    ]
    for i, t in enumerate(topics, 1):
        title = t["title"].replace("|", "／").replace("\n", " ")
        if len(title) > 42:
            title = title[:42] + "…"
        pinned = "📌" if not t["created_at"].startswith("2026-10") else ""
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
