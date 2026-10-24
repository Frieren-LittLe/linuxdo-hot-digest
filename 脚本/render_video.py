# -*- coding: utf-8 -*-
"""《大肥鱼的科技日报》第 4 步：$1:\\sqrt{2}$ 竖屏（1080x1528）动画渲染 v2。

v2 变化：Q 版透明底立绘（selected_cut）、DeepSeek 品牌蓝深海背景（鲸鱼剪影/气泡/Token 金币/水印）、
插图拍立得贴纸卡、BGM CC-BY 署名。仍为时间驱动 seek(t) + 逐帧截图 + FFmpeg 合成。

用法: python 脚本/render_video.py [YYYY-MM-DD] [preview]
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
#stage{position:relative;width:1080px;height:1528px;
 background:linear-gradient(168deg,#0a0f2e 0%,#122466 46%,#0a1533 100%)}
#ocean{position:absolute;inset:0}
#rain{position:absolute;inset:0;opacity:.16}
#vig{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,transparent 52%,rgba(2,6,26,.6) 100%);pointer-events:none}
#wm{position:absolute;right:-90px;bottom:-60px;width:760px;opacity:.09;z-index:1;pointer-events:none}
/* 顶部横幅 12% */
#banner{position:absolute;top:0;left:0;right:0;height:183px;padding:20px 36px;
 background:linear-gradient(90deg,rgba(20,38,110,.72),rgba(16,28,80,.55));backdrop-filter:blur(14px);
 border-bottom:2px solid rgba(77,107,254,.55);display:flex;align-items:center;gap:24px;z-index:5}
#logo{font-size:44px;font-weight:900;color:#f2f7ff;letter-spacing:2px;text-shadow:0 0 26px rgba(77,107,254,.95)}
#logo em{font-style:normal;color:#7d9bff}
#date{margin-left:auto;text-align:right;color:#9db4f0;font-size:24px;line-height:1.5}
#wave{display:flex;align-items:flex-end;gap:5px;height:64px;padding:0 8px}
#wave i{display:block;width:7px;background:linear-gradient(180deg,#9db4f0,#4d6bfe);border-radius:3px;box-shadow:0 0 8px rgba(77,107,254,.8)}
/* 中部展台 58% */
#stageMid{position:absolute;top:183px;left:0;right:0;height:886px;padding:26px 40px 0}
#titleBar{position:relative;height:96px;margin-bottom:20px;border-radius:18px;
 background:linear-gradient(90deg,rgba(77,107,254,.34),rgba(77,107,254,.05));
 border:1px solid rgba(140,165,255,.4);display:flex;align-items:center;padding:0 28px}
#titleTxt{font-size:37px;font-weight:800;color:#fff;text-shadow:0 2px 10px rgba(0,0,20,.7);white-space:nowrap}
#polaroid{position:relative;width:940px;margin:0 auto;height:618px;background:#f6f8ff;border-radius:10px;
 padding:14px 14px 44px;box-shadow:0 20px 70px rgba(0,0,10,.65),0 0 0 1px rgba(150,170,255,.25);
 transition:none}
#picBox{position:relative;width:100%;height:100%;border-radius:6px;overflow:hidden;background:#000}
#picBox img{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}
#flash{position:absolute;inset:0;background:#e7efff;opacity:0;pointer-events:none}
#tape{position:absolute;top:-18px;left:46%;width:130px;height:38px;background:rgba(255,214,90,.85);
 transform:rotate(-3deg);border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.35)}
#card{position:absolute;left:40px;right:40px;bottom:8px;height:100px;border-radius:16px;
 background:rgba(10,18,44,.86);backdrop-filter:blur(10px);border:1px solid rgba(255,204,64,.5);
 display:flex;align-items:center;justify-content:center;padding:0 24px}
#cardTxt{font-size:25px;font-weight:700;color:#ffe9a8;white-space:nowrap}
#segBadge{position:absolute;top:22px;right:26px;z-index:6;background:linear-gradient(90deg,#ff4d6d,#ff7a5c);color:#fff;
 font-size:30px;font-weight:900;padding:8px 22px;border-radius:14px;box-shadow:0 6px 18px rgba(255,77,109,.45)}
/* 底部 30% */
#stageBot{position:absolute;bottom:0;left:0;right:0;height:459px;
 background:linear-gradient(180deg,rgba(10,18,46,0),rgba(7,12,34,.9) 32%)}
#fish{position:absolute;right:6px;bottom:-10px;height:440px;filter:drop-shadow(0 0 26px rgba(77,107,254,.5)) drop-shadow(0 10px 18px rgba(0,0,10,.45))}
#bubble{position:absolute;left:40px;bottom:70px;width:560px;min-height:150px;padding:24px 30px;
 background:linear-gradient(135deg,rgba(46,72,150,.94),rgba(30,50,110,.94));
 border:2px solid rgba(140,180,255,.6);border-radius:26px;border-bottom-left-radius:6px;
 box-shadow:0 14px 40px rgba(0,0,10,.55)}
#subNow{font-size:36px;font-weight:800;color:#fff;line-height:1.45}
#subPrev{font-size:25px;color:#a9c3f2;opacity:.55;line-height:1.4;margin-top:10px;max-height:72px;overflow:hidden}
#credit{position:absolute;left:40px;bottom:22px;color:#5c7bc4;font-size:17px;letter-spacing:.5px}
</style></head><body><div id="stage">
<canvas id="ocean" width="1080" height="1528"></canvas>
<canvas id="rain" width="1080" height="1528"></canvas>
<img id="wm"><div id="vig"></div>
<div id="banner"><div id="logo">🐟 大肥鱼的<em>科技日报</em></div><div id="wave"></div>
<div id="date">__DATE__<br>Linux.do 热榜精读</div></div>
<div id="stageMid">
 <div id="segBadge"></div>
 <div id="titleBar"><div id="titleTxt"></div></div>
 <div id="polaroid"><div id="tape"></div><div id="picBox"><img id="pic"><div id="flash"></div></div></div>
 <div id="card"><div id="cardTxt"></div></div>
</div>
<div id="stageBot"><img id="fish"><div id="bubble"><div id="subNow"></div><div id="subPrev"></div></div>
<div id="credit">BGM: 2tech-audio “Event” / mixaund “Dreamers” · free-stock-music.com · CC BY 3.0</div></div>
</div>
<script>
const DATA = __DATA__;
const IMG = "__WS__/selected_images";
const FEI = "__FEIYU__";
const WM = "__FEIYU__/token_01.png";
const $ = id => document.getElementById(id);
const cache = {};
[...new Set(DATA.segments.map(s => IMG + "/" + s.pic + ".png")),
 ...new Set(DATA.segments.map(s => FEI + "/" + s.img + ".png")), WM].forEach(u => {
  const im = new Image(); im.src = u; cache[u] = im;
});
$("wm").src = WM;
const waveBox = $("wave"); const bars = [];
for (let i = 0; i < 26; i++) { const b = document.createElement("i"); b.style.height = "6px"; waveBox.appendChild(b); bars.push(b); }
/* 深海层：鲸鱼剪影 + 气泡 + Token 金币 */
const oc = $("ocean").getContext("2d");
const bubbles = Array.from({length: 20}, (_, i) => ({x: (i * 173 + 40) % 1080, r: 3 + (i * 7) % 7, sp: 26 + (i * 13) % 34, ph: i * 137}));
const coins = Array.from({length: 9}, (_, i) => ({x: (i * 233 + 90) % 1080, sp: 15 + (i * 11) % 20, ph: i * 71, r: 13 + (i * 5) % 6}));
function drawWhale(x, y, s, alpha, flip, t) {
  oc.save(); oc.translate(x, y + Math.sin(t * .7 + x) * 14); oc.scale(flip ? -s : s, s);
  oc.globalAlpha = alpha; oc.fillStyle = "#3560e0";
  oc.beginPath();
  oc.moveTo(-85, 0);
  oc.quadraticCurveTo(-45, -42, 25, -38);
  oc.quadraticCurveTo(80, -33, 92, -6);
  oc.quadraticCurveTo(58, 6, 18, 9);
  oc.quadraticCurveTo(-25, 13, -58, 24);
  oc.lineTo(-96, 44); oc.lineTo(-72, 8); oc.lineTo(-98, -10);
  oc.closePath(); oc.fill();
  oc.beginPath(); oc.ellipse(8, 20, 22, 9, .45, 0, 7); oc.fill();
  oc.restore();
}
function drawOcean(t) {
  oc.clearRect(0, 0, 1080, 1528);
  // 光柱
  const g = oc.createLinearGradient(0, 0, 0, 900);
  g.addColorStop(0, "rgba(120,150,255,.16)"); g.addColorStop(1, "rgba(120,150,255,0)");
  oc.fillStyle = g;
  for (let i = 0; i < 3; i++) {
    oc.beginPath(); oc.moveTo(180 + i * 340, 0);
    oc.lineTo(320 + i * 340, 0); oc.lineTo(460 + i * 340, 900); oc.lineTo(140 + i * 340, 900);
    oc.closePath(); oc.fill();
  }
  drawWhale(((t * 26) % 1500) - 260, 420, 1.5, .26, false, t);
  drawWhale(1080 - ((t * 17) % 1500) + 200, 1050, .9, .20, true, t + 3);
  // 气泡
  oc.strokeStyle = "rgba(200,222,255,.85)"; oc.lineWidth = 2.2;
  for (const b of bubbles) {
    const y = 1528 - ((t * b.sp + b.ph) % 1620);
    oc.beginPath(); oc.arc(b.x + Math.sin(t * 1.3 + b.ph) * 10, y, b.r, 0, 7); oc.stroke();
  }
  // Token 金币
  oc.font = "bold " + 16 + "px Consolas,monospace"; oc.textAlign = "center"; oc.textBaseline = "middle";
  for (const c of coins) {
    const y = 1528 - ((t * c.sp + c.ph) % 1680);
    const x = c.x + Math.sin(t * .9 + c.ph) * 16;
    oc.globalAlpha = .9;
    oc.beginPath(); oc.arc(x, y, c.r, 0, 7);
    oc.fillStyle = "#ffd76a"; oc.fill();
    oc.strokeStyle = "#c9971f"; oc.lineWidth = 2; oc.stroke();
    oc.fillStyle = "#7a5410"; oc.fillText("T", x, y + 1);
    oc.globalAlpha = 1;
  }
}
/* 代码雨 */
const rc = $("rain").getContext("2d");
const colsR = [];
for (let i = 0; i < 30; i++) colsR.push({ x: i * 36 + 8, sp: 70 + (i * 53 % 7) * 30, txt: Array.from({length: 16}, () => (Math.random() * 36 + 10 | 0).toString(36)) });
function drawRain(t) {
  rc.clearRect(0, 0, 1080, 1528);
  rc.font = "16px Consolas,monospace";
  for (const c of colsR) {
    const off = (t * c.sp) % 860;
    for (let k = 0; k < 12; k++) {
      const y = ((off + k * 44) % 1500) - 40;
      rc.fillStyle = k === 0 ? "rgba(160,255,230,.8)" : "rgba(90,160,255," + (0.5 - k * 0.04) + ")";
      rc.fillText(c.txt[(k + (t * 2 | 0) + c.x) % 16], c.x, y);
    }
  }
}
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
function seek(t) {
  let si = 0;
  for (let i = 0; i < DATA.segments.length; i++) if (t >= DATA.segments[i].start) si = i;
  const seg = DATA.segments[si];
  const p = clamp((t - seg.start) / seg.dur, 0, 1);
  const tin = clamp((t - seg.start) / 0.45, 0, 1);
  const fi = Math.floor(t * DATA.fps);
  for (let i = 0; i < bars.length; i++) {
    const v = DATA.wave[clamp(fi - i * 2, 0, DATA.wave.length - 1)] || 0;
    bars[i].style.height = (5 + v * 56) + "px";
  }
  $("segBadge").textContent = seg.key.startsWith("n") ? ("TOP " + seg.key.slice(1)) : (seg.key === "t1" || seg.key === "t2" ? "小白练手" : "");
  $("titleTxt").textContent = seg.title;
  $("titleBar").style.opacity = tin;
  $("titleBar").style.transform = "translateY(" + (1 - tin) * -16 + "px)";
  const picEl = $("pic");
  if (!picEl.src.endsWith(seg.pic + ".png")) picEl.src = IMG + "/" + seg.pic + ".png";
  const ks = 1.06 + 0.10 * p;
  picEl.style.transform = "scale(" + ks + ") translate(" + (-16 * p) + "px," + (9 * p) + "px)";
  picEl.style.opacity = tin;
  // 拍立得贴纸：每段交替微旋转 + 切镜弹入
  const rot = (si % 2 === 0 ? 1 : -1) * (0.9 + (si % 3) * 0.25);
  const pop = 0.94 + 0.06 * clamp((t - seg.start) / 0.4, 0, 1);
  $("polaroid").style.transform = "rotate(" + rot + "deg) scale(" + pop + ")";
  $("flash").style.opacity = clamp(1 - (t - seg.start) / 0.28, 0, 1) * 0.5;
  if (seg.card) {
    const cin = clamp((t - seg.start - 1.05) / 0.4, 0, 1);
    $("card").style.opacity = cin;
    $("card").style.transform = "translateY(" + (1 - cin) * 40 + "px)";
    $("cardTxt").textContent = seg.card;
    $("cardTxt").style.fontSize = (seg.card.length > 40 ? 19 : seg.card.length > 32 ? 22 : 25) + "px";
  } else { $("card").style.opacity = 0; }
  // Q 版立绘：呼吸 + 说话 Q 弹 + 切换弹跳登场
  const fish = $("fish");
  if (!fish.src.endsWith(seg.img + ".png")) fish.src = FEI + "/" + seg.img + ".png";
  let cur = null, prev = null;
  for (const s of DATA.subtitles) {
    if (t >= s.start - 0.05 && t <= s.end + 0.25) cur = s;
    else if (t > s.end + 0.25 && t - s.end < 6) prev = s;
  }
  const speaking = !!cur;
  const bob = Math.sin(t * 2.3) * 8;
  const jit = speaking ? Math.sin(t * 42) * 2.4 : 0;
  const bounceIn = 1 + 0.18 * Math.sin(clamp((t - seg.start) / 0.5, 0, 1) * Math.PI) * (1 - clamp((t - seg.start) / 0.5, 0, 1));
  const sc = (1 + (speaking ? 0.016 * Math.sin(t * 24) : 0)) * bounceIn;
  fish.style.transform = "translateY(" + (bob + jit) + "px) scale(" + sc + ")";
  fish.style.opacity = clamp((t - seg.start) / 0.3, 0, 1);
  $("subNow").textContent = cur ? cur.text : "";
  $("subPrev").textContent = prev ? prev.text : "";
  $("bubble").style.opacity = cur ? 1 : 0.6;
  drawOcean(t);
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
        .replace("__FEIYU__", (REPO_ROOT / "data" / "feiyu_assets" / "selected_cut").as_posix())
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
        page.wait_for_timeout(1200)
        if preview:
            for t in (2.0, 30.0, 63.0, 250.0):
                page.evaluate(f"seek({t})")
                page.wait_for_timeout(150)
                page.screenshot(path=str(WS / f"preview_t{int(t)}.jpg"), type="jpeg", quality=88)
                print(f"[preview] t={t}s")
            browser.close()
            print("[ok] preview done")
            return
        browser.close()  # 关闭预载用的初始会话，渲染改为分段重启
        n_frames = int(total * FPS)
        RESTART_EVERY = 1200  # 分段重启浏览器，防长会话内存累积导致渲染进程崩溃
        i = 0
        while i < n_frames:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(page_html.as_uri())
            page.wait_for_timeout(1500)
            j_end = min(i + RESTART_EVERY, n_frames)
            for k in range(i, j_end):
                fp = FRAMES / f"f{k:05d}.jpg"
                if fp.exists():
                    continue  # 断点续渲
                page.evaluate(f"seek({k / FPS:.4f})")
                page.screenshot(path=str(fp), type="jpeg", quality=90)
                if k % 300 == 0:
                    print(f"[frame] {k}/{n_frames} ({k / FPS:.0f}s)", flush=True)
            browser.close()
            print(f"[seg] {i}-{j_end} 完成", flush=True)
            i = j_end

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
