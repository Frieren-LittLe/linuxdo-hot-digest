# -*- coding: utf-8 -*-
"""《大肥鱼的科技日报》第 4 步：$1:\\sqrt{2}$ 竖屏（1080x1528）动画渲染。

原理：生成时间驱动的 HTML 动画页（window.seek(t) 决定一切画面状态，无实时循环），
Playwright(Edge) 逐帧截图（30fps JPEG），FFmpeg 封装混音音轨成片。
波形条数据从人声轨真实 RMS 包络预计算。

用法: python 脚本/render_video.py [YYYY-MM-DD]
输出: data/video_workspace/<date>/大肥鱼的科技日报_<date>.mp4
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-23"
WS = REPO_ROOT / "data" / "video_workspace" / DATE
FRAMES = WS / "frames"
FPS = 30
W, H = 1080, 1528


def find_ffmpeg():
    for p in (REPO_ROOT / "data" / "bin").rglob("ffmpeg.exe"):
        return str(p)
    return "ffmpeg"


def voice_envelope(fps):
    """人声轨每帧 RMS 包络（0~1），驱动波形条。"""
    with wave.Wave_read(str(WS / "voice_track.wav")) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    hop = int(44100 / fps)
    n = len(raw) // hop
    env = np.sqrt((raw[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    env = env / (env.max() + 1e-9)
    return env.tolist()


HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1528px;overflow:hidden;font-family:"Microsoft YaHei",sans-serif}
#stage{position:relative;width:1080px;height:1528px;background:linear-gradient(160deg,#0b1020 0%,#0d1a33 45%,#0a1226 100%)}
#rain{position:absolute;inset:0;opacity:.16}
#vig{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 42%,transparent 55%,rgba(0,0,10,.55) 100%);pointer-events:none}
/* 顶部横幅 12% */
#banner{position:absolute;top:0;left:0;right:0;height:183px;padding:20px 36px;
 background:rgba(13,26,51,.55);backdrop-filter:blur(14px);border-bottom:1px solid rgba(90,160,255,.25);
 display:flex;align-items:center;gap:24px;z-index:5}
#logo{font-size:44px;font-weight:900;color:#eaf4ff;letter-spacing:2px;text-shadow:0 0 24px rgba(77,163,255,.8)}
#logo em{font-style:normal;color:#59c2ff}
#date{margin-left:auto;text-align:right;color:#8fb8e8;font-size:24px;line-height:1.5}
#wave{display:flex;align-items:flex-end;gap:5px;height:64px;padding:0 8px}
#wave i{display:block;width:7px;background:linear-gradient(180deg,#7dd3fc,#3b82f6);border-radius:3px;box-shadow:0 0 8px rgba(59,130,246,.7)}
/* 中部展台 58% */
#stageMid{position:absolute;top:183px;left:0;right:0;height:886px;padding:26px 40px 0}
#titleBar{position:relative;height:96px;margin-bottom:18px;border-radius:18px;
 background:linear-gradient(90deg,rgba(59,130,246,.28),rgba(59,130,246,.06));
 border:1px solid rgba(120,180,255,.35);display:flex;align-items:center;padding:0 28px;overflow:hidden}
#titleTxt{font-size:38px;font-weight:800;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.6);white-space:nowrap}
#picBox{position:relative;width:1000px;height:620px;border-radius:24px;overflow:hidden;
 border:1px solid rgba(120,180,255,.3);box-shadow:0 18px 60px rgba(0,0,0,.55);background:#000}
#picBox img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover;transition:none}
#flash{position:absolute;inset:0;background:#dff1ff;opacity:0;pointer-events:none}
#card{position:absolute;left:40px;right:40px;bottom:14px;height:104px;border-radius:16px;
 background:rgba(8,16,34,.82);backdrop-filter:blur(10px);border:1px solid rgba(255,204,64,.45);
 display:flex;align-items:center;justify-content:center;padding:0 24px}
#cardTxt{font-size:27px;font-weight:700;color:#ffe9a8;letter-spacing:1px;white-space:nowrap}
#segBadge{position:absolute;top:22px;right:26px;z-index:6;background:rgba(255,77,109,.92);color:#fff;
 font-size:30px;font-weight:900;padding:8px 22px;border-radius:14px;box-shadow:0 6px 18px rgba(255,77,109,.4)}
/* 底部 30% */
#stageBot{position:absolute;bottom:0;left:0;right:0;height:459px;
 background:linear-gradient(180deg,rgba(10,16,34,.0),rgba(8,12,28,.88) 30%)}
#fish{position:absolute;right:8px;bottom:-14px;height:470px;filter:drop-shadow(0 0 24px rgba(64,140,255,.35))}
#bubble{position:absolute;left:40px;bottom:74px;width:560px;min-height:150px;padding:24px 30px;
 background:linear-gradient(135deg,rgba(37,66,120,.92),rgba(28,48,96,.92));
 border:2px solid rgba(125,211,252,.55);border-radius:26px;border-bottom-left-radius:6px;
 box-shadow:0 14px 40px rgba(0,0,0,.5)}
#subNow{font-size:36px;font-weight:800;color:#ffffff;line-height:1.45}
#subPrev{font-size:26px;color:#9fc3ef;opacity:.55;line-height:1.4;margin-top:10px;max-height:76px;overflow:hidden}
#dots{position:absolute;left:40px;bottom:26px;color:#5f87c7;font-size:22px;letter-spacing:2px}
</style></head><body><div id="stage">
<canvas id="rain" width="1080" height="1528"></canvas><div id="vig"></div>
<div id="banner"><div id="logo">🐟 大肥鱼的<em>科技日报</em></div><div id="wave"></div>
<div id="date">__DATE__<br>Linux.do 热榜精读</div></div>
<div id="stageMid">
 <div id="segBadge">__BADGE__</div>
 <div id="titleBar"><div id="titleTxt"></div></div>
 <div id="picBox"><img id="pic"><div id="flash"></div></div>
 <div id="card"><div id="cardTxt"></div></div>
</div>
<div id="stageBot"><img id="fish"><div id="bubble"><div id="subNow"></div><div id="subPrev"></div></div>
<div id="dots">● ● ● ● ● ●</div></div>
</div>
<script>
const DATA = __DATA__;
const IMG = "__WS__/selected_images";
const FEI = "__FEIYU__";
const $ = id => document.getElementById(id);
// 预载所有图
const pics = [...new Set(DATA.segments.map(s => s.pic))];
const imgs = [...new Set(DATA.segments.map(s => s.img))];
const cache = {};
[...pics.map(p => IMG + "/" + p + ".png"), ...imgs.map(i => FEI + "/" + i + ".png")].forEach(u => {
  const im = new Image(); im.src = u; cache[u] = im;
});
// 波形条
const waveBox = $("wave"); const bars = [];
for (let i = 0; i < 26; i++) { const b = document.createElement("i"); b.style.height = "6px"; waveBox.appendChild(b); bars.push(b); }
// 代码雨
const rc = $("rain").getContext("2d");
const cols = [];
for (let i = 0; i < 34; i++) cols.push({ x: i * 32 + 6, sp: 60 + (i * 53 % 7) * 34, txt: Array.from({length: 18}, () => Math.random().toString(36)[2 % 36 === 0 ? 0 : Math.floor(Math.random() * 26 + 10)] || "0") });
function drawRain(t) {
  rc.clearRect(0, 0, 1080, 1528);
  rc.font = "17px Consolas,monospace";
  for (const c of cols) {
    const off = (t * c.sp) % 900;
    for (let k = 0; k < 14; k++) {
      const y = ((off + k * 46) % 1600) - 60;
      rc.fillStyle = k === 0 ? "rgba(140,255,220,.9)" : "rgba(70,170,255," + (0.55 - k * 0.04) + ")";
      rc.fillText(c.txt[(k + Math.floor(t * 2 + c.x)) % 18], c.x, y);
    }
  }
}
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
function seek(t) {
  // 当前段
  let si = 0;
  for (let i = 0; i < DATA.segments.length; i++) if (t >= DATA.segments[i].start) si = i;
  const seg = DATA.segments[si];
  const p = clamp((t - seg.start) / seg.dur, 0, 1);
  const tin = clamp((t - seg.start) / 0.45, 0, 1);           // 段进入进度
  // 顶部波形（真实人声包络）
  const fi = Math.floor(t * DATA.fps);
  for (let i = 0; i < bars.length; i++) {
    const v = DATA.wave[clamp(fi - i * 2, 0, DATA.wave.length - 1)] || 0;
    bars[i].style.height = (5 + v * 56) + "px";
  }
  // 中部
  $("segBadge").textContent = seg.key.startsWith("n") ? ("TOP " + seg.key.slice(1)) : (seg.key === "t1" || seg.key === "t2" ? "小白练手" : "");
  $("titleTxt").textContent = seg.title;
  $("titleBar").style.opacity = tin;
  $("titleBar").style.transform = "translateY(" + (1 - tin) * -16 + "px)";
  const picEl = $("pic");
  const wantSrc = IMG + "/" + seg.pic + ".png";
  if (!picEl.src.endsWith(seg.pic + ".png")) { picEl.src = wantSrc; }
  // Ken Burns
  const ks = 1.06 + 0.10 * p, kx = -18 * p, ky = 10 * p;
  picEl.style.transform = "scale(" + ks + ") translate(" + kx + "px," + ky + "px)";
  picEl.style.opacity = tin;
  $("flash").style.opacity = clamp(1 - (t - seg.start) / 0.28, 0, 1) * 0.55;
  // 指标卡（长文本自适应字号，防溢出）
  if (seg.card) {
    const cin = clamp((t - seg.start - 1.05) / 0.4, 0, 1);
    $("card").style.opacity = cin;
    $("card").style.transform = "translateY(" + (1 - cin) * 40 + "px)";
    $("cardTxt").textContent = seg.card;
    $("cardTxt").style.fontSize = (seg.card.length > 40 ? 19 : seg.card.length > 32 ? 22 : 26) + "px";
  } else { $("card").style.opacity = 0; }
  // 底部立绘：呼吸 + 说话微颤 + 切换淡入
  const fish = $("fish");
  const fsrc = FEI + "/" + seg.img + ".png";
  if (!fish.src.endsWith(seg.img + ".png")) fish.src = fsrc;
  // 当前字幕
  let cur = null, prev = null;
  for (const s of DATA.subtitles) {
    if (t >= s.start - 0.05 && t <= s.end + 0.25) cur = s;
    else if (t > s.end + 0.25 && t - s.end < 6) prev = s;
  }
  const speaking = !!cur;
  const bob = Math.sin(t * 2.1) * 7;
  const jit = speaking ? Math.sin(t * 41) * 2.2 : 0;
  const sc = 1 + (speaking ? 0.012 * Math.sin(t * 23) : 0);
  fish.style.transform = "translateY(" + (bob + jit) + "px) scale(" + sc + ")";
  fish.style.opacity = clamp((t - seg.start) / 0.35, 0, 1);
  $("subNow").textContent = cur ? cur.text : "";
  $("subPrev").textContent = prev ? prev.text : "";
  $("bubble").style.opacity = cur ? 1 : 0.55;
  drawRain(t);
}
window.seek = seek;
</script></body></html>"""


def main():
    tl = json.loads((WS / "timeline.json").read_text(encoding="utf-8"))
    total = tl["total"]
    env = voice_envelope(FPS)
    html = (HTML.replace("__DATA__", json.dumps(
        {"fps": FPS, "wave": [round(x, 3) for x in env], "segments": tl["segments"],
         "subtitles": tl["subtitles"]}, ensure_ascii=False))
        .replace("__WS__", WS.as_posix())
        .replace("__FEIYU__", (REPO_ROOT / "data" / "feiyu_assets" / "selected").as_posix())
        .replace("__DATE__", DATE))
    page_html = WS / "render.html"
    page_html.write_text(html, encoding="utf-8")

    FRAMES.mkdir(exist_ok=True)
    for old in FRAMES.glob("*.jpg"):
        old.unlink()

    from playwright.sync_api import sync_playwright
    preview = len(sys.argv) > 2 and sys.argv[2] == "preview"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(page_html.as_uri())
        page.wait_for_timeout(1200)  # 预载图片
        if preview:
            for t in (2.0, 30.0, 63.0, 250.0):
                page.evaluate(f"seek({t})")
                page.wait_for_timeout(150)
                page.screenshot(path=str(WS / f"preview_t{int(t)}.jpg"), type="jpeg", quality=88)
                print(f"[preview] t={t}s")
            browser.close()
            print("[ok] preview done")
            return
        n_frames = int(total * FPS)
        for i in range(n_frames):
            page.evaluate(f"seek({i / FPS:.4f})")
            page.screenshot(path=str(FRAMES / f"f{i:05d}.jpg"), type="jpeg", quality=90)
            if i % 300 == 0:
                print(f"[frame] {i}/{n_frames} ({i / FPS:.0f}s)", flush=True)
        browser.close()

    out = WS / f"大肥鱼的科技日报_{DATE}.mp4"
    subprocess.run([find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                    "-framerate", str(FPS), "-i", str(FRAMES / "f%05d.jpg"),
                    "-i", str(WS / "audio_final.wav"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(out)], check=True)
    print(f"[ok] 成片 -> {out} ({out.stat().st_size // 1048576}MB)")


if __name__ == "__main__":
    main()
