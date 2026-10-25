# -*- coding: utf-8 -*-
"""带卡死检测与自动重试的抓取运行器。

三种"卡住"场景的处理：
  1. 代理不通（Clash 未开）   -> 启动前/重试前等待代理恢复（每 15s 探测，上限 30 分钟）
  2. 抓取进程挂死             -> 单轮 15 分钟超时强制结束，重试
  3. 抓取"成功"但拿到 0 条    -> 校验 hot_100.json 数量（<30 视为失败），重试

用法:
  python 脚本/daily_runner.py hot              # 运行 jina_fetch.py hot（自动重试，共 3 轮）
  python 脚本/daily_runner.py topic <id>...    # topic 模式同样受保护
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
PROXY_HOST, PROXY_PORT = "127.0.0.1", 7897
ATTEMPTS = 3
ATTEMPT_TIMEOUT = 15 * 60   # 单轮抓取上限（秒）
PROXY_WAIT = 30 * 60        # 代理等待上限（秒）
POLL = 15
MIN_TOPICS = 30             # hot 模式低于此数视为失败


def proxy_alive():
    try:
        with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=3):
            return True
    except OSError:
        return False


def wait_proxy(why):
    if proxy_alive():
        return
    print(
        f"[guard] {why}代理 {PROXY_HOST}:{PROXY_PORT} 不可达，等待恢复"
        f"（每 {POLL}s 探测，上限 {PROXY_WAIT // 60} 分钟）…",
        flush=True,
    )
    deadline = time.time() + PROXY_WAIT
    while time.time() < deadline:
        time.sleep(POLL)
        if proxy_alive():
            print("[guard] 代理已恢复，继续", flush=True)
            return
    raise SystemExit("[guard] 等待代理超时，放弃。请开启代理后手动重跑。")


def run(args, timeout):
    print(f"[guard] 运行: {' '.join(str(a) for a in args)}", flush=True)
    try:
        return subprocess.run(args, cwd=str(REPO), timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print(f"[guard] 单轮超时（{timeout // 60} 分钟），判定为卡死，准备重试", flush=True)
        return 1


def count_topics():
    try:
        return len(json.loads((DATA / "hot_100.json").read_text(encoding="utf-8")))
    except Exception:
        return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "hot"
    fetch = REPO / "脚本" / "jina_fetch.py"
    wait_proxy("启动前检查；")
    for attempt in range(1, ATTEMPTS + 1):
        if mode == "hot":
            rc = run([sys.executable, str(fetch), "hot"], ATTEMPT_TIMEOUT)
            n = count_topics()
            print(f"[guard] 第 {attempt}/{ATTEMPTS} 轮结束 rc={rc} topics={n}", flush=True)
            if rc == 0 and n >= MIN_TOPICS:
                print(f"[guard] 抓取成功（{n} 条）", flush=True)
                return
            reason = f"rc={rc}, topics={n}"
        else:
            rc = run([sys.executable, str(fetch), "topic", *sys.argv[2:]], ATTEMPT_TIMEOUT)
            if rc == 0:
                print("[guard] topic 抓取成功", flush=True)
                return
            reason = f"rc={rc}"
        if attempt < ATTEMPTS:
            print(f"[guard] 本轮失败（{reason}），进入重试", flush=True)
            wait_proxy("重试前检查；")
            time.sleep(10)
    raise SystemExit(f"[guard] {ATTEMPTS} 轮均失败，放弃并如实上报")


if __name__ == "__main__":
    main()
