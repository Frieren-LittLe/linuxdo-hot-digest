# -*- coding: utf-8 -*-
"""筛选短名单 + 正文清洗：把噪音过滤从 AI 挪到本地脚本，压缩日报任务的 token 消耗。

用法:
  python 脚本/shortlist.py [N] [YYYY-MM-DD]     # 从 data/hot_100.json 打印前 N 条候选（默认 18）
                                                # 补做历史日报时传日期，窗口与 gen_report.py 对齐
  python 脚本/shortlist.py read <id> [<id>...]   # 输出清洗后的帖子正文供精读
"""
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
REPORTS = REPO / "日报"

# 分类权重：技术/资讯类优先，闲聊与羊毛降权
CAT_W = {
    "Develop": 3.0,
    "前沿快讯": 2.6,
    "资源荟萃": 2.4,
    "国产替代": 2.2,
    "搞七捻三": 1.0,
    "福利羊毛": 0.9,
    "运营反馈": 0.4,
}

# 标题噪音关键词（抽奖/打卡/签到类，命中则大幅降权而非硬删，防误伤）
NOISE_KW = re.compile(
    r"抽奖|红包|打卡|新人报到|生日|徽章|每日一题|leetcode|已结束|\[已无\]|满了|停止注册|邀请码"
)


def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def featured_ids():
    """扫描历史日报的精选标题行，返回已深度解读过的帖子 id 集合。"""
    ids = set()
    if not REPORTS.exists():
        return ids
    pat = re.compile(r"^###\s*\d+\.\s*\[.*?\]\(https?://linux\.do/t/topic/(\d+)", re.M)
    for f in sorted(REPORTS.glob("*.md")):
        ids.update(int(x) for x in pat.findall(f.read_text(encoding="utf-8")))
    return ids


def window_start_for(day=None):
    """返回统计窗口起点（本地时区 前一日 21:00）。

    day 为 None 时按"当前"推算（日常 21:00 跑的口径）；
    补做历史日报时显式传日报日期字符串 YYYY-MM-DD，与 gen_report.py 的参数对齐。
    """
    local_tz = datetime.now().astimezone().tzinfo
    if day:
        return datetime.fromisoformat(f"{day}T21:00:00").replace(tzinfo=local_tz) - timedelta(days=1)
    return (
        datetime.now(tz=local_tz).replace(hour=21, minute=0, second=0, microsecond=0)
        - timedelta(days=1)
    )


def shortlist(n=18, day=None):
    topics = json.loads((DATA / "hot_100.json").read_text(encoding="utf-8"))
    window_start = window_start_for(day)
    done = featured_ids()

    cands = []
    n_old = n_noise = n_done = 0
    for t in topics:
        dt = parse_dt(t["created_at"])
        if dt and dt < window_start:
            n_old += 1
            continue  # 窗口外旧帖：只进索引表，不进精选
        if t["id"] in done:
            n_done += 1
            continue  # 往期已深度解读
        title = t["title"]
        noise = bool(NOISE_KW.search(title))
        views, likes = t["views"], t["like_count"]
        ratio = (likes / views) if views else 0
        w = CAT_W.get(t["category"], 1.0)
        score = w * math.log1p(likes) * (1 + 30 * ratio)
        if noise:
            score *= 0.15
            n_noise += 1
        cands.append((score, noise, t))
    cands.sort(key=lambda x: -x[0])

    print(
        f"[shortlist] 总数 {len(topics)} | 窗口外旧帖 {n_old} | 往期已解读 {n_done} | "
        f"疑似水帖(降权未删) {n_noise} | 候选 {len(cands)}，取前 {min(n, len(cands))}"
    )
    for i, (score, noise, t) in enumerate(cands[:n], 1):
        flag = "⚠水" if noise else ""
        ratio = (t["like_count"] / t["views"] * 100) if t["views"] else 0
        print(
            f"#{i}|{t['id']}|{t['category']}|s={score:.1f}{flag}"
            f"|v={t['views']} like={t['like_count']}({ratio:.1f}%)"
            f"|{t['title'][:52]}|{t['excerpt'][:60]}"
        )


# ---- 正文清洗 ----
BOILER = re.compile(
    r"本帖使用社区(?:开源|公益)推广[，,].*?以上选择我承诺是永久有效的[^\n]*", re.S
)
IMG_PLACEHOLDER = re.compile(r"image\s+\d+×\d+\s+[\d.]+\s*[KM]B|\[image\]|image\s+\d+×\d+")
BARE_SITE = re.compile(r"^\s*(github\.com|gitlab\.com|codeberg\.org)\s*$", re.M)


def clean_text(s, limit=5000):
    s = BOILER.sub("[推广申明略]", s)
    s = IMG_PLACEHOLDER.sub("", s)
    s = BARE_SITE.sub("", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    s = "\n".join(line.strip() for line in s.splitlines())
    s = s.strip()
    if len(s) > limit:
        s = s[:limit] + "\n…[已截断]"
    return s


def read_topics(ids):
    for tid in ids:
        f = DATA / f"topic_{tid}.json"
        if not f.exists():
            print(f"[warn] {f} 不存在，先运行 jina_fetch.py topic {tid}")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        print(f"===== [{d['id']}] {d['title']}")
        print(f"URL: https://linux.do/t/topic/{d['id']} | v={d['views']} like={d['like_count']} reply={d['posts_count']} | 作者 {d['author']}")
        print("--- 主帖正文（已清洗）---")
        print(clean_text(d["main_text"]))
        if d.get("top_replies"):
            print("--- 高赞回复 ---")
            for r in d["top_replies"][:3]:
                print(f"@{r['author']}: {clean_text(r['text'], 300)}")
        print()


def main():
    # 参数兼容两种用法：<read <id>...> 与 <[N] [YYYY-MM-DD]>
    if len(sys.argv) >= 2 and sys.argv[1] == "read":
        read_topics([int(x) for x in sys.argv[2:] if x.isdigit()])
        return
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    n = int(nums[0]) if nums else 18
    days = [a for a in sys.argv[1:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", a)]
    shortlist(n, days[0] if days else None)


if __name__ == "__main__":
    main()
