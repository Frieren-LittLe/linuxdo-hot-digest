# -*- coding: utf-8 -*-
"""通过 r.jina.ai 阅读服务抓取 linux.do Discourse JSON（绕过 Cloudflare 对本机
IP 的拦截）。输出与 browser_fetch.py 相同结构的精简数据。

用法:
  python jina_fetch.py hot       # -> data/hot_100.json
  python jina_fetch.py topic <id> [<id>...]  # -> data/topic_<id>.json
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
# 仓库根目录（脚本位于 <repo>/脚本/），data/ 与 reports/ 固定落在仓库根下
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"


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


def jina_get(url, retries=4):
    """经 r.jina.ai 抓取目标 URL，返回 (json_obj, raw_text)。"""
    for i in range(retries):
        try:
            r = requests.get(
                "https://r.jina.ai/" + url,
                headers={
                    "Accept": "text/plain",
                    "X-Return-Format": "text",
                },
                impersonate="chrome",
                proxies=detect_proxies(),
                timeout=90,
            )
            if r.status_code != 200:
                print(f"[warn] jina {url} -> HTTP {r.status_code}: {r.text[:150]}", flush=True)
                time.sleep(5 * (i + 1))
                continue
            text = r.text
            # 去掉 jina 的 markdown 头（Title:/URL Source:/Markdown Content:）
            m = re.search(r"Markdown Content:\s*\n", text)
            payload = text[m.end():] if m else text
            # JSON 从第一个 { 开始
            br = payload.find("{")
            if br < 0:
                print(f"[warn] jina {url} no JSON found: {payload[:150]}", flush=True)
                time.sleep(5 * (i + 1))
                continue
            return json.loads(payload[br:]), payload
        except Exception as e:
            print(f"[warn] jina {url} attempt {i+1}: {e}", flush=True)
            time.sleep(5 * (i + 1))
    return None, None


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</(p|li|h[1-6]|pre|blockquote)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        text = text.replace(a, b)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_hot():
    cat_map = {}
    cats, _ = jina_get(BASE + "/categories.json")
    if isinstance(cats, dict) and "category_list" in cats:
        for c in cats["category_list"].get("categories", []):
            cat_map[c["id"]] = c.get("name", "")
            for sub in c.get("subcategory_list", []) or []:
                cat_map[sub["id"]] = sub.get("name", "")
    print(f"[info] categories: {len(cat_map)}", flush=True)

    topics, seen = [], set()
    sources = ["/hot.json"] + [f"/top.json?period=daily&page={p}" for p in range(0, 4)]
    for path in sources:
        if len(topics) >= 100:
            break
        data, _ = jina_get(BASE + path)
        if not isinstance(data, dict) or "topic_list" not in data:
            print(f"[warn] {path} bad response", flush=True)
            continue
        raw = data["topic_list"].get("topics", [])
        print(f"[info] {path} -> {len(raw)} topics", flush=True)
        for t in raw:
            if t["id"] in seen or len(topics) >= 100 or not t.get("title"):
                continue
            seen.add(t["id"])
            excerpt = strip_html(t.get("excerpt", ""))[:200]
            topics.append({
                "id": t["id"],
                "title": t["title"].strip(),
                "url": f"{BASE}/t/{t.get('slug', 'topic')}/{t['id']}",
                "created_at": t.get("created_at", ""),
                "views": t.get("views", 0),
                "like_count": t.get("like_count", 0),
                "posts_count": t.get("posts_count", 0),
                "category": cat_map.get(t.get("category_id"), str(t.get("category_id", "?"))),
                "excerpt": excerpt,
            })
        time.sleep(3)

    DATA.mkdir(exist_ok=True)
    (DATA / "hot_100.json").write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] saved {len(topics)} topics -> data/hot_100.json", flush=True)
    for i, t in enumerate(topics, 1):
        print(f"#{i}|{t['id']}|{t['title'][:60]}|cat={t['category']}|v={t['views']}|like={t['like_count']}|reply={t['posts_count']}|{t['excerpt'][:80]}")


def fetch_topics(ids):
    DATA.mkdir(exist_ok=True)
    for tid in ids:
        data, _ = jina_get(f"{BASE}/t/{tid}.json")
        if not isinstance(data, dict) or "post_stream" not in data:
            print(f"[warn] topic {tid} bad response", flush=True)
            continue
        posts = data["post_stream"].get("posts", [])
        main = posts[0] if posts else {}
        main_text = strip_html(main.get("cooked", ""))[:12000]
        replies = []
        for p in sorted(posts[1:], key=lambda x: x.get("like_count", 0), reverse=True)[:3]:
            replies.append({
                "author": p.get("username", ""),
                "like_count": p.get("like_count", 0),
                "text": strip_html(p.get("cooked", ""))[:400],
            })
        out = {
            "id": tid,
            "title": data.get("title", ""),
            "views": data.get("views", 0),
            "like_count": data.get("like_count", 0),
            "posts_count": data.get("posts_count", 0),
            "author": main.get("username", ""),
            "created_at": main.get("created_at", ""),
            "main_text": main_text,
            "top_replies": replies,
        }
        (DATA / f"topic_{tid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[ok] topic {tid} saved ({len(main_text)} chars)", flush=True)
        time.sleep(3)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "hot"
    if mode == "hot":
        fetch_hot()
    elif mode == "topic":
        fetch_topics(sys.argv[2:])
