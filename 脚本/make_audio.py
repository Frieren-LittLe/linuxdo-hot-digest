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
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-23"
WS = REPO_ROOT / "data" / "video_workspace" / DATE
VOICE = WS / "voice"
SR = 44100

VOICE_NAME = "zh-CN-XiaoyiNeural"
RATE = "+10%"

# 段落：img=主立绘, pic=主视觉插图, title=切镜标题, card=指标卡文本, bgm 语义段
SEGS = [
    {"key": "hook", "img": "normal_01", "pic": "1A", "title": "PHP 核弹引爆！Cloudflare 免费帮你挡？", "card": "", "gap_after": 0.9,
     "text": "昨天 PHP 炸出俩核弹级漏洞？别慌，Cloudflare 免费帮你挡了！我是大肥鱼，开饭！"},
    {"key": "n1", "img": "shock_01", "pic": "1A", "title": "PHP2Shell 核弹引爆，Cloudflare 紧急 WAF 免费救命", "card": "上手难度 ★★☆☆☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：Cloudflare WAF / 原帖 3054943", "gap_after": 1.0,
     "text": "PHP 突然爆出 CVE-2026-109618 和 109619 两个远程代码执行核弹，全球建站佬连夜排险。补丁来不及打怎么办？Cloudflare 已经在托管 WAF 里推了紧急规则，免费版默认全开，攻击流量直接拦截。但有个大前提：源站必须只认 Cloudflare 的回源 IP，不然攻击者绕过 CF 直连你的服务器，规则就成了摆设。记住三件事：锁源站、留规则、抓紧升级 PHP。WAF 只是止血，升级才是治病。"},
    {"key": "n2", "img": "geek_01", "pic": "2A", "title": "伪 POC 满天飞？这篇复盘教你冷静", "card": "上手难度 ★★★☆☆ ｜ 白嫖指数 ★★☆☆☆ ｜ 核心指路：Nginx 缓解组合拳 / 原帖 3065907", "gap_after": 1.0,
     "text": "同一事件，L 站佬友交出一篇高分复盘。先说结论：真实可用的 POC 依赖二进制硬编码偏移，PHP 版本一变偏移就变，打错一位的结果是搞崩自己服务而不是拿 shell，实际利用门槛极高。网上一堆自称 POC，多半是旧漏洞换皮。补丁没到时可以打组合拳：关掉 session.upload_progress，Nginx 限制请求体，multipart 上传直接拒绝。最扎心的是：事后他问了一圈 AI，全都喊非常严重立即响应，理性一算，多数小站根本不用停机。AI 能加速研判，但风险决策不能外包给模型。"},
    {"key": "n3", "img": "laugh_03", "pic": "3B", "title": "AI 副业可复制样本：3 天交付 6 单", "card": "上手难度 ★★★☆☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：开源 VVV 框架 / 原帖 3064156", "gap_after": 1.0,
     "text": "这位佬友结婚缺个暖场视频，外面做一条报价五十，他干脆用 Claude 自己撸：小红书找参考视频，把视频、音乐、婚纱照、文案一股脑丢给模型，复刻成 Remotion 动效，缺素材就调生图能力补齐。结果两三天交付六单，赚了三百多，推广只花三十块。规模化关键是成本解耦：模板制作留给 Claude 烧周限额度，批量生成交给便宜模型。他还开源了 VVV 框架，一套模板二十多个 Agent 通用。想抄作业记住：核心资产是模板库，不是模型调用。"},
    {"key": "n4", "img": "geek_03", "pic": "4B", "title": "AI 会话是内存，项目目录才是硬盘", "card": "上手难度 ★★☆☆☆ ｜ 白嫖指数 ★★★★★ ｜ 核心指路：npx skills add briqt/knowledge-project / 原帖 3062753", "gap_after": 1.0,
     "text": "高强度 vibe coding 的老毛病：目标、进度、决策理由全散落在不同会话里，换个窗口就得跟 AI 重新自我介绍。这位佬友开源了 knowledge-project：方法论放在 skill 里，上下文全部落在项目文件。AGENTS.md 存目标和约定，log.md 存进展和下一步，调研结论写成带 frontmatter 的 Markdown。同类问题反复出现就固化成规则，规则膨胀了就精简。不锁定任何 Agent 生态，一条命令安装。核心思想一句话：AI 会话是易失内存，项目目录才是持久磁盘。"},
    {"key": "n5", "img": "geek_05", "pic": "5C", "title": "不 root 不刷机，老电视焕新实录", "card": "上手难度 ★★★★☆ ｜ 白嫖指数 ★★★★☆ ｜ 核心指路：GitHub morluto/rea / 原帖 3064579", "gap_after": 0.9,
     "text": "2019 年的小米电视 A50，臃肿到开机要两分钟。这位佬友不 root 不刷机，用无线 ADB 把它压到二十一秒。路数：电视端连点型号开开发者模式，允许 ADB 调试；电脑同一 WiFi 无线连接，再用开源工具 REA 配合 AI 逆向分析系统应用，精准处置自启和冗余组件，全程可回滚。两个坑提前说：电视重启后 ADB 会自动关闭，得重新打开；tvhome 桌面被系统绑定，想换 launcher 得 root，此路不通。家里老电视老盒子，换新之前先抢救一轮。"},
    {"key": "t1", "img": "token_01", "pic": "6A", "title": "讯飞星辰 MaaS 注册白送 10 亿 Token", "card": "上手难度 ★★☆☆☆ 需实名 ｜ 白嫖指数 ★★★★★ ｜ 核心指路：讯飞星辰 MaaS / 原帖 3060920", "gap_after": 0.6, "bgm": "cute",
     "text": "又到了小白练手环节！今天吃白饭 Token 的任务是：讯飞星辰 MaaS，注册就送十亿 Token。第一步，搜索讯飞星辰 MaaS 进官网，手机号注册账号。第二步，完成个人实名认证，这是唯一门槛，介意交身份信息的佬友围观就好。第三步，活动页一键领取十亿 Token，写代码调智能体够折腾一个月。"},
    {"key": "t2", "img": "token_03", "pic": "6A", "title": "防过期提醒", "card": "", "gap_after": 0,
     "text": "注意：额度只能跑讯飞自家模型，31 天内有效，每人限领一次，领了记得月底前用完，过期不补！今天的白饭 Token 肥鱼吃饱了，你们也别饿着。点个关注，明晚九点，鲸鲸准时开饭！"},
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


async def tts_one(text, mp3_path, words_path):
    import edge_tts
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
        out.append({"i": idx_start + i, "start": seg_start + t0 / 1e7,
                    "end": seg_start + t1 / 1e7 + 0.12, "text": s})
    return out, idx_start + len(sents)


def fmt_ts(x):
    h, m = int(x // 3600), int(x % 3600 // 60)
    s, ms = int(x % 60), int(x * 1000 % 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    VOICE.mkdir(parents=True, exist_ok=True)
    # 1. TTS
    for seg in SEGS:
        mp3 = VOICE / f"seg_{seg['key']}.mp3"
        wj = VOICE / f"seg_{seg['key']}.words.json"
        if not mp3.exists():
            print(f"[tts] {seg['key']} ({len(seg['text'])}字)", flush=True)
            asyncio.run(tts_one(seg["text"], mp3, wj))
        else:
            print(f"[skip] {mp3.name} 已存在")
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

    # 7. 字幕
    subs, idx = [], 1
    for seg in SEGS:
        words = json.loads((VOICE / f"seg_{seg['key']}.words.json").read_text(encoding="utf-8"))
        s, idx = words_to_srt(words, seg["start"], idx)
        subs += s
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
