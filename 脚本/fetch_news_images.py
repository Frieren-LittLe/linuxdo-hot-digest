# -*- coding: utf-8 -*-
"""《大肥鱼的科技日报》候选插图抓取（视觉优先三源策略）。

优先级（规范：拒绝生搬原帖废图）:
  1. 项目实景高清截图：Playwright(Edge) 打开 GitHub 仓库/官网，2x 高清首屏
  2. 全网关键词搜图：Bing Images 提取原图 murl，过滤小图
  3. 原帖插图仅备选：只保留明确指定的独家实测对比图（topic_keep）

用法: python 脚本/fetch_news_images.py [YYYY-MM-DD]
输出: data/video_workspace/<date>/candidates/newsN_A.png ... + preview.html
"""
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image
from curl_cffi import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-23"
WS = REPO_ROOT / "data" / "video_workspace" / DATE
CAND = WS / "candidates"

PROXY = os.environ.get("LINUXDO_PROXY", "http://127.0.0.1:7897")
PX = {"http": PROXY, "https": PROXY}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

BOARDS = [
    {"n": 1, "label": "Cloudflare WAF", "topic": 3054943, "topic_keep": 0,
     "shots": ["https://www.cloudflare.com/", "https://blog.cloudflare.com/"],
     "bings": [("Cloudflare WAF dashboard", 1), ("cloudflare brand orange cloud", 1)]},
    {"n": 2, "label": "PHP 漏洞复盘", "topic": 3065907, "topic_keep": 0,
     "shots": ["https://www.php.net/"],
     "bings": [("elePHPant PHP logo", 1), ("hacker code screen dark", 1)]},
    {"n": 3, "label": "婚礼视频副业 VVV", "topic": 3064156, "topic_keep": 0,
     "shots": ["https://www.remotion.dev/", "https://claude.ai/"],
     "bings": [("Remotion react video", 1), ("AI wedding video editing", 1)]},
    {"n": 4, "label": "knowledge-project", "topic": 3062753, "topic_keep": 0,
     "shots": ["https://github.com/briqt/knowledge-project"],
     "bings": [("AI agent coding workflow", 1), ("Claude Code terminal", 1)]},
    {"n": 5, "label": "REA 逆向小米电视", "topic": 3064579, "topic_keep": 1,
     "shots": ["https://github.com/morluto/rea"],
     "bings": [("小米电视 桌面", 1), ("Android TV settings", 1)]},
    {"n": 6, "label": "讯飞 10 亿 Token", "topic": 3060920, "topic_keep": 1,
     "shots": ["https://xinghuo.xfyun.cn/"],
     "bings": [("讯飞星火 大模型", 2)]},
]


def fetch(url):
    headers = {"User-Agent": UA}
    host = url.split("/")[2]
    if any(d in host for d in ("hdslb.com", "bilibili.com", "ldstatic.com", "linux.do")):
        headers["Referer"] = f"https://{host}/"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener(
            urllib.request.ProxyHandler(PX)).open(req, timeout=60) as r:
        return r.read()


def jina_html(url, retries=3):
    """r.jina.ai 返回目标页 HTML（绕 linux.do Cloudflare）。"""
    for i in range(retries):
        try:
            r = requests.get("https://r.jina.ai/" + url,
                             headers={"X-Return-Format": "html"},
                             impersonate="chrome", proxies=PX, timeout=90)
            if r.status_code == 200:
                return r.text
            print(f"[warn] jina {url} HTTP {r.status_code}", flush=True)
        except Exception as e:
            print(f"[warn] jina {url}: {e}", flush=True)
        time.sleep(5 * (i + 1))
    return ""


def topic_images(tid):
    """原帖正文图：cdn*.ldstatic.com/4X/（用户上传），original 优先，排除小缩略。"""
    html = jina_html(f"https://linux.do/t/{tid}")
    urls = re.findall(
        r'https://cdn\d*\.ldstatic\.com/(?:original|optimized)/4X/[^\s"\'<>\\)]+', html)
    seen, out = set(), []
    for u in urls:
        u = u.split("\\")[0].rstrip(".,)")
        if re.search(r"_2_(?:32x32|180x180|360x360)\.", u) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    out.sort(key=lambda u: 0 if "/original/" in u else 1)
    return out


def bing_image_search(query, want):
    """Bing Images 搜索：HTML 里 m='{"murl":"原图URL"...}' 逐条提取。"""
    u = "https://www.bing.com/images/search?q=" + urllib.parse.quote(query) + "&form=HDRSC2"
    try:
        html = fetch(u).decode("utf-8", "ignore")
    except Exception as e:
        print(f"[warn] bing {query}: {e}")
        return []
    urls = []
    for pat in (r'&quot;murl&quot;:&quot;(https?://[^&]+)&quot;',
                r'"murl":"(https?://[^"]+)"'):
        urls += re.findall(pat, html)
    out = []
    for x in urls:
        if re.search(r"\.(jpe?g|png|webp)(\?|$)", x, re.I) and x not in out:
            out.append(x.replace("\\u0026", "&"))
        if len(out) >= want * 3:  # 多备几条，下载时按质量淘汰
            break
    return out[:want * 3]


def playwright_shots(urls, board_n):
    """Edge 无头浏览器 2x 高清首屏截图。"""
    from playwright.sync_api import sync_playwright
    shots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True,
                                        proxy={"server": PROXY})
            page = browser.new_page(viewport={"width": 1280, "height": 800},
                                    device_scale_factor=2)
            for u in urls:
                try:
                    page.goto(u, timeout=45000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    buf = page.screenshot()
                    img = Image.open(io.BytesIO(buf))
                    shots.append({"buf": buf, "tag": f"截图:{u.split('/')[2]}", "img": img})
                    print(f"[ok] 截图 {u} {img.width}x{img.height}")
                except Exception as e:
                    print(f"[warn] 截图失败 {u}: {e}")
            browser.close()
    except Exception as e:
        print(f"[warn] playwright 不可用: {e}")
    return shots


def collect(board):
    got, seen_md5 = [], set()

    def try_save(data_or_buf, src_tag, min_w=600, min_h=400):
        if len(got) >= 4:
            return
        try:
            if isinstance(data_or_buf, dict):  # playwright shot
                img = data_or_buf["img"]
                data = data_or_buf["buf"]
            else:
                data = data_or_buf
                img = Image.open(io.BytesIO(data))
                img.load()
            if img.width < min_w or img.height < min_h:
                print(f"[skip] {src_tag} 尺寸过小 {img.width}x{img.height}")
                return
            md5 = hashlib.md5(data).hexdigest()
            if md5 in seen_md5:
                return
            seen_md5.add(md5)
            letter = "ABCD"[len(got)]
            p = CAND / f"news{board['n']}_{letter}.png"
            img.convert("RGB").save(p)
            got.append({"file": p.name, "src": src_tag, "size": f"{img.width}x{img.height}"})
            print(f"[ok] {p.name} <- {src_tag} {img.width}x{img.height}")
        except Exception as e:
            print(f"[warn] 弃用 {src_tag}: {e}")

    # 1. Playwright 实景截图（首选）
    for shot in playwright_shots(board["shots"], board["n"]):
        try_save(shot, shot["tag"])

    # 2. Bing 全网搜图
    for q, want in board["bings"]:
        for u in bing_image_search(q, want):
            if len([g for g in got if g["src"].startswith("搜图")]) >= sum(
                    w for _, w in board["bings"]) + 1:
                break
            try:
                try_save(fetch(u), f"搜图:{q}")
            except Exception as e:
                print(f"[warn] 搜图下载失败 {u[:70]}: {e}")

    # 3. 原帖备选：只保留明确数量的前几张（独家实测对比图）
    if board["topic_keep"] > 0:
        for u in topic_images(board["topic"])[:board["topic_keep"]]:
            try:
                try_save(fetch(u), f"原帖实测图{board['topic']}")
            except Exception as e:
                print(f"[warn] 原帖图失败: {e}")
    return got


def preview(all_got):
    cards = []
    for b in BOARDS:
        items = all_got.get(b["n"], [])
        imgs = "".join(
            f'<figure><img src="candidates/{it["file"]}"><figcaption>{it["file"].split(".")[0].upper()} ｜ {it["src"]} ｜ {it["size"]}</figcaption></figure>'
            for it in items)
        cards.append(f'<section><h2>News {b["n"]}｜{b["label"]}（原帖 {b["topic"]}）</h2><div class="g">{imgs}</div></section>')
    html = f"""<!DOCTYPE html><html lang="zh"><meta charset="utf-8"><title>候选插图 {DATE}</title>
<style>body{{font-family:system-ui;margin:24px;background:#16181f;color:#eee}}
h2{{border-left:4px solid #4da3ff;padding-left:10px}}
.g{{display:flex;flex-wrap:wrap;gap:14px}}
figure{{margin:0;max-width:340px;background:#22252f;border-radius:10px;padding:10px}}
img{{max-width:100%;max-height:260px;border-radius:6px;display:block;margin:auto}}
figcaption{{font-size:13px;color:#9ab;padding-top:8px;text-align:center}}</style>
<h1>《大肥鱼的科技日报》{DATE} 候选插图评选（视觉优先版）</h1>
<p>来源：Playwright 实景截图 ／ Bing 全网搜图 ／ 原帖独家实测图。每板块选定 1 张（回复如 <b>1A, 2C, 3B, 4A, 5B, 6A</b>）</p>
{''.join(cards)}"""
    (WS / "preview.html").write_text(html, encoding="utf-8")
    print(f"[ok] preview -> {WS / 'preview.html'}")


if __name__ == "__main__":
    CAND.mkdir(parents=True, exist_ok=True)
    for old in CAND.glob("*.png"):
        old.unlink()  # 清空旧候选池
    all_got = {}
    for b in BOARDS:
        print(f"===== News {b['n']} {b['label']} =====", flush=True)
        all_got[b["n"]] = collect(b)
        time.sleep(1)
    (WS / "candidates_manifest.json").write_text(
        json.dumps(all_got, ensure_ascii=False, indent=1), encoding="utf-8")
    preview(all_got)
    total = sum(len(v) for v in all_got.values())
    print(f"[done] 共 {total} 张候选")
