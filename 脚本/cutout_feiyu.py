# -*- coding: utf-8 -*-
"""大肥鱼立绘批量抠图：selected/*.png --rembg--> selected_cut/*.png（透明底）。

首次运行会经代理下载 u2net 模型（~170MB）到 ~/.u2net/。
用法: python 脚本/cutout_feiyu.py
"""
import os
from pathlib import Path

os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7897")
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7897")

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "feiyu_assets" / "selected"
DST = REPO_ROOT / "data" / "feiyu_assets" / "selected_cut"


def main():
    DST.mkdir(exist_ok=True)
    from rembg import remove, new_session
    from PIL import Image
    session = new_session("u2net")
    n = 0
    for p in sorted(SRC.glob("*.png")):
        out = DST / p.name
        if out.exists():
            continue
        img = Image.open(p)
        if getattr(img, "is_animated", False):
            img.seek(0)
        result = remove(img.convert("RGBA"), session=session)
        # 收紧透明边
        bbox = result.getbbox()
        if bbox:
            result = result.crop(bbox)
        result.save(out)
        n += 1
        print(f"[ok] {p.name} -> {result.width}x{result.height}")
    print(f"[done] 抠图 {n} 张 -> {DST}")


if __name__ == "__main__":
    main()
