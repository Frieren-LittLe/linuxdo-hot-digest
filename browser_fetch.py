# -*- coding: utf-8 -*-
"""用本机真实 Edge 浏览器（Playwright 有头模式，走系统代理）通过 linux.do 的
Cloudflare 验证，然后在页面上下文中 fetch 同源 Discourse JSON 接口。

用法:
  python browser_fetch.py hot       # 抓 Top 100 热帖元数据 -> data/hot_100.json
  python browser_fetch.py topic <id> [<id>...]  # 抓指定帖子主帖正文 -> data/topic_<id>.json
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://linux.do"
DATA = Path("data")


def detect_proxy_server():
    """Playwright 代理地址：LINUXDO_PROXY 环境变量优先，其次系统代理，均无则 None。"""
    p = (
        os.environ.get("LINUXDO_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
    )
    if p:
        return p
    ps = urllib.request.getproxies()
    return ps.get("https") or ps.get("http")


def try_click_turnstile(page):
    """尝试点击 Turnstile 复选框；只有真实找到 widget iframe 才点击。"""
    for sel in [
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[title*="Cloudflare"]',
        'iframe[title*="Widget"]',
    ]:
        try:
            fr = page.locator(sel).first
            box = fr.bounding_box(timeout=1500)
            if box and box["width"] > 200 and box["height"] > 40:
                x = box["x"] + 30
                y = box["y"] + box["height"] / 2
                page.mouse.click(x, y)
                print(f"[cf] clicked iframe {sel} at ({x:.0f},{y:.0f})", flush=True)
                return True
        except Exception:
            continue
    return False


def wait_for_forum(page, timeout_s=180):
    """等待通过 Cloudflare 验证进入论坛（标题不再是 请稍候/Just a moment）。"""
    DATA.mkdir(exist_ok=True)
    start_ts = time.time()
    deadline = start_ts + timeout_s
    clicked = 0
    last_shot = 0
    while time.time() < deadline:
        title = (page.title() or "").strip()
        if "请稍候" not in title and "moment" not in title.lower() and title:
            return True
        now = time.time()
        # 每 15 秒诊断截图一次
        if now - last_shot > 15:
            try:
                page.screenshot(path=str(DATA / "cf_debug.png"))
                body = page.evaluate("() => document.body ? document.body.innerText.slice(0,200) : ''")
                print(f"[cf] t={int(now-start_ts)}s title={title!r} body={body!r}", flush=True)
                last_shot = now
            except Exception as e:
                print(f"[cf] diag error: {e}", flush=True)
        # 仅在 widget iframe 真实出现时点击（最多 3 次）
        if clicked < 3:
            try:
                found = page.locator('iframe[src*="challenges.cloudflare.com"]').count()
                if found > 0 and try_click_turnstile(page):
                    clicked += 1
            except Exception:
                pass
        page.wait_for_timeout(3000)
    return False


def page_fetch_json(page, path):
    return page.evaluate(
        """async (p) => {
            const r = await fetch(p, {headers: {'Accept': 'application/json'}, credentials: 'include'});
            if (!r.ok) return {__status: r.status};
            return await r.json();
        }""",
        path,
    )


def strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</(p|li|h[1-6]|pre|blockquote)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_hot(page):
    cat_map = {}
    cats = page_fetch_json(page, "/categories.json")
    if isinstance(cats, dict) and "category_list" in cats:
        for c in cats["category_list"].get("categories", []):
            cat_map[c["id"]] = c.get("name", "")
            for sub in c.get("subcategory_list", []) or []:
                cat_map[sub["id"]] = sub.get("name", "")

    topics, seen = [], set()
    sources = ["/hot.json"] + [f"/top.json?period=daily&page={p}" for p in range(0, 5)]
    for path in sources:
        if len(topics) >= 100:
            break
        data = page_fetch_json(page, path)
        if not isinstance(data, dict) or "topic_list" not in data:
            print(f"[warn] {path} bad response: {str(data)[:120]}", flush=True)
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
        page.wait_for_timeout(800)

    DATA.mkdir(exist_ok=True)
    (DATA / "hot_100.json").write_text(
        json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"[ok] saved {len(topics)} topics -> data/hot_100.json", flush=True)
    for i, t in enumerate(topics, 1):
        print(f"#{i}|{t['id']}|{t['title'][:60]}|cat={t['category']}|v={t['views']}|like={t['like_count']}|reply={t['posts_count']}|{t['excerpt'][:80]}")


def fetch_topics(page, ids):
    DATA.mkdir(exist_ok=True)
    for tid in ids:
        data = page_fetch_json(page, f"/t/{tid}.json?track_visit=false")
        if not isinstance(data, dict) or "post_stream" not in data:
            print(f"[warn] topic {tid} bad response: {str(data)[:120]}", flush=True)
            continue
        posts = data["post_stream"].get("posts", [])
        main = posts[0] if posts else {}
        main_text = strip_html(main.get("cooked", ""))[:12000]
        # 点赞最高的 3 条回复，作为社区反响参考
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
        (DATA / f"topic_{tid}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"[ok] topic {tid} saved ({len(main_text)} chars main text)", flush=True)
        page.wait_for_timeout(800)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "hot"
    DATA.mkdir(exist_ok=True)
    with sync_playwright() as p:
        proxy_server = detect_proxy_server()
        launch_opts = dict(
            user_data_dir=str(DATA / "edge_profile"),
            channel="msedge",
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            args=["--disable-blink-features=AutomationControlled"],
        )
        if proxy_server:
            launch_opts["proxy"] = {"server": proxy_server}
        ctx = p.chromium.launch_persistent_context(**launch_opts)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        ok = wait_for_forum(page)
        print(f"[cf] forum ready: {ok}, title: {page.title()!r}", flush=True)
        if not ok:
            ctx.close()
            sys.exit(1)

        if mode == "hot":
            fetch_hot(page)
        elif mode == "topic":
            fetch_topics(page, sys.argv[2:])
        ctx.close()


if __name__ == "__main__":
    main()
