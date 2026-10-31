# -*- coding: utf-8 -*-
"""一次性工具（放在 gitignored 的 data/ 下）：用周榜把历史上某一天的候选池捞回来。

背景：linux.do 热榜是实时快照，没有历史存档。补做往期日报时（如 10-29 漏跑、
第二天才补），只能从"周榜 top.json?period=weekly"里按 created_at 反筛出落在
目标窗口内的帖子。浏览量/点赞是**当前累计值**，不是当天的快照值——这点在日报里要说明。

用法:
  python data/_fetch_weekly.py weekly            # 抓周榜 -> data/weekly_top.json
  python data/_fetch_weekly.py slice 2026-10-29  # 按窗口切片 -> data/hot_100_<day>.json
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "脚本"))
from jina_fetch import BASE, DATA, jina_get, strip_html  # noqa: E402


def fetch_weekly(pages=4):
    cat_map = {}
    cats, _ = jina_get(BASE + "/categories.json")
    if isinstance(cats, dict) and "category_list" in cats:
        for c in cats["category_list"].get("categories", []):
            cat_map[c["id"]] = c.get("name", "")
            for sub in c.get("subcategory_list", []) or []:
                cat_map[sub["id"]] = sub.get("name", "")
    print(f"[info] categories: {len(cat_map)}", flush=True)

    topics, seen = [], set()
    for p in range(pages):
        data, _ = jina_get(f"{BASE}/top.json?period=weekly&page={p}")
        if not isinstance(data, dict) or "topic_list" not in data:
            print(f"[warn] weekly page {p} bad response", flush=True)
            continue
        raw = data["topic_list"].get("topics", [])
        print(f"[info] weekly page {p} -> {len(raw)} topics", flush=True)
        for t in raw:
            if t["id"] in seen or not t.get("title"):
                continue
            seen.add(t["id"])
            topics.append({
                "id": t["id"],
                "title": t["title"].strip(),
                "url": f"{BASE}/t/{t.get('slug', 'topic')}/{t['id']}",
                "created_at": t.get("created_at", ""),
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "posts_count": t.get("posts_count", 0),
                "category": cat_map.get(t.get("category_id"), str(t.get("category_id", "?"))),
                "excerpt": strip_html(t.get("excerpt", ""))[:200],
            })
    out = DATA / "weekly_top.json"
    out.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] saved {len(topics)} -> {out}", flush=True)


def slice_day(day, also_merge_hot=True):
    """按 gen_report 的窗口定义（报告日前一日 21:00 ~ 当日 21:00，本地时区）切片。"""
    local_tz = datetime.now().astimezone().tzinfo
    end = datetime.fromisoformat(f"{day}T21:00:00").replace(tzinfo=local_tz)
    start = end - timedelta(days=1)

    # 优先用当天归档的真实快照（jina_fetch 每次抓取都会另存一份到 data/snapshots/），
    # 它比"周榜反筛"完整得多；只有没有归档时才退化到周榜重建。
    snaps = sorted((DATA / "snapshots").glob(f"hot_{day}T*.json"))
    if snaps:
        # 归档快照就是当天那次抓取的完整榜单：整表沿用、保持原始排名顺序，
        # 让 gen_report 照常规给窗口外旧帖打 📌，产出的报告与正常日报完全同构。
        picked = json.loads(snaps[-1].read_text(encoding="utf-8"))
        print(f"[info] 命中当日归档快照 {snaps[-1].name}"
              f"（{len(picked)} 条，完整热榜，按原排名输出）", flush=True)
        out = DATA / f"hot_100_{day}.json"
        out.write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[ok] -> {out}", flush=True)
        for i, t in enumerate(picked[:40], 1):
            print(f"#{i}|{t['id']}|{t['category']}|v={t['views']} like={t['like_count']}"
                  f" reply={t['posts_count']}|{t['created_at'][:16]}|{t['title'][:56]}")
        return

    # 没有归档：退化到周榜重建，此时必须按窗口过滤（周榜覆盖整整一周）
    print("[warn] 当日无归档快照，退化为周榜反筛（会漏掉当天小火、后来沉掉的帖子）", flush=True)
    pool = json.loads((DATA / "weekly_top.json").read_text(encoding="utf-8"))
    ids = {t["id"] for t in pool}
    if also_merge_hot:
        hf = DATA / "hot_100.json"
        if hf.exists():
            for t in json.loads(hf.read_text(encoding="utf-8")):
                if t["id"] not in ids:
                    ids.add(t["id"])
                    pool.append(t)

    def parse(s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    picked = [t for t in pool if (dt := parse(t["created_at"])) and start <= dt < end]
    picked.sort(key=lambda t: -(t["like_count"]))
    out = DATA / f"hot_100_{day}.json"
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] window {start} ~ {end} -> {len(picked)} topics -> {out}", flush=True)
    for i, t in enumerate(picked[:40], 1):
        print(f"#{i}|{t['id']}|{t['category']}|v={t['views']} like={t['like_count']}"
              f" reply={t['posts_count']}|{t['created_at'][:16]}|{t['title'][:56]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "weekly"
    if mode == "weekly":
        fetch_weekly()
    elif mode == "slice":
        slice_day(sys.argv[2])
