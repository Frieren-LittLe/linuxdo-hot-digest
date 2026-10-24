# -*- coding: utf-8 -*-
"""《大肥鱼的科技日报》第 3 步音频流水线：TTS 分段配音 -> SRT 字幕 -> 混音。

输入: script_draft.md 的段落文本（内嵌本文件）
输出(工作目录 data/video_workspace/<date>/):
  voice/seg_*.mp3 + seg_*.wav   每段配音
  audio_final.wav               混音成品（BGM 闪避 + 音效）
  subtitles.srt                 全片字幕
  timeline.json                 段落时间轴（渲染器输入）
"""
import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-23"
WS = REPO_ROOT / "data" / "video_workspace" / DATE
VOICE = WS / "voice"
SR = 44100

VOICE_NAME = "zh-CN-XiaoyiNeural"
RATE = "+15%"
PROXY = "http://127.0.0.1:7897"

# 段落：img=Q版主立绘(selected_cut), pic=主视觉插图, title=切镜标题, card=指标卡文本
SEGS = [
    {"key": "hook", "img": "normal_06", "pic": "1A", "title": "PHP 出大事了！半个互联网连夜加班", "card": "", "gap_after": 0.9,
     "text": "这两天程序员圈炸锅了！一个用了三十年的老技术出了天大的漏洞，半个互联网的网站连夜抢修。别怕，我是大肥鱼，今天带你们看戏加捡漏，开饭！"},
    {"key": "n1", "img": "shock_05", "pic": "1A", "title": "网站漏洞爆发，Cloudflare 免费帮你挡", "card": "上手难度 ★★☆☆☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：Cloudflare 防火墙 / 原帖 3054943", "gap_after": 1.0,
     "text": "先说这个漏洞有多狠。PHP，全球一大半网站背后的老技术，前两天被扒出两个大洞：坏人看一眼你的网站，就能直接在你的电脑上乱敲命令。修漏洞要时间，等不及的怎么办？Cloudflare，就是帮网站挡流量的那家公司，火速上线了免费防火墙规则，把坏人拦在门外。但你得做一件事：把你服务器的门牌号藏好，只让 Cloudflare 进得来，不然坏人绕后门，规则就白搭了。一句话总结：规则开起来，补丁抓紧打。"},
    {"key": "n2", "img": "speechless_04", "pic": "2A", "title": "网上全是假黑客？佬友亲测别慌", "card": "上手难度 ★★★☆☆ ｜ 白嫖指数 ★★☆☆☆ ｜ 核心指路：应急复盘 / 原帖 3065907", "gap_after": 1.0,
     "text": "还是这个漏洞的后续。网上突然冒出一堆人喊：我能一秒黑掉你的网站！吓得好多站长连夜关门。有位佬友冷静下来研究发现：真能用的攻击代码，每台服务器长得都不一样，拿来乱打，大概率先把你自己服务器搞崩。所以大部分小网站真不用慌着关站。还有个细节特别真实：他去问了一圈 AI 助手，个个都说事态紧急赶紧停机，结果自己一算，根本不用停。AI 给个参考可以，拿主意还得是你自己。"},
    {"key": "n3", "img": "laugh_05", "pic": "3B", "title": "用 AI 做婚礼视频，三天赚回订阅费", "card": "上手难度 ★★★☆☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：开源 VVV 工具 / 原帖 3064156", "gap_after": 1.0,
     "text": "这位佬友要结婚，婚礼要放个暖场视频，外面做一条五十块。他一拍脑袋：我自己有 AI，凭什么花钱？把找来的参考视频、音乐、婚纱照，一股脑全丢给 Claude 照着做，缺什么图就再让 AI 画。做完顺手挂到二手平台上卖，两三天接了六单，订阅费赚回来了还有富余。他还把整套方法做成了免费开源工具，人人能用。想学的记住一句话：模板才是宝贝，AI 只是打工的。"},
    {"key": "n4", "img": "geek_03", "pic": "4B", "title": "换个聊天窗口，AI 就把你忘了？", "card": "上手难度 ★★☆☆☆ ｜ 白嫖指数 ★★★★★ ｜ 核心指路：knowledge-project / 原帖 3062753", "gap_after": 1.0,
     "text": "天天用 AI 干活的佬友肯定懂这个痛苦：换个窗口，AI 就把你忘得一干二净，什么都得从头交代。这位佬友的解决办法特别简单：给项目写两份文档。一份写我们要干什么、定过什么规矩；另一份写干到哪了、下一步干啥。AI 每次开工先读这两份文档，立马接上进度。全部免费开源，一条命令装好。记住这句话：聊天记录会丢，写下来的才算数。"},
    {"key": "n5", "img": "geek_01", "pic": "5C", "title": "老电视开机两分钟？21 秒搞定", "card": "上手难度 ★★★★☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：开源工具 REA / 原帖 3064579", "gap_after": 0.9,
     "text": "家里 2019 年买的小米电视，开机要干等两分钟？这位佬友没换新电视，也没拆机刷机，就是用电脑连上电视，把系统里偷偷自启动的软件一个个揪出来关掉，开机时间从两分钟压到二十一秒。用的工具还是免费开源的。提醒两个坑：电视一重启，调试开关会自己关掉，得重新打开；系统桌面换不掉，别白费劲。家里有老电视老盒子的，先抢救一轮再考虑买新的。"},
    {"key": "t1", "img": "token_03", "pic": "6A", "title": "白嫖时间！注册就送 10 亿 Token", "card": "上手难度 ★★☆☆☆ 需实名 ｜ 白嫖指数 ★★★★★ ｜ 核心指路：讯飞星辰 MaaS / 原帖 3060920", "gap_after": 0.6, "bgm": "cute",
     "text": "又到了白嫖时间！讯飞开放了大模型平台，新用户注册就送十亿 Token。十亿什么概念？天天写代码、做小工具，一个月都用不完。三步搞定：第一步，搜讯飞星辰，手机号注册。第二步，做个实名认证，这是唯一的门槛，不想提交身份信息的，这期跳过就好。第三步，进活动页，十亿 Token 直接到账！"},
    {"key": "t2", "img": "token_01", "pic": "6A", "title": "记得用完，过期不补！", "card": "", "gap_after": 0,
     "text": "敲黑板：额度只有三十一天有效期，只能用讯飞自家的模型，领了就赶紧用，过期不补！好了，今天的白饭，肥鱼吃饱了。明晚九点，我们不见不散，拜拜！"},
]


def find_ffmpeg():
    for p in (REPO_ROOT / "data" / "bin").rglob("ffmpeg.exe"):
        return str(p)
    return "ffmpeg"


def run_ff(args):
    r = subprocess.run([find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"] + args,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-600:])


def mp3_duration(path):
    tmp = Path(str(path) + ".chk.wav")
    run_ff(["-i", str(path), "-ar", str(SR), "-ac", "1", str(tmp)])
    d = len(read_wav(tmp)) / SR
    tmp.unlink()
    return d


async def tts_one(text, mp3_path, words_path):
    """edge 合成 + 完整性校验：音频时长必须覆盖词边界末尾，否则重试（防截断）。"""
    import edge_tts
    for attempt in range(4):
        c = edge_tts.Communicate(text, VOICE_NAME, rate=RATE, boundary="WordBoundary")
        audio = bytearray()
        words = []
        async for chunk in c.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"], "d": chunk["duration"], "w": chunk["text"]})
        mp3_path.write_bytes(audio)
        words_path.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        words_end = max((w["t"] + w["d"]) for w in words) / 1e7 if words else 0
        dur = mp3_duration(mp3_path)
        if dur >= words_end - 1.0:
            return
        print(f"[warn] 截断检测：音频 {dur:.1f}s < 词边界 {words_end:.1f}s，重试{attempt + 1}", flush=True)
        await asyncio.sleep(3)
    raise RuntimeError(f"TTS 反复截断: {mp3_path.name}")


def mp3_to_wav_mono(mp3, wav):
    run_ff(["-i", str(mp3), "-ar", str(SR), "-ac", "1", str(wav)])


def read_wav(path):
    with wave.Wave_read(str(path)) as w:
        assert w.getframerate() == SR, f"{path} 采样率 {w.getframerate()} != {SR}"
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768
        if w.getnchannels() == 2:
            raw = raw.reshape(-1, 2).mean(axis=1)  # 立体声转单声道
        return raw


def write_wav(path, data, gain=1.0):
    data = data / (np.abs(data).max() + 1e-9) * gain
    pcm = (data * 32767).astype(np.int16)
    with wave.Wave_write(str(path)) as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def words_to_srt(words, seg_start, idx_start):
    """WordBoundary 流 -> 按标点聚合的句级字幕。"""
    sents, cur, cur_t0, cur_t1 = [], "", None, None
    PUNCT = "？！。；：，…、"
    for w in words:
        if cur_t0 is None:
            cur_t0 = w["t"]
        cur += w["w"]
        cur_t1 = w["t"] + w["d"]
        if (w["w"] and w["w"][-1] in "？！。；：…") or len(cur) >= 26:
            sents.append((cur_t0, cur_t1, cur))
            cur, cur_t0 = "", None
    if cur:
        sents.append((cur_t0, cur_t1, cur))
    out = []
    for i, (t0, t1, s) in enumerate(sents):
        st = seg_start + t0 / 1e7
        en = seg_start + t1 / 1e7 + 0.12
        if en <= st:
            en = st + 0.6
        out.append({"i": idx_start + i, "start": st, "end": en, "text": s})
    return out, idx_start + len(sents)


def fmt_ts(x):
    h, m = int(x // 3600), int(x % 3600 // 60)
    s, ms = int(x % 60), int(x * 1000 % 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


FISH_KEY_FILE = REPO_ROOT / "data" / "fish_api_key.txt"
FISH_VOICE_ID = "fe50cdf3040449298470d58ff0991e1d"  # FishAudio「蓝色大肥鱼」
FISH_TTS_URL = "https://api.fish.audio/v1/tts"


def fish_key():
    return FISH_KEY_FILE.read_text(encoding="utf-8").strip() if FISH_KEY_FILE.exists() else ""


def split_sentences(text):
    """按标点切句（短句合并到 ~18 字），供逐句 TTS 与句级字幕。"""
    import re as _re
    parts = [p for p in _re.split(r"(?<=[？！。；…])", text) if p.strip()]
    merged, cur = [], ""
    for p in parts:
        if len(cur) + len(p) <= 18 or not cur:
            cur += p
        else:
            merged.append(cur)
            cur = p
    if cur:
        merged.append(cur)
    return merged


def fish_tts_sentence(text, out_path, retries=3):
    """FishAudio TTS 单句合成 -> mp3 文件。"""
    import urllib.request
    for i in range(retries):
        try:
            body = json.dumps({"text": text, "reference_id": FISH_VOICE_ID,
                               "format": "mp3", "mp3_bitrate": "128",
                               "chunk_length": 200, "normalize": True}).encode("utf-8")
            req = urllib.request.Request(FISH_TTS_URL, data=body, headers={
                "Authorization": f"Bearer {fish_key()}",
                "Content-Type": "application/json"})
            with urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})).open(req, timeout=120) as r:
                data = r.read()
            if len(data) < 2000:
                raise RuntimeError(f"audio too small ({len(data)}B)")
            Path(out_path).write_bytes(data)
            return
        except Exception as e:
            print(f"[warn] fish tts 重试{i+1}: {e}", flush=True)
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"FishAudio 合成失败: {text[:30]}")


def main():
    VOICE.mkdir(parents=True, exist_ok=True)
    # 1. TTS（fish: 逐句合成并产出句文件清单；edge: 整段合成+词边界；manual: E1 手动mp3）
    MANUAL = WS / "manual_tts"
    manual_files = {p.stem.replace("seg_", ""): p for p in MANUAL.glob("seg_*.mp3")} if MANUAL.exists() else {}
    if manual_files:
        print(f"[info] manual 引擎：检测到 {len(manual_files)} 段手动音频（字幕将线性对齐实际时长）")
    use_fish = bool(fish_key()) and not manual_files
    if not manual_files:
        print(f"[info] TTS 引擎: {'FishAudio 蓝色大肥鱼' if use_fish else 'edge-tts ' + VOICE_NAME}")
    for seg in SEGS:
        marker = VOICE / f"seg_{seg['key']}.done"
        if marker.exists():
            print(f"[skip] {seg['key']} 已合成")
            continue
        if use_fish:
            print(f"[tts-fish] {seg['key']} ({len(seg['text'])}字)", flush=True)
            sents = split_sentences(seg["text"])
            lines = []
            for i, s in enumerate(sents):
                out = VOICE / f"seg_{seg['key']}_s{i:02d}.mp3"
                fish_tts_sentence(s, out)
                lines.append(s)
                time.sleep(1)
            (VOICE / f"seg_{seg['key']}.sentences.json").write_text(
                json.dumps(lines, ensure_ascii=False), encoding="utf-8")
            # 拼成整段 mp3（ffmpeg concat）
            lst = VOICE / f"seg_{seg['key']}.txt"
            lst.write_text("\n".join(f"file 'seg_{seg['key']}_s{i:02d}.mp3'" for i in range(len(lines))), encoding="utf-8")
            run_ff(["-f", "concat", "-safe", "0", "-i", str(lst), "-c:a", "libmp3lame", "-q:a", "3",
                    str(VOICE / f"seg_{seg['key']}.mp3")])
            (VOICE / f"seg_{seg['key']}.words.json").unlink(missing_ok=True)
        else:
            raw = VOICE / f"seg_{seg['key']}.raw.mp3"
            if seg["key"] in manual_files:
                # manual 引擎：edge 只出词边界时间轴，音频换成手动合成的 E1 mp3
                if not (VOICE / f"seg_{seg['key']}.words.json").exists():
                    asyncio.run(tts_one(seg["text"], raw, VOICE / f"seg_{seg['key']}.words.json"))
                    raw.unlink(missing_ok=True)
                shutil.copy2(manual_files[seg["key"]], VOICE / f"seg_{seg['key']}.mp3")
                print(f"[manual] {seg['key']} <- {manual_files[seg['key']].name}")
            else:
                print(f"[tts-edge] {seg['key']} ({len(seg['text'])}字)", flush=True)
                asyncio.run(tts_one(seg["text"], raw, VOICE / f"seg_{seg['key']}.words.json"))
                # Q 弹变声：升调 1.32x + 时长补偿（净时长不变；源采样率动态探测，edge 为 24k）
                sr_in = subprocess.run(
                    [find_ffmpeg().replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
                     "-select_streams", "a:0", "-show_entries", "stream=sample_rate",
                     "-of", "csv=p=0", str(raw)], capture_output=True, text=True).stdout.strip()
                sr_in = int(sr_in or 24000)
                f = 1.32
                run_ff(["-i", str(raw), "-af",
                        f"asetrate={sr_in}*{f},aresample=44100,atempo={1/f:.4f}",
                        "-c:a", "libmp3lame", "-q:a", "3",
                        str(VOICE / f"seg_{seg['key']}.mp3")])
                raw.unlink(missing_ok=True)
        marker.touch()
    # 2. 解码 + 时间轴
    timeline, t = [], 0.6  # 片头留 0.6s
    voice_track_parts = []
    for seg in SEGS:
        wav = VOICE / f"seg_{seg['key']}.wav"
        mp3_to_wav_mono(VOICE / f"seg_{seg['key']}.mp3", wav)
        data = read_wav(wav)
        seg["start"] = t
        seg["dur"] = len(data) / SR
        timeline.append({k: seg[k] for k in ("key", "img", "pic", "title", "card", "start", "dur", "gap_after")})
        voice_track_parts.append((t, data))
        t += seg["dur"] + seg["gap_after"]
    total = t + 1.6  # 尾部余量
    print(f"[info] 总时长 {total:.1f}s")

    # 3. 人声轨
    voice = np.zeros(int(total * SR))
    for start, data in voice_track_parts:
        i = int(start * SR)
        voice[i:i + len(data)] += data
    write_wav(WS / "voice_track.wav", voice, gain=0.96)

    # 4. 音效轨（切镜 pop / 指标卡 ding / 片头 type）
    sfx = np.zeros(int(total * SR))
    pop = read_wav(REPO_ROOT / "data" / "sfx" / "pop.wav")
    ding = read_wav(REPO_ROOT / "data" / "sfx" / "ding.wav")
    typ = read_wav(REPO_ROOT / "data" / "sfx" / "type.wav")

    def put(tr, snd, at, g=1.0):
        i = int(at * SR)
        j = min(i + len(snd), len(tr))
        if i < len(tr):
            tr[i:j] += snd[: j - i] * g

    for seg in timeline:
        put(sfx, pop, seg["start"] - 0.15, 0.9)
        if seg["card"]:
            put(sfx, ding, seg["start"] + 1.1, 0.8)
    put(sfx, typ, 0.65, 0.7)
    write_wav(WS / "sfx_track.wav", sfx, gain=0.85)

    # 5. BGM 轨（tech 循环到片尾换 cute，交接处淡出淡入）
    def load_mp3_mono(p):
        tmp = WS / (p.stem + "_tmp.wav")
        run_ff(["-i", str(p), "-ar", str(SR), "-ac", "1", str(tmp)])
        d = read_wav(tmp)
        tmp.unlink()
        return d

    tech, cute = load_mp3_mono(REPO_ROOT / "data" / "bgm" / "bgm_tech_main.mp3"), \
                 load_mp3_mono(REPO_ROOT / "data" / "bgm" / "bgm_cute_wool.mp3")
    bgm = np.zeros(int(total * SR))

    def tile_to(tr, snd, a, b, fade_in=1.2, fade_out=1.5):
        n = b - a
        i0, i1 = int(a * SR), int(b * SR)
        seg = np.zeros(i1 - i0)
        k = 0
        while k < len(seg):
            chunk = snd[: min(len(snd), len(seg) - k)]
            seg[k:k + len(chunk)] = chunk
            k += len(chunk)
        fi, fo = int(fade_in * SR), int(fade_out * SR)
        if fi > 0:
            seg[:fi] *= np.linspace(0, 1, fi)
        if fo > 0:
            seg[-fo:] *= np.linspace(1, 0, fo)
        tr[i0:i1] += seg

    t1_start = next(s["start"] for s in timeline if s["key"] == "t1")
    tile_to(bgm, tech, 0.0, t1_start + 0.8, fade_in=1.5, fade_out=1.6)
    tile_to(bgm, cute, t1_start, total, fade_in=1.2, fade_out=3.0)
    write_wav(WS / "bgm_track.wav", bgm, gain=0.35)

    # 6. ducking 混音：BGM 被人声闪避压低
    run_ff(["-i", str(WS / "voice_track.wav"), "-i", str(WS / "bgm_track.wav"),
            "-i", str(WS / "sfx_track.wav"),
            "-filter_complex",
            "[1:a][0:a]sidechaincompress=threshold=0.04:ratio=14:attack=25:release=600:makeup=1[duck];"
            "[0:a][duck][2:a]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.95[a]",
            "-map", "[a]", "-ar", str(SR), str(WS / "audio_final.wav")])
    dur = float(subprocess.run([find_ffmpeg().replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error",
                                "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(WS / "audio_final.wav")], capture_output=True, text=True).stdout.strip())
    print(f"[ok] audio_final.wav {dur:.1f}s")

    # 7. 字幕（edge: 词边界聚合；fish: 逐句实际时长）
    subs, idx = [], 1
    for seg in SEGS:
        wj = VOICE / f"seg_{seg['key']}.words.json"
        if wj.exists():
            words = json.loads(wj.read_text(encoding="utf-8"))
            if seg["key"] in manual_files and words:
                # manual 音频实际时长 vs edge 参考时长 -> 线性缩放词边界
                edge_end = max(w["t"] + w["d"] for w in words) / 1e7
                scale = (seg["dur"] / edge_end) if edge_end > 0.1 else 1.0
                for w in words:
                    w["t"] = int(w["t"] * scale)
                    w["d"] = int(w["d"] * scale)
                print(f"[align] {seg['key']} 缩放 {scale:.3f}")
            s, idx = words_to_srt(words, seg["start"], idx)
            subs += s
        else:
            sents = json.loads((VOICE / f"seg_{seg['key']}.sentences.json").read_text(encoding="utf-8"))
            t0 = seg["start"]
            for i, s_txt in enumerate(sents):
                swav = VOICE / f"seg_{seg['key']}_s{i:02d}.wav"
                mp3_to_wav_mono(VOICE / f"seg_{seg['key']}_s{i:02d}.mp3", swav)
                d = len(read_wav(swav)) / SR
                subs.append({"i": idx, "start": t0, "end": t0 + d + 0.1, "text": s_txt})
                idx += 1
                t0 += d
    # 句尾 0.12s 延时不得侵入下一句（严格轨道校验要求）
    for i in range(len(subs) - 1):
        subs[i]["end"] = min(subs[i]["end"], subs[i + 1]["start"] - 0.01)
    srt = "\n".join(f"{s['i']}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n{s['text']}\n" for s in subs)
    (WS / "subtitles.srt").write_text(srt, encoding="utf-8")
    (WS / "timeline.json").write_text(
        json.dumps({"total": total, "segments": timeline, "subtitles": subs},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] subtitles.srt ({len(subs)} 句) + timeline.json")


if __name__ == "__main__":
    main()
