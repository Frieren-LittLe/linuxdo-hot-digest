# -*- coding: utf-8 -*-
"""一次性基建：合成 BGM（2 首）与基础转场音效（3 个）。

输出:
  data/bgm/bgm_tech_main.mp3   轻快极客电子风（正片）
  data/bgm/bgm_cute_wool.mp3   呆萌摸鱼风（片尾小白练手）
  data/sfx/pop.wav type.wav ding.wav
全部由 numpy 加法合成（零外部素材、零版权风险），WAV 经 ffmpeg 转 MP3。
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
BGM = REPO_ROOT / "data" / "bgm"
SFX = REPO_ROOT / "data" / "sfx"
SR = 44100


def find_ffmpeg():
    for p in (REPO_ROOT / "data" / "bin").rglob("ffmpeg.exe"):
        return str(p)
    return "ffmpeg"


def note(freq):
    """音名 -> 频率，如 note('A2')。"""
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4,
             "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}
    m, octv = freq[:-1], int(freq[-1])
    return 440.0 * 2 ** (names[m] / 12 + (octv - 4))


def adsr(n, a=0.01, d=0.05, s=0.7, r=0.15):
    """长度 n 采样的包络：快攻-衰- sustain - 释放。"""
    t = np.linspace(0, 1, n)
    an, dn, rn = int(a * SR), int(d * SR), int(r * SR)
    env = np.full(n, s)
    if an > 0:
        env[:an] = np.linspace(0, 1, an)
        env[an:an + dn] = np.linspace(1, s, min(dn, n - an))
    if rn > 0 and n > rn:
        env[-rn:] = np.linspace(s, 0, rn) * (env[-rn:] / max(env[-rn:].max(), 1e-9))
    return env


def place(buf, sig, start):
    end = min(start + len(sig), len(buf))
    if start < len(buf):
        buf[start:end] += sig[: end - start]


def sine(freq, dur, gain=1.0, shape="pure"):
    """基础音色：pure / square（奇次谐波）/ bell（4倍泛音）。"""
    t = np.arange(int(dur * SR)) / SR
    w = np.sin(2 * np.pi * freq * t)
    if shape == "square":
        w = (w + np.sin(2 * np.pi * freq * 3 * t) / 3 + np.sin(2 * np.pi * freq * 5 * t) / 5) / 1.5
    elif shape == "bell":
        w = w + 0.25 * np.sin(2 * np.pi * freq * 4 * t)
    return w * gain


def write_wav(path, buf, gain=0.85):
    buf = buf / np.abs(buf).max() * gain
    pcm = (buf * 32767).astype(np.int16)
    stereo = np.column_stack([pcm, pcm]).ravel()
    with wave.Wave_write(str(path)) as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def synth_tech_main():
    """轻快极客电子风：Am-F-C-G，kick 四踩 + 方波 bass + 16 分琶音 + pad + hat。"""
    bpm = 124
    beat = 60 / bpm
    bar = beat * 4
    bars = 50
    total = int(bars * bar * SR) + SR
    buf = np.zeros(total)
    chords = [["A2", "A3", "C4", "E4"], ["F2", "F3", "A3", "C4"],
              ["C3", "G3", "C4", "E4"], ["G2", "G3", "B3", "D4"]]
    rng = np.random.default_rng(42)
    for b in range(bars):
        t0 = int(b * bar * SR)
        ch = chords[b % 4]
        # pad：整小节和弦长音
        for nv in ch[1:]:
            sig = sine(note(nv), bar, 0.10, "pure") * np.linspace(0.4, 1, int(bar * SR)) ** 2
            place(buf, sig, t0)
        # bass：八分音符根音
        for i in range(8):
            dur = beat / 2
            sig = sine(note(ch[0]), dur, 0.30, "square") * adsr(int(dur * SR), 0.004, 0.05, 0.55, 0.05)
            place(buf, sig, t0 + int(i * dur * SR))
        # arp：16 分琶音（和弦音 + 高八度，跨两个八度上行）
        pool = [note(x) for x in ch[1:]] + [note(x) * 2 for x in ch[1:3]]
        for i in range(16):
            f = pool[i % len(pool)] * (2 if i % 5 == 4 else 1)
            dur = beat / 4
            sig = sine(f, dur, 0.16, "bell") * adsr(int(dur * SR), 0.002, 0.08, 0.25, 0.04)
            place(buf, sig, t0 + int(i * dur * SR))
        # kick：每拍
        for i in range(4):
            n = int(beat * 0.5 * SR)
            t = np.arange(n) / SR
            f = 120 * np.exp(-t * 18) + 45
            sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.55
            place(buf, sig, t0 + int(i * beat * SR))
        # hat：半拍
        for i in range(8):
            n = int(0.05 * SR)
            sig = (rng.standard_normal(n)) * np.exp(-np.arange(n) / SR * 90) * 0.08
            sig = np.diff(sig, prepend=0)  # 高通感
            place(buf, sig, t0 + int(i * beat / 2 * SR))
    # 结尾 2 小节淡出
    fade = int(2 * bar * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)
    write_wav(BGM / "bgm_tech_main.wav", buf, gain=0.80)
    print("[ok] bgm_tech_main.wav", round(total / SR), "s")


def synth_cute_wool():
    """呆萌摸鱼风：C-G-Am-F，音乐盒旋律 + 圆 bass + 木鱼 tick + 泡泡滑音。"""
    bpm = 96
    beat = 60 / bpm
    bar = beat * 4
    bars = 28
    total = int(bars * bar * SR) + SR
    buf = np.zeros(total)
    chords = [["C3", "C4", "E4", "G4"], ["G2", "G3", "B3", "D4"],
              ["A2", "A3", "C4", "E4"], ["F2", "F3", "A3", "C4"]]
    # 手写 2 小节旋律动机（五声感），循环并轻微变奏
    motif = ["E5", "G5", "A5", "G5", "E5", "G5", "A5", "C6",
             "D6", "C6", "A5", "G5", "E5", "D5", "E5", "R"]
    for b in range(bars):
        t0 = int(b * bar * SR)
        ch = chords[b % 4]
        for nv in ch[1:]:
            sig = sine(note(nv), bar, 0.09, "pure") * np.hanning(int(bar * SR)) ** 0.5
            place(buf, sig, t0)
        for i in range(2):  # bass 二分音符
            sig = sine(note(ch[0]) * 2, beat * 2, 0.30) * adsr(int(beat * 2 * SR), 0.01, 0.1, 0.7, 0.3)
            place(buf, sig, t0 + int(i * beat * 2 * SR))
        for i, nn in enumerate(motif):  # 旋律：每音一拍
            if b % 4 == 3 and i % 4 == 1:
                continue  # 变奏：留白呼吸
            if nn == "R":
                continue
            f = note(nn)
            if b % 8 >= 4:
                f *= 1.0 if i not in (6, 7) else 0.94  # 轻微变调防机械
            dur = beat * 0.95
            sig = sine(f, dur, 0.20, "bell") * adsr(int(dur * SR), 0.003, 0.12, 0.35, 0.25)
            place(buf, sig, t0 + int(i * beat * SR))
        for i in range(4):  # 木鱼 tick 正拍
            n = int(0.03 * SR)
            t = np.arange(n) / SR
            sig = np.sin(2 * np.pi * 1900 * t) * np.exp(-t * 120) * 0.10
            place(buf, sig, t0 + int(i * beat * SR))
        if b % 2 == 1:  # 泡泡滑音
            n = int(0.12 * SR)
            t = np.arange(n) / SR
            f = 500 + 700 * t / 0.12
            sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 25) * 0.12
            place(buf, sig, t0 + int(2.5 * beat * SR))
    fade = int(2.5 * bar * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)
    write_wav(BGM / "bgm_cute_wool.wav", buf, gain=0.78)
    print("[ok] bgm_cute_wool.wav", round(total / SR), "s")


def synth_sfx():
    # pop：气泡啵（滑升 + 快衰减）
    n = int(0.10 * SR)
    t = np.arange(n) / SR
    f = 350 + 550 * t / 0.10
    pop = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40) * 0.9
    write_wav(SFX / "pop.wav", pop, gain=0.85)
    # type：3 连键盘 click
    rng = np.random.default_rng(7)
    total = int(0.22 * SR)
    typ = np.zeros(total)
    for k, off in enumerate([0.0, 0.07, 0.15]):
        n = int(0.025 * SR)
        t = np.arange(n) / SR
        click = rng.standard_normal(n) * np.exp(-t * 260) * 0.8
        click *= np.sin(2 * np.pi * 2400 * t) + 0.6
        place(typ, click, int(off * SR))
    write_wav(SFX / "type.wav", typ, gain=0.80)
    # ding：G6 清脆叮
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    ding = (np.sin(2 * np.pi * 1568 * t) + 0.3 * np.sin(2 * np.pi * 3136 * t)) * np.exp(-t * 7) * 0.9
    write_wav(SFX / "ding.wav", ding, gain=0.80)
    print("[ok] pop.wav / type.wav / ding.wav")


def to_mp3():
    ff = find_ffmpeg()
    for name in ("bgm_tech_main", "bgm_cute_wool"):
        wav = BGM / f"{name}.wav"
        mp3 = BGM / f"{name}.mp3"
        r = subprocess.run([ff, "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3)],
                           capture_output=True, text=True)
        print(("[ok]" if r.returncode == 0 else "[fail]") + f" {mp3.name} {mp3.stat().st_size//1024}KB")
        if r.returncode == 0:
            wav.unlink()  # mp3 成功后删 wav 省空间


if __name__ == "__main__":
    BGM.mkdir(parents=True, exist_ok=True)
    SFX.mkdir(parents=True, exist_ok=True)
    synth_tech_main()
    synth_cute_wool()
    synth_sfx()
    to_mp3()
