# -*- coding: utf-8 -*-
"""一次性基建：搭建「蓝色大肥鱼（DeepSeek娘）」本地图库。

源 A: data/feiyu_assets/repo_pack（git clone 的表情包仓库，本脚本只负责扫描）
源 B: https://蓝色大肥鱼.com/characters/deepseek.html（直抓 HTML，失败走 r.jina.ai）
源 C: https://aigengtu.com/DeepSeek娘（同上）
源 D: 6 张核心保底高清直链

用法:
  python 脚本/init_feiyu_assets.py fetch       # 抓取+清洗+生成拼图预览 raw_manifest.json
  python 脚本/init_feiyu_assets.py finalize    # 按 selection.json 归档到 selected/ 并生成 feiyu_index.json

全部网络请求走代理（LINUXDO_PROXY 环境变量优先，默认 http://127.0.0.1:7897）。
"""
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "data" / "feiyu_assets"
RAW = ASSETS / "raw"
SELECTED = ASSETS / "selected"

PROXY = os.environ.get("LINUXDO_PROXY", "http://127.0.0.1:7897")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

SRC_B_PAGE = "https://xn--pssy23gqgbz2d718b.com/characters/deepseek.html"
SRC_C_PAGE = "https://aigengtu.com/DeepSeek%E5%A8%98"
SRC_D_URLS = [
    ("srcD_01", "https://img.36krcdn.com/hsossms/20260820/v2_1a2ca770bcdb4a5b846e9dc6a8bc5ee7@6119835_oswg791280oswg690oswg1215_img_000?x-oss-process=image/format,jpg/interlace,1"),
    ("srcD_02", "https://n1.itc.cn/img7/adapt/wb/sohulife/2026/08/21/178731037339220126_664_2000.PNG"),
    ("srcD_03", "https://n1.itc.cn/img7/adapt/wb/sohulife/2026/08/21/178731037392572983_664_2000.PNG"),
    ("srcD_04", "https://n1.itc.cn/img7/adapt/wb/sohulife/2026/08/21/178731037416294998_664_2000.PNG"),
    ("srcD_05", "https://img1.gamersky.com/image2026/08/20260817_zy_red_164_2/1121_S.jpg"),
    ("srcD_06", "https://i0.hdslb.com/bfs/archive/b43cadb6e12a42af45f02978320557f73b5d9eed.jpg"),
]
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
URL_JUNK = re.compile(r"(logo|icon|avatar|favicon|banner|button|\.svg)", re.I)


def opener():
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )


def http_get(url, timeout=60, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with opener().open(req, timeout=timeout) as r:
        return r.read()


def save_bytes(name_stem, data, src):
    """按扩展名落盘 raw/，返回路径；扩展名按 Content-Type 或 magic bytes 判定。"""
    ext = ".png"
    if data[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        ext = ".gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    p = RAW / f"{name_stem}{ext}"
    p.write_bytes(data)
    return p


def collect_from_repo_pack():
    """源 A：扫描已 clone 的仓库，把图片复制进 raw/。"""
    n = 0
    pack = ASSETS / "repo_pack"
    if not pack.exists():
        print("[warn] repo_pack 不存在，跳过源 A")
        return
    for p in sorted(pack.rglob("*")):
        if p.suffix.lower() in IMG_EXT and p.is_file():
            n += 1
            (RAW / f"srcA_{n:02d}{p.suffix.lower()}").write_bytes(p.read_bytes())
    print(f"[ok] 源A repo_pack -> {n} 张")


def extract_img_urls(html, base):
    """从 HTML 里提取候选图片 URL（src / data-src / srcset），过滤站务杂图。"""
    from urllib.parse import urljoin
    urls = []
    for m in re.finditer(r"""(?:src|data-src)\s*=\s*["']([^"']+)["']""", html):
        u = urljoin(base, m.group(1))
        if u.lower().startswith("http") and not URL_JUNK.search(u) and looks_like_img(u):
            urls.append(u)
    # srcset：逗号分隔的 "url 宽度w" 列表，取每组最大宽度那条
    for m in re.finditer(r"""srcset\s*=\s*["']([^"']+)["']""", html):
        best = None
        for part in m.group(1).split(","):
            tok = part.strip().split()
            if not tok:
                continue
            w = 0
            if len(tok) > 1 and tok[1].endswith("w"):
                w = int(tok[1][:-1] or 0)
            if best is None or w > best[0]:
                best = (w, tok[0])
        if best and best[1].lower().startswith("http") and not URL_JUNK.search(best[1]) and looks_like_img(best[1]):
            urls.append(best[1])
    for m in re.finditer(r"""!\[[^\]]*\]\((https?://[^)\s]+)\)""", html):
        u = urljoin(base, m.group(1))
        if not URL_JUNK.search(u) and looks_like_img(u):
            urls.append(u)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def looks_like_img(u):
    """URL 路径像图片（带图片扩展名，或明显是 previews 图床路径）。"""
    path = u.split("?")[0].lower()
    return any(path.endswith(e) for e in IMG_EXT) or "/preview" in path


def fetch_page(tag, page_url, prefix, limit=40):
    """源 B/C：直抓页面提图，失败走 r.jina.ai。"""
    html = None
    try:
        html = http_get(page_url).decode("utf-8", "ignore")
        print(f"[ok] {tag} 直连成功，{len(html)} 字符")
    except Exception as e:
        print(f"[warn] {tag} 直连失败: {e}，改走 r.jina.ai")
        try:
            txt = http_get("https://r.jina.ai/" + page_url, timeout=90,
                           headers={"Accept": "text/plain", "X-Return-Format": "text"}).decode("utf-8", "ignore")
            html = txt
            print(f"[ok] {tag} jina 中转成功，{len(txt)} 字符")
        except Exception as e2:
            print(f"[fail] {tag} jina 也失败: {e2}")
            return
    urls = extract_img_urls(html, page_url)
    print(f"[info] {tag} 提取到 {len(urls)} 个候选图片 URL")
    n = 0
    for u in urls[:limit]:
        try:
            data = http_get(u)
            if len(data) < 8000:  # <8KB 的多半是小图标
                continue
            save_bytes(f"{prefix}_{n + 1:02d}", data, u)
            n += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"[warn] {tag} 下载失败 {u[:80]}: {e}")
    print(f"[ok] {tag} -> {n} 张")


def fetch_direct():
    """源 D：6 张保底直链。"""
    for name, url in SRC_D_URLS:
        for attempt in range(3):
            try:
                data = http_get(url)
                p = save_bytes(name, data, url)
                print(f"[ok] {name} <- {len(data)//1024}KB {p.name}")
                break
            except Exception as e:
                print(f"[warn] {name} 第{attempt+1}次失败: {e}")
                time.sleep(3)
        time.sleep(0.5)


def ahash(img):
    h = img.convert("L").resize((8, 8), Image.LANCZOS)
    px = list(h.getdata())
    avg = sum(px) / 64
    return "".join("1" if p > avg else "0" for p in px)


def clean_and_manifest():
    """清洗：损坏/小于 200x200 剔除；md5 + aHash 去重；产出 manifest 与拼图预览。"""
    items, seen_md5, seen_ah = [], set(), {}
    for p in sorted(RAW.iterdir()):
        if p.suffix.lower() not in IMG_EXT:
            continue
        try:
            img = Image.open(p)
            img.load()
            if getattr(img, "is_animated", False):
                img.seek(0)
            w, hgt = img.size
        except Exception:
            print(f"[del] 损坏 {p.name}")
            p.unlink()
            continue
        if w < 200 or hgt < 200:
            print(f"[del] 过小 {p.name} {w}x{hgt}")
            p.unlink()
            continue
        md5 = hashlib.md5(p.read_bytes()).hexdigest()
        ah = ahash(img)
        if md5 in seen_md5 or any(sum(a != b for a, b in zip(ah, k)) <= 6 for k in seen_ah):
            print(f"[del] 重复 {p.name}")
            p.unlink()
            continue
        seen_md5.add(md5)
        seen_ah[ah] = p.name
        items.append({"id": "", "file": p.name, "w": w, "h": hgt, "kb": p.stat().st_size // 1024})
    # 编号 + manifest
    manifest = []
    for i, it in enumerate(items, 1):
        it["id"] = f"A{i:03d}"
        manifest.append(it)
    (ASSETS / "raw_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] 清洗后 {len(manifest)} 张 -> raw_manifest.json")
    make_sheets(manifest)


def make_sheets(manifest):
    """拼图预览：每张 sheet 4 列 x 5 行，缩略图 280px + 编号标签，供 AI 一次浏览挑选。"""
    cols, rows, cell, pad, label_h = 4, 5, 280, 8, 26
    for s_idx in range(0, len(manifest), cols * rows):
        chunk = manifest[s_idx:s_idx + cols * rows]
        W = cols * (cell + pad) + pad
        H = rows * (cell + label_h + pad) + pad
        sheet = Image.new("RGB", (W, H), (24, 26, 34))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        for i, it in enumerate(chunk):
            cx, cy = i % cols, i // cols
            x = pad + cx * (cell + pad)
            y = pad + cy * (cell + label_h + pad)
            try:
                img = Image.open(RAW / it["file"]).convert("RGB")
                img.thumbnail((cell, cell), Image.LANCZOS)
                sheet.paste(img, (x + (cell - img.width) // 2, y + (cell - img.height) // 2))
            except Exception:
                pass
            d.text((x + 2, y + cell + 4), f"{it['id']} {it['w']}x{it['h']}", fill=(240, 240, 240))
        out = ASSETS / f"sheet_{s_idx // (cols * rows) + 1}.png"
        sheet.save(out)
        print(f"[ok] {out.name} ({len(chunk)} 图)")


def finalize():
    """按 selection.json（AI 挑选后手写）归档 selected/ 并生成 feiyu_index.json。"""
    sel = json.loads((ASSETS / "selection.json").read_text(encoding="utf-8"))
    man = {m["id"]: m for m in json.loads((ASSETS / "raw_manifest.json").read_text(encoding="utf-8"))}
    SELECTED.mkdir(parents=True, exist_ok=True)
    counters, index = {}, {}
    for row in sel:
        cat = row["category"]
        counters[cat] = counters.get(cat, 0) + 1
        src = RAW / man[row["id"]]["file"]
        dst = SELECTED / f"{cat}_{counters[cat]:02d}.png"
        img = Image.open(src)
        if getattr(img, "is_animated", False):
            img.seek(0)
        img.convert("RGBA").save(dst)
        index.setdefault(cat, []).append({
            "file": f"data/feiyu_assets/selected/{dst.name}",
            "desc": row.get("desc", ""),
            "source_id": row["id"],
            "size": f"{img.width}x{img.height}",
        })
        print(f"[ok] {row['id']} -> {dst.name}")
    (ASSETS / "feiyu_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] index -> data/feiyu_assets/feiyu_index.json ({sum(len(v) for v in index.values())} 张)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if mode == "fetch":
        RAW.mkdir(parents=True, exist_ok=True)
        collect_from_repo_pack()
        fetch_direct()
        fetch_page("源B蓝色大肥鱼.com", SRC_B_PAGE, "srcB")
        fetch_page("源C aigengtu", SRC_C_PAGE, "srcC")
        clean_and_manifest()
    elif mode == "finalize":
        finalize()
