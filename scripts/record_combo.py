"""Cong cu ghi va phat lai thao tac cham phan cung (/dev/input/event0) khong bo dem."""
import argparse
import json
import math
import os
import struct
import subprocess
import sys
import time
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import coc_executor_tools as cet
import coc_vision_grid as cvg

EVENT_STRUCT = struct.Struct("<QQHHi")
LATEST_POINTER = os.path.join(cet.RUNTIME_DIR, "latest_recording_path.txt")


def _adb_base():
    return cet._adb_base_args()


def get_surface_orientation():
    r = cet.adb_shell("dumpsys input | grep SurfaceOrientation", timeout=5)
    out = r.stdout if (r and r.stdout) else ""
    if "1" in out and "3" not in out:
        return 1
    return 3


def raw_to_screen(rx, ry, orient):
    if orient == 1:
        px = int(round(ry * 2220.0 / 4096.0))
        py = int(round((4095.0 - rx) * 1080.0 / 4096.0))
    else:
        px = int(round((4095.0 - ry) * 2220.0 / 4096.0))
        py = int(round(rx * 1080.0 / 4096.0))
    px = max(0, min(2219, px))
    py = max(0, min(1079, py))
    return px, py


def read_exact(stream, n):
    chunks = []
    got = 0
    while got < n:
        chunk = stream.read(n - got)
        if not chunk:
            return None
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def run_self_test():
    orient = get_surface_orientation()
    print(f"[SELF-TEST] SurfaceOrientation={orient}", flush=True)
    proc = subprocess.Popen(
        _adb_base() + ["exec-out", "cat /dev/input/event0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    time.sleep(0.5)
    cet.tap(2150, 750, sleep_sec=0.2)

    cur_slot = 0
    slots = {}
    parsed = None
    deadline = time.time() + 4.0
    packets = 0
    while time.time() < deadline:
        raw = read_exact(proc.stdout, EVENT_STRUCT.size)
        if raw is None:
            break
        packets += 1
        sec, usec, ev_type, ev_code, ev_val = EVENT_STRUCT.unpack(raw)
        ts = sec + usec / 1_000_000.0
        if ev_type == 3:
            if ev_code == 0x2F:
                cur_slot = ev_val
            elif ev_code == 0x39:
                if ev_val >= 0:
                    slots[cur_slot] = {"rx": None, "ry": None, "points": []}
                else:
                    st = slots.pop(cur_slot, None)
                    if st and st["points"]:
                        parsed = st["points"][0]
                        break
            elif ev_code == 0x35 and cur_slot in slots:
                slots[cur_slot]["rx"] = ev_val
            elif ev_code == 0x36 and cur_slot in slots:
                slots[cur_slot]["ry"] = ev_val
        elif ev_type == 0 and ev_code == 0:
            for st in slots.values():
                if st["rx"] is not None and st["ry"] is not None:
                    px, py = raw_to_screen(st["rx"], st["ry"], orient)
                    st["points"].append((ts, px, py))
    proc.kill()
    try:
        proc.wait(timeout=2)
    except Exception:
        pass
    if parsed:
        print(f"[SELF-TEST] OK! packets={packets}, parsed tap=({parsed[1]}, {parsed[2]})", flush=True)
        return 0
    err = proc.stderr.read().decode(errors="ignore")
    print(f"[SELF-TEST] FAILED! packets={packets}, stderr={err}", flush=True)
    return 1


def run_record():
    os.makedirs(cet.RUNTIME_DIR, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    bin_log = os.path.join(cet.RUNTIME_DIR, f"recorded_raw_{tag}.bin")
    jsonl_log = os.path.join(cet.RUNTIME_DIR, f"recorded_taps_{tag}.jsonl")
    with open(LATEST_POINTER, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(jsonl_log)

    orient = get_surface_orientation()
    print(f"[RECORDER] Ready | SurfaceOrientation={orient}", flush=True)
    print(f"[RECORDER] JSONL: {jsonl_log}", flush=True)

    proc = subprocess.Popen(
        _adb_base() + ["exec-out", "cat /dev/input/event0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    cur_slot = 0
    slots = {}
    action_idx = 0
    prev_start_t = None
    prev_end_t = None

    with open(bin_log, "wb") as f_bin, open(jsonl_log, "a", encoding="utf-8", newline="\n") as f_js:
        while True:
            raw = read_exact(proc.stdout, EVENT_STRUCT.size)
            if raw is None:
                break
            f_bin.write(raw)
            f_bin.flush()

            sec, usec, ev_type, ev_code, ev_val = EVENT_STRUCT.unpack(raw)
            ts = sec + usec / 1_000_000.0

            if ev_type == 3:
                if ev_code == 0x2F:
                    cur_slot = ev_val
                elif ev_code == 0x39:
                    if ev_val >= 0:
                        slots[cur_slot] = {
                            "tracking_id": ev_val,
                            "rx": None,
                            "ry": None,
                            "start_t": ts,
                            "last_t": ts,
                            "points": [],
                        }
                    else:
                        st = slots.pop(cur_slot, None)
                        if st and st["points"]:
                            action_idx += 1
                            t0, x0, y0 = st["points"][0]
                            t1, x1, y1 = st["points"][-1]
                            dist = math.hypot(x1 - x0, y1 - y0)
                            kind = "tap" if dist < 25 else "swipe"
                            dt_start = round(t0 - prev_start_t, 3) if prev_start_t is not None else 0.0
                            dt_gap = round(t0 - prev_end_t, 3) if prev_end_t is not None else 0.0
                            hold_sec = round(max(0.0, ts - t0), 3)
                            prev_start_t = t0
                            prev_end_t = ts
                            rec = {
                                "idx": action_idx,
                                "kind": kind,
                                "x": x0,
                                "y": y0,
                                "end_x": x1,
                                "end_y": y1,
                                "dt": dt_start,
                                "dt_gap": dt_gap,
                                "hold_sec": hold_sec,
                                "t_start": t0,
                                "t_end": ts,
                                "wall_time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                                "points": st["points"],
                            }
                            f_js.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            f_js.flush()
                            print(
                                f"[#{action_idx}] {kind.upper()} ({x0}, {y0})"
                                + (f" -> ({x1}, {y1})" if kind == "swipe" else "")
                                + f" | dt={dt_start:.2f}s (gap={dt_gap:.2f}s) | hold={hold_sec:.3f}s",
                                flush=True,
                            )
                elif ev_code == 0x35 and cur_slot in slots:
                    slots[cur_slot]["rx"] = ev_val
                    slots[cur_slot]["last_t"] = ts
                elif ev_code == 0x36 and cur_slot in slots:
                    slots[cur_slot]["ry"] = ev_val
                    slots[cur_slot]["last_t"] = ts
            elif ev_type == 0 and ev_code == 0:
                for st in slots.values():
                    if st["rx"] is not None and st["ry"] is not None:
                        px, py = raw_to_screen(st["rx"], st["ry"], orient)
                        if not st["points"] or (px, py) != (st["points"][-1][1], st["points"][-1][2]):
                            st["points"].append((st["last_t"], px, py))


def run_replay(jsonl_path):
    with open(jsonl_path, "r", encoding="utf-8") as f:
        actions = [json.loads(line) for line in f if line.strip()]

    img0 = cet.capture_screen()
    print(f"[REPLAY] Start | Battle button: {cvg.is_battle_button_visible(img0)} | Actions: {len(actions)}", flush=True)
    for a in actions:
        gap = float(a.get("dt_gap", 0.0))
        if gap > 0:
            time.sleep(gap)
        if a["kind"] == "tap":
            hold = max(0.045, float(a.get("hold_sec", 0.045)))
            print(f"[REPLAY #{a['idx']}] TAP ({a['x']}, {a['y']}) after {gap:.2f}s (hold={hold:.3f}s)", flush=True)
            cet.tap(a["x"], a["y"], sleep_sec=0.0, hold_sec=hold)
        else:
            dur_ms = max(100, int(round(float(a.get("hold_sec", 0.25)) * 1000)))
            print(f"[REPLAY #{a['idx']}] SWIPE ({a['x']}, {a['y']}) -> ({a['end_x']}, {a['end_y']}) after {gap:.2f}s", flush=True)
            cet.swipe(a["x"], a["y"], a["end_x"], a["end_y"], duration_ms=dur_ms, sleep_sec=0.0)
    time.sleep(1.0)
    img1 = cet.capture_screen()
    print(f"[REPLAY] Done | Battle button: {cvg.is_battle_button_visible(img1)}", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghi va phat lai combo thao tac Clash of Clans qua /dev/input/event0")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--replay", type=str, default=None)
    args = parser.parse_args()
    if args.self_test:
        sys.exit(run_self_test())
    elif args.record:
        run_record()
    elif args.replay:
        sys.exit(run_replay(args.replay))
    else:
        parser.print_help()
