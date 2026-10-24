# -*- coding: utf-8 -*-
"""用注入的 fish.audio 会话 token 自动创建 API Key。

输入: data/fish_session_token.txt（网页登录 token）
输出: data/fish_api_key.txt（API Key，成功时）
原理: 注入 cookie+localStorage 登录态 -> 重试打开 /dashboard/api_keys -> 填名点创建 -> 拦截响应。
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKEN = (REPO_ROOT / "data" / "fish_session_token.txt").read_text(encoding="utf-8").strip()
WS_ID = "157b064a30e64803bf648c7117650cb6"
KEY_FILE = REPO_ROOT / "data" / "fish_api_key.txt"


def attempt(b, n):
    st = {"headers": None, "key_resp": []}
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    ctx.add_cookies([
        {"name": "token", "value": TOKEN, "domain": "fish.audio", "path": "/"},
        {"name": "active_workspace_id", "value": WS_ID, "domain": "fish.audio", "path": "/"},
    ])
    page = ctx.new_page()

    def on_req(req):
        if "api.fish.audio" in req.url and "ad-" not in req.url and st["headers"] is None:
            st["headers"] = dict(req.headers)

    def on_resp(resp):
        u = resp.url
        if "api.fish.audio" in u and "ad-" not in u and (
                "key" in u.lower() or resp.request.method == "POST"):
            try:
                body = resp.text()[:600]
            except Exception:
                body = ""
            st["key_resp"].append((resp.request.method, u, resp.status, body,
                                   resp.request.post_data or ""))

    page.on("request", on_req)
    page.on("response", on_resp)

    page.goto("https://fish.audio/zh-CN/", timeout=60000)
    page.evaluate("([t, w]) => { localStorage.setItem('token', t);"
                  " localStorage.setItem('active_workspace_id', w);"
                  " localStorage.setItem('active_team_id', w); }", [TOKEN, WS_ID])
    page.goto("https://fish.audio/zh-CN/dashboard/api_keys", timeout=60000)
    page.wait_for_timeout(9000 + n * 2000)
    txt = page.evaluate("() => document.body.innerText")
    if "创建" not in txt and "密钥" not in txt:
        print(f"[try{n}] 管理界面未渲染: {'错误页' if '出错' in txt else txt[:50]}")
        ctx.close()
        return st, None
    print(f"[try{n}] 管理界面已渲染")
    clicked = False
    for sel in ("input", "textarea"):
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=5000)
            loc.fill("feiyu-daily")
            page.wait_for_timeout(400)
            page.locator("button", has_text="创建").first.click(timeout=5000)
            clicked = True
            break
        except Exception:
            continue
    print("[click]", "成功" if clicked else "失败")
    page.wait_for_timeout(9000)
    txt2 = page.evaluate("() => document.body.innerText")
    page.screenshot(path=str(REPO_ROOT / "data" / "fish_key_created.png"))
    ctx.close()
    return st, txt2


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True,
                              proxy={"server": "http://127.0.0.1:7897"})
        txt2 = None
        st = None
        for n in range(1, 5):
            st, txt2 = attempt(b, n)
            if txt2 is not None:
                break
            time.sleep(3)
        b.close()

    print("== 请求头样例 ==")
    if st and st["headers"]:
        for k in ("authorization", "token", "cookie", "content-type"):
            if k in st["headers"]:
                print(" ", k, ":", str(st["headers"][k])[:90])
    print("== key 相关响应 ==")
    api_key = None
    if st:
        for m, u, s, body, req in st["key_resp"]:
            print(m, s, u[:120])
            if req:
                print("   req:", req[:150])
            if body:
                print("   resp:", body[:300])
            # 从响应里挖 key（形如长随机串）
            try:
                j = json.loads(body)
                for v in (j.get("key"), j.get("api_key"), j.get("secret"),
                          (j.get("item") or {}).get("key") if isinstance(j.get("item"), dict) else None):
                    if v and len(str(v)) > 20:
                        api_key = str(v)
            except Exception:
                pass
    if txt2:
        print("== 页面文本 ==")
        print(txt2[:600].replace("\n", " | "))
        if api_key is None:
            # 页面文本里找 feiyu-daily 对应的 key 行
            for line in txt2.split("\n"):
                if len(line) > 30 and ("_" in line or line.startswith("fa")) and "feiyu" not in line:
                    import re
                    if re.fullmatch(r"[A-Za-z0-9_\-]{28,}", line.strip()):
                        api_key = line.strip()
                        print("候选key:", api_key[:12], "...")
                        break
    if api_key:
        KEY_FILE.write_text(api_key, encoding="utf-8")
        print("[ok] API Key 已保存 -> data/fish_api_key.txt")
    else:
        print("[fail] 未捕获到 key")
        sys.exit(1)


if __name__ == "__main__":
    main()
