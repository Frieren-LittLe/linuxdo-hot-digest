# -*- coding: utf-8 -*-
"""抓取 Linux.do (Discourse) 每日热门 Top 100 帖子元数据，输出精简 JSON 供分析。

直连会被 Cloudflare 按 TLS 指纹拦截（403），故使用 curl_cffi 模拟 Chrome 指纹，
并走本机系统代理。
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from curl_cffi import requests

BASE = "https://linux.do"
HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://linux.do/",
}


def detect_proxies():
    """代理配置：LINUXDO_PROXY 环境变量优先，其次系统代理，均无则 None（直连）。"""
    p = (
        os.environ.get("LINUXDO_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
    )
    if p:
        return {"http": p, "https": p}
    ps = urllib.request.getproxies()
    if ps.get("http") or ps.get("https"):
        return {
            "http": ps.get("http") or ps.get("https"),
            "https": ps.get("https") or ps.get("http"),
        }
    return None


PROXIES = detect_proxies()


def get_json(path, retries=3):
    url = BASE + path
    for i in range(retries):
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                impersonate="chrome",
                proxies={"http": PROXY, "https": PROXY},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()
            print(f"[warn] {url} -> HTTP {r.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"[warn] {url} attempt {i+1} error: {e}", file=sys.stderr)
        time.sleep(2 * (i + 1))
    return None


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_topic(t, cat_map):
    excerpt = strip_html(t.get("excerpt", ""))[:200]
    return {
        "id": t["id"],
        "title": t.get("title", "").strip(),
        "url": f"{BASE}/t/{t.get('slug', 'topic')}/{t['id']}",
        "created_at": t.get("created_at", ""),
        "views": t.get("views", 0),
        "like_count": t.get("like_count", 0),
        "posts_count": t.get("posts_count", 0),
        "category": cat_map.get(t.get("category_id"), str(t.get("category_id", "?"))),
        "excerpt": excerpt,
    }


def main():
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)

    # 分类映射
    cat_map = {}
    cats = get_json("/categories.json")
    if cats:
        for c in cats.get("category_list", {}).get("categories", []):
            cat_map[c["id"]] = c.get("name", "")
            for sub in c.get("subcategory_list", []) or []:
                cat_map[sub["id"]] = sub.get("name", "")

    # hot 列表 + daily top 分页，去重凑满 100 条
    topics, seen = [], set()
    sources = ["/hot.json"] + [f"/top.json?period=daily&page={p}" for p in range(0, 5)]
    for path in sources:
        if len(topics) >= 100:
            break
        data = get_json(path)
        if not data:
            continue
        raw = data.get("topic_list", {}).get("topics", [])
        print(f"[info] {path} -> {len(raw)} topics", file=sys.stderr)
        for t in raw:
            if t["id"] in seen or len(topics) >= 100:
                continue
            if not t.get("title"):
                continue
            seen.add(t["id"])
            topics.append(clean_topic(t, cat_map))
        time.sleep(1)

    if not topics:
        print("[error] 未抓取到任何帖子", file=sys.stderr)
        sys.exit(1)

    out = out_dir / "hot_100.json"
    out.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] saved {len(topics)} topics -> {out}", file=sys.stderr)

    # 紧凑摘要供模型分析（控制 token）
    for i, t in enumerate(topics, 1):
        print(f"#{i}|{t['id']}|{t['title'][:60]}|cat={t['category']}|v={t['views']}|like={t['like_count']}|reply={t['posts_count']}|{t['excerpt'][:80]}")


if __name__ == "__main__":
    main()
