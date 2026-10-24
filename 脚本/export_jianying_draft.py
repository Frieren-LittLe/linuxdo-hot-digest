# -*- coding: utf-8 -*-
"""《大肥鱼的科技日报》剪映专业版草稿导出：对齐插图/立绘/配音/BGM/音效/字幕轨道。

用法: python 脚本/export_jianying_draft.py [YYYY-MM-DD]
草稿写入剪映草稿目录（存在时），否则退回工作目录。
"""
import json
import os
import sys
from pathlib import Path

import pyJianYingDraft as dj

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-23"
WS = REPO_ROOT / "data" / "video_workspace" / DATE
FEIYU = REPO_ROOT / "data" / "feiyu_assets" / "selected"
DRAFT_NAME = f"大肥鱼的科技日报_{DATE}"

JY_DIR = Path(os.environ["LOCALAPPDATA"]) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"


def main():
    tl = json.loads((WS / "timeline.json").read_text(encoding="utf-8"))
    total = tl["total"]
    segs = tl["segments"]

    if JY_DIR.exists():
        folder = dj.DraftFolder(str(JY_DIR))
        target = JY_DIR / DRAFT_NAME
    else:
        folder = dj.DraftFolder(str(WS / "jianying_drafts"))
        target = WS / "jianying_drafts" / DRAFT_NAME
    sf = folder.create_draft(DRAFT_NAME, 1080, 1528, 30, allow_replace=True, maintrack_adsorb=False)

    t_pic, t_fish, t_voc, t_bgm, t_sfx, _ = sf.append_tracks([
        dj.TrackSpec(dj.TrackType.video, name="新闻插图"),
        dj.TrackSpec(dj.TrackType.video, name="大肥鱼立绘"),
        dj.TrackSpec(dj.TrackType.audio, name="配音人声"),
        dj.TrackSpec(dj.TrackType.audio, name="BGM"),
        dj.TrackSpec(dj.TrackType.audio, name="音效"),
        dj.TrackSpec(dj.TrackType.text, name="字幕"),
    ])

    def s_(x):
        return f"{x:.3f}s"

    for s in segs:
        dur = s["dur"] + s["gap_after"]
        pic = dj.VideoSegment(dj.VideoMaterial(str(WS / "selected_images" / f"{s['pic']}.png")),
                              dj.trange(s_(s["start"]), s_(dur)))
        sf.add_segment(pic, t_pic)
        fish = dj.VideoSegment(dj.VideoMaterial(str(FEIYU / f"{s['img']}.png")),
                               dj.trange(s_(s["start"]), s_(dur)))
        sf.add_segment(fish, t_fish)

    for wav, tr in (("voice_track.wav", t_voc), ("bgm_track.wav", t_bgm), ("sfx_track.wav", t_sfx)):
        seg = dj.AudioSegment(dj.AudioMaterial(str(WS / wav)), dj.trange("0s", s_(total)))
        sf.add_segment(seg, tr)

    sf.import_srt(str(WS / "subtitles.srt"), "字幕")

    sf.save()
    print(f"[ok] 剪映草稿 -> {target}")
    print("[hint] 打开剪映专业版即可在草稿列表看到并继续微调")


if __name__ == "__main__":
    main()
