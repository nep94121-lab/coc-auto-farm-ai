import os
import sys
import json
import time
import shutil
import struct
import atexit
import argparse
import subprocess
from datetime import datetime
import cv2
import numpy as np

from coc_vision_grid import (
    read_enemy_loot,
    read_home_resources,
    is_battle_button_visible,
    is_in_battle,
    is_next_button_visible,
    is_return_home_visible,
    is_five_button_wall_bar,
    is_upgrade_button_affordable,
    is_confirm_wall_modal_green,
    inspect_army_slots,
    draw_coordinate_grid,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
LOG_PATH = os.path.join(RUNTIME_DIR, "executor_v2.log")
LIVE_LOG_PATH = os.path.join(RUNTIME_DIR, "live_log.txt")

def _resolve_adb_path():
    env_adb = os.environ.get("ADB_PATH", "").strip()
    if env_adb:
        return env_adb
    which_adb = shutil.which("adb")
    if which_adb:
        return which_adb
    local_app = os.environ.get("LOCALAPPDATA", "")
    win_default = os.path.join(local_app, "Android", "Sdk", "platform-tools", "adb.exe") if local_app else ""
    if win_default and os.path.exists(win_default):
        return win_default
    mac_default = os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
    if os.path.exists(mac_default):
        return mac_default
    return "adb"


ADB = _resolve_adb_path()
SERIAL = os.environ.get("ANDROID_SERIAL", "").strip()

os.makedirs(RUNTIME_DIR, exist_ok=True)


def reset_live_session_log():
    """Khởi tạo lại file live_log.txt sạch sẽ (UTF-8) cho phiên chạy hiện tại."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    with open(LIVE_LOG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    with open(LIVE_LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    print(line, file=sys.stdout, flush=True)


def _adb_base_args():
    return [ADB, "-s", SERIAL] if SERIAL else [ADB]


def adb_shell(cmd, timeout=12):
    try:
        return subprocess.run(
            _adb_base_args() + ["shell", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log(f"[WARN] ADB shell timeout: {cmd}")
        return None


def reconnect_adb():
    log("[ADB] Khởi động lại ADB Server để khôi phục kết nối...")
    try:
        subprocess.run([ADB, "kill-server"], capture_output=True, timeout=10)
        subprocess.run([ADB, "start-server"], capture_output=True, timeout=10)
        time.sleep(1.2)
    except Exception as exc:
        log(f"[ADB] Lỗi khởi động lại ADB: {exc}")


def capture_screen(save_name=None, retry=True):
    """
    Chụp màn hình RAW không nén trực tiếp qua RAM (exec-out screencap),
    tốc độ ~0.63s (nhanh gấp 4.1 lần screencap -p), không ghi rác vào thẻ nhớ.
    """
    import struct

    try:
        r = subprocess.run(
            _adb_base_args() + ["exec-out", "screencap"],
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        r = None

    if r is None or r.returncode != 0 or not r.stdout or len(r.stdout) < 100000:
        if retry:
            reconnect_adb()
            return capture_screen(save_name=save_name, retry=False)
        return None

    buf = r.stdout
    w, h, _ = struct.unpack_from("<III", buf, 0)
    expected_pixels = w * h * 4
    if w > 0 and h > 0 and len(buf) >= expected_pixels + 12:
        hdr = len(buf) - expected_pixels
        arr = np.frombuffer(buf, dtype=np.uint8, offset=hdr).reshape((h, w, 4))
        img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    else:
        arr = np.frombuffer(buf, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if img is not None and save_name:
        cv2.imwrite(os.path.join(RUNTIME_DIR, save_name), img)
    return img


_TOUCH_PIPE = None
_TOUCH_ORIENTATION = None
_TRACKING_ID = 4000


def _close_touch_pipe():
    global _TOUCH_PIPE
    if _TOUCH_PIPE is not None:
        try:
            _TOUCH_PIPE.stdin.close()
            _TOUCH_PIPE.wait(timeout=1)
        except Exception:
            try:
                _TOUCH_PIPE.kill()
            except Exception:
                pass
        _TOUCH_PIPE = None


atexit.register(_close_touch_pipe)


def _get_surface_orientation():
    global _TOUCH_ORIENTATION
    if _TOUCH_ORIENTATION in (1, 3):
        return _TOUCH_ORIENTATION
    r = adb_shell("dumpsys input | grep SurfaceOrientation", timeout=5)
    if r and r.stdout and "1" in r.stdout and "3" not in r.stdout:
        _TOUCH_ORIENTATION = 1
    else:
        _TOUCH_ORIENTATION = 3
    return _TOUCH_ORIENTATION


def _ev(ev_type, ev_code, ev_val):
    return struct.pack("<QQHHi", 0, 0, ev_type, ev_code, int(ev_val))


def _ensure_touch_pipe():
    global _TOUCH_PIPE
    if _TOUCH_PIPE is not None and _TOUCH_PIPE.poll() is None:
        return _TOUCH_PIPE
    try:
        _TOUCH_PIPE = subprocess.Popen(
            _adb_base_args() + ["shell", "su -c 'cat > /dev/input/event0'"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.25)
        return _TOUCH_PIPE
    except Exception:
        _TOUCH_PIPE = None
        return None


def tap(x, y, sleep_sec=0.25, hold_sec=0.045):
    """
    Chạm trực tiếp phần cứng cảm ứng /dev/input/event0 (~0.045s/lần chạm, nhanh gấp 35 lần 'input tap' Java VM,
    tốn 0% CPU máy và không bao giờ bị timeout hay rơi mất quân!).
    """
    global _TRACKING_ID
    orient = _get_surface_orientation()
    px = max(0, min(2219, int(x)))
    py = max(0, min(1079, int(y)))
    if orient == 1:
        rx = max(0, min(4095, int(round(4095.0 - (py * 4096.0 / 1080.0)))))
        ry = max(0, min(4095, int(round(px * 4096.0 / 2220.0))))
    else:
        rx = max(0, min(4095, int(round(py * 4096.0 / 1080.0))))
        ry = max(0, min(4095, int(round(4095.0 - (px * 4096.0 / 2220.0)))))

    pipe = _ensure_touch_pipe()
    if pipe is not None and pipe.stdin is not None:
        try:
            _TRACKING_ID = (_TRACKING_ID + 1) % 60000 + 1000
            down_pkt = b"".join(
                [
                    _ev(3, 47, 0),
                    _ev(3, 57, _TRACKING_ID),
                    _ev(1, 330, 1),
                    _ev(1, 325, 1),
                    _ev(3, 53, rx),
                    _ev(3, 54, ry),
                    _ev(3, 48, 6),
                    _ev(3, 49, 6),
                    _ev(0, 0, 0),
                ]
            )
            up_pkt = b"".join(
                [
                    _ev(3, 47, 0),
                    _ev(3, 57, -1),
                    _ev(1, 330, 0),
                    _ev(1, 325, 0),
                    _ev(0, 0, 0),
                ]
            )
            pipe.stdin.write(down_pkt)
            pipe.stdin.flush()
            time.sleep(max(0.035, float(hold_sec)))
            pipe.stdin.write(up_pkt)
            pipe.stdin.flush()
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            return
        except Exception:
            _close_touch_pipe()

    adb_shell(f"input tap {px} {py}")
    if sleep_sec > 0:
        time.sleep(sleep_sec)


def close_all_modals():
    # Chạm các nút X góc trên & vùng cỏ trống bên phải (1815, 480) — tránh (480, 120) là Trader & tránh đáy giữa (Gem)
    for mx, my in [(2025, 80), (1850, 75), (1815, 110), (1502, 339), (1815, 480), (750, 75)]:
        tap(mx, my, sleep_sec=0.15)
    time.sleep(0.3)


def _ensure_device_gesture(asset_dir_name, script_name):
    """Đảm bảo bộ khung thao tác (vd zoom_pinch_fast, swipe_list_fast) đã nằm trên /data/local/tmp/."""
    remote_dir = f"/data/local/tmp/{asset_dir_name}"
    chk = adb_shell(f"test -f {remote_dir}/{script_name} && echo OK || echo MISSING", timeout=5)
    if chk and chk.stdout and "OK" in chk.stdout:
        return True
    local_dir = os.path.join(BASE_DIR, "assets", asset_dir_name)
    if not os.path.exists(os.path.join(local_dir, script_name)):
        return False
    adb_shell(f"rm -rf {remote_dir} && mkdir -p {remote_dir}", timeout=5)
    res = subprocess.run(_adb_base_args() + ["push", local_dir, "/data/local/tmp/"], capture_output=True, text=True, timeout=15)
    return res.returncode == 0


def _run_device_gesture(tag, asset_dir_name, script_name, repeats=1, sleep_sec=0.25, fallback_shell=None):
    """Chạy thao tác cảm ứng đóng gói sẵn trực tiếp trên /dev/input/event0 với độ trễ chuẩn."""
    repeats = max(1, int(repeats))
    has_bundle = _ensure_device_gesture(asset_dir_name, script_name)
    method = asset_dir_name if has_bundle else "fallback"
    for r in range(repeats):
        ran = False
        if has_bundle:
            res = adb_shell(f"su -c 'sh /data/local/tmp/{asset_dir_name}/{script_name}'", timeout=25)
            ran = bool(res and res.returncode == 0)
        if not ran and fallback_shell:
            log(f"[{tag}] Dùng fallback -> {fallback_shell}")
            adb_shell(fallback_shell, timeout=15)
            method = f"{method}_fallback"
        if r < repeats - 1 or sleep_sec > 0:
            time.sleep(max(0.15, float(sleep_sec)))
    log(f"[{tag}] Đã thực thi xong ({repeats} nhịp, method={method}).")
    return {"ok": True, "method": method, "repeats": repeats}


def zoom_out_pinch(repeats=1, sleep_sec=0.25):
    """Thực thi động tác chụm 2 ngón tay thu nhỏ màn hình (pinch zoom-out) từ thao tác tay của Sếp."""
    return _run_device_gesture(
        "ZOOM-OUT",
        "zoom_pinch_fast",
        "run_pinch.sh",
        repeats=repeats,
        sleep_sec=sleep_sec,
        fallback_shell="su -c 'sh /sdcard/do_pinch.sh'",
    )


def scroll_upgrade_list(repeats=1, sleep_sec=0.3):
    """Lướt xuống 1 nhịp trong danh sách nâng cấp Công trình (Build) hoặc Nghiên cứu (Lab) (~4.5s)."""
    return _run_device_gesture(
        "SCROLL-UPGRADE",
        "swipe_list_fast",
        "run_swipe.sh",
        repeats=repeats,
        sleep_sec=sleep_sec,
        fallback_shell="input swipe 1904 851 1937 81 900",
    )


def clamp_battle_point(x, y):
    """Đảm bảo tọa độ thả quân nằm gọn trong vùng bản đồ an toàn, không chạm nút UI."""
    cx = max(125, min(2095, int(x)))
    cy = max(60, min(830, int(y)))
    if cx < 265 and cy > 750:
        cy = 740
    if cx > 1860 and cy > 640:
        cy = 630
    return cx, cy


def get_status(with_grid=True):
    img = capture_screen("status_raw.png")
    if img is None:
        return {"ok": False, "error": "ADB_DISCONNECTED_OR_NO_SCREEN"}

    state = "unknown"
    data = {"ok": True}
    if is_return_home_visible(img):
        state = "battle_ended"
    elif is_in_battle(img) and is_next_button_visible(img):
        state = "battle_scout"
        eg, ee = read_enemy_loot(img)
        data["enemy_gold"] = eg
        data["enemy_elixir"] = ee
        data["slots"] = inspect_army_slots(img)
    elif is_in_battle(img):
        state = "battle_active"
        data["slots"] = inspect_army_slots(img)
    elif is_battle_button_visible(img):
        state = "home_village"
        hg, he = read_home_resources(img)
        data["home_gold"] = hg
        data["home_elixir"] = he
        data["ready_for_10m_wall_upgrade"] = (hg >= 10000000 and he >= 10000000)
    else:
        hg, he = read_home_resources(img)
        data["home_gold"] = hg
        data["home_elixir"] = he

    data["state"] = state
    if with_grid:
        grid_img = draw_coordinate_grid(
            img, show_battle_safe_box=(state in ("battle_scout", "battle_active"))
        )
        grid_path = os.path.join(RUNTIME_DIR, "status_grid.png")
        cv2.imwrite(grid_path, grid_img)
        data["grid_image"] = grid_path
    return data


def apply_ultra_battery_saver(keep_awake=True):
    """
    Ép toàn bộ cấu hình tiết kiệm pin tối đa + khôi phục sạc cho Galaxy S9 (Root + ADB):
    1. Gỡ khóa cảm biến nhiệt cuộn sạc không dây bị đứt (ADC=0 -> 900 / -200) để mở lại sạc (Status=Charging, Health=Good),
       vẫn giữ nguyên bảo vệ nhiệt phần cứng thật của IC sạc (chg_temp) và cổng USB (usb_temp).
    2. Tắt 3 nhân lớn Mongoose M3 (cpu5..7), hạ xung cpu0..3 xuống 832MHz, cpu4 xuống 650MHz, GPU xuống 260MHz
       (giảm nhiệt CPU từ 76°C xuống ~48°C và đảo dòng từ -2134 sang sạc dương +37 ngay trên cổng USB Laptop).
    3. Hạ độ sáng màn hình về 0, bật Battery Saver, tắt GPS/Bluetooth/4G/quét ngầm/loa/rung/animation.
    """
    stayon_val = "true" if keep_awake else "false"
    adb_shell(
        f"svc power stayon {stayon_val}; "
        "settings put global low_power 1; "
        "settings put global low_power_sticky 1; "
        "settings put system show_touches 0; "
        "settings put system pointer_location 0; "
        "settings put system screen_brightness_mode 0; "
        "settings put system screen_brightness 0; "
        "settings put system screen_auto_brightness_adj -1.0; "
        "settings put system high_brightness_mode_user_enable 0; "
        "settings put system aod_mode 0; "
        "settings put secure location_mode 0; "
        "settings put global wifi_scan_always_enabled 0; "
        "settings put global ble_scan_always_enabled 0; "
        "svc bluetooth disable; svc data disable; "
        "settings put system haptic_feedback_enabled 0; "
        "settings put system sip_key_feedback_vibration 0; "
        "settings put system sound_effects_enabled 0; "
        "media volume --stream 3 --set 0; "
        "settings put global window_animation_scale 0; "
        "settings put global transition_animation_scale 0; "
        "settings put global animator_duration_scale 0; "
        "am kill-all"
    )
    root_script = (
        "echo '950 910 -300 -250 950 910 -300 -250' > /sys/class/power_supply/battery/batt_temp_table\n"
        "echo 950 > /sys/class/power_supply/battery/batt_tune_temp_high_normal\n"
        "echo 910 > /sys/class/power_supply/battery/batt_tune_temp_high_rec_normal\n"
        "echo -300 > /sys/class/power_supply/battery/batt_tune_temp_low_normal\n"
        "echo -250 > /sys/class/power_supply/battery/batt_tune_temp_low_rec_normal\n"
        "echo 950 > /sys/class/power_supply/battery/batt_tune_coil_temp_high\n"
        "echo 910 > /sys/class/power_supply/battery/batt_tune_coil_temp_rec\n"
        "echo 1 > /sys/class/power_supply/battery/batt_swelling_control\n"
        "echo 1 > /sys/class/power_supply/battery/update\n"
        "echo 832000 > /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq\n"
        "echo 650000 > /sys/devices/system/cpu/cpufreq/policy4/scaling_max_freq\n"
        "echo 0 > /sys/devices/system/cpu/cpu5/online\n"
        "echo 0 > /sys/devices/system/cpu/cpu6/online\n"
        "echo 0 > /sys/devices/system/cpu/cpu7/online\n"
        "echo 260000 > /sys/kernel/gpu/gpu_max_clock\n"
    )
    try:
        subprocess.run(
            _adb_base_args() + ["shell", "su -c sh"],
            input=root_script,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        log(f"[WARN] Root battery tune warning: {exc}")
    return {"ok": True, "keep_awake": keep_awake}


def sleep_screen():
    """Tắt hẳn màn hình khi nghỉ chờ để pin chuyển sang sạc dương tối đa."""
    adb_shell("svc power stayon false; input keyevent 223")
    return {"ok": True, "screen": "sleeping"}


def wake_screen():
    """Bật sáng màn hình và mở khóa để tiếp tục điều khiển."""
    adb_shell("input keyevent 224; input keyevent 82; svc power stayon true")
    time.sleep(1.0)
    return {"ok": True, "screen": "awake"}


def launch_clash_of_clans():
    """Khởi động game Clash of Clans nếu chưa chạy hoặc bị đóng."""
    log("[GAME] Khởi động game Clash of Clans...")
    adb_shell("am start -n com.supercell.clashofclans/com.supercell.titan.GameApp")
    time.sleep(7.0)


def ensure_game_foreground():
    """Đảm bảo màn hình đang bật và Clash of Clans đang ở foreground."""
    r_pwr = adb_shell("dumpsys power", timeout=5)
    if r_pwr and r_pwr.stdout and "mWakefulness=Awake" not in r_pwr.stdout:
        wake_screen()
    r_win = adb_shell("dumpsys window", timeout=5)
    if r_win and r_win.stdout:
        focus_lines = [
            l for l in r_win.stdout.splitlines()
            if "mCurrentFocus" in l or "mFocusedApp" in l
        ]
        if focus_lines and not any("com.supercell.clashofclans" in l for l in focus_lines):
            launch_clash_of_clans()
            return False
    return True


def get_battery_info():
    """
    Đọc trực tiếp sysfs phần cứng để lấy % pin, nhiệt độ, và trạng thái sạc siêu tốc (<0.03s).
    """
    cmd = "cat /sys/class/power_supply/battery/capacity /sys/class/power_supply/battery/status /sys/class/power_supply/battery/batt_temp"
    r = adb_shell(cmd, timeout=5)
    if r and r.stdout:
        lines = r.stdout.strip().splitlines()
        try:
            capacity = int(lines[0].strip()) if len(lines) > 0 else 0
            status = lines[1].strip() if len(lines) > 1 else "Unknown"
            temp = int(lines[2].strip()) if len(lines) > 2 else 0
            return {"ok": True, "capacity": capacity, "status": status, "temp": temp}
        except Exception:
            pass
    # Fallback dumpsys battery
    r2 = adb_shell("dumpsys battery", timeout=5)
    if r2 and r2.stdout:
        cap = None
        status_str = "Unknown"
        temp = 0
        status_map = {"2": "Charging", "3": "Discharging", "4": "Not charging", "5": "Full"}
        for line in r2.stdout.splitlines():
            s = line.strip()
            if s.startswith("level:"):
                try:
                    cap = int(s.split(":", 1)[1].strip())
                except Exception:
                    pass
            elif s.startswith("status:"):
                code = s.split(":", 1)[1].strip()
                status_str = status_map.get(code, "Unknown")
            elif s.startswith("temperature:"):
                try:
                    temp = int(s.split(":", 1)[1].strip())
                except Exception:
                    pass
        if cap is not None:
            return {"ok": True, "capacity": cap, "status": status_str, "temp": temp}
    return {"ok": False, "capacity": -1, "status": "Unknown", "temp": 0}


def sleep_and_fast_charge_until(target_percent=25, check_interval_sec=45):
    """
    Bảo vệ pin thông minh (Zero Shutdown):
    Khi pin < 20%:
    1. Về Home màn hình chính để game ngừng render GPU.
    2. Tắt hẳn màn hình (input keyevent 223).
    3. Giữ cấu hình hạ xung CPU/GPU để pin sạc vào nhanh nhất và máy hoàn toàn mát.
    4. Ngủ định kỳ kiểm tra % pin.
    5. Đạt >= target_percent% (ví dụ 25%) -> Đánh thức màn hình, mở lại Clash of Clans và tiếp tục cày!
    """
    log(f"[BATTERY-GUARD] Pin thấp! Đưa máy về Home, tắt màn hình nghỉ sạc đến khi pin đạt >= {target_percent}%...")
    adb_shell("input keyevent 3")
    time.sleep(0.5)
    sleep_screen()
    apply_ultra_battery_saver(keep_awake=False)

    while True:
        time.sleep(check_interval_sec)
        batt = get_battery_info()
        cap = batt.get("capacity", -1)
        status = batt.get("status", "Unknown")
        if not batt.get("ok") or cap < 0:
            log("[BATTERY-GUARD] Tạm không đọc được % pin (ADB gián đoạn), tiếp tục chờ...")
            continue
        log(f"[BATTERY-GUARD] Đang nghỉ sạc mát máy... Pin hiện tại: {cap}% (Trạng thái: {status}, Ngưỡng mở lại: {target_percent}%)")
        if status == "Not charging":
            log("[BATTERY-GUARD] Phát hiện Not charging -> Áp dụng lại cấu hình mở khóa nhiệt độ sạc...")
            apply_ultra_battery_saver(keep_awake=False)
        if cap >= target_percent:
            log(f"[BATTERY-GUARD] Pin đã sạc hồi phục {cap}% >= {target_percent}%! Đánh thức máy và mở lại game...")
            break

    wake_screen()
    launch_clash_of_clans()
    return True


def take_clan_castle_cake():
    """
    Tự động kiểm tra và nhận quân Bánh Hội thành (Clan Castle Cake):
    - Nếu nút Bánh FREE màu xanh lá (chưa nhận): Bấm nhận + Confirm + Attack!
    - Nếu Bánh đã nhận trước đó (nút xám): Bỏ qua, bấm Attack! đi tìm trận ngay.
    - Đảm bảo 100% không bao giờ bị kẹt lại!
    """
    log("[CC-CAKE] Bắt đầu kiểm tra quân viện trợ Bánh Hội thành...")
    close_all_modals()
    # 1. Bấm nút kiếm Battle góc dưới trái
    tap(110, 970, sleep_sec=1.2)
    # 2. Bấm nút Edit Army góc dưới trái để vào bảng My Army (227, 940)
    tap(227, 940, sleep_sec=1.6)

    img_army = capture_screen()
    is_cake_available = False
    if img_army is not None:
        # Vùng nút bánh: x: 1680..1854, y: 842..916
        crop_cake = img_army[842:916, 1680:1854]
        hsv = cv2.cvtColor(crop_cake, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        if mask.mean() > 10:
            is_cake_available = True

    if is_cake_available:
        log("[CC-CAKE] Phát hiện nút Bánh FREE xanh -> Bấm nhận và xác nhận...")
        tap(1767, 879, sleep_sec=1.5)
        tap(1340, 755, sleep_sec=1.8)
        # Bấm Attack! trên My Army để đi tìm trận
        tap(1876, 940, sleep_sec=3.5)
    else:
        log("[CC-CAKE] Bánh đã nhận trước đó hoặc quân đã đủ -> Bấm Attack! đi tìm trận ngay!")
        tap(1876, 940, sleep_sec=3.5)

    # Kiểm tra nếu vẫn còn kẹt ở My Army hoặc Battle Modal
    time.sleep(1.0)
    chk = capture_screen()
    if chk is not None and not is_in_battle(chk):
        # Nếu vẫn còn nút Attack! xanh (1876, 940) của My Army
        crop_atk = chk[920:965, 1682:2053]
        if crop_atk.mean() > 50:
            log("[CC-CAKE] Thử lại bấm Attack! (1876, 940)...")
            tap(1876, 940, sleep_sec=3.5)
        # Nếu ở Battle Mode ngoài Làng -> Bấm Find a Match (325, 740)
        chk2 = capture_screen()
        if chk2 is not None and not is_in_battle(chk2):
            log("[CC-CAKE] Bấm Find a Match (325, 740)...")
            tap(325, 740, sleep_sec=3.5)

    log("[CC-CAKE] Đã hoàn tất và đang tiến hành tìm kiếm đối thủ!")
    return True


def find_rich_target(min_gold=1000000, min_elixir=1000000, max_searches=60):
    """
    Con số 2 tự động bấm tìm nhà và lọc chuẩn TỪNG LOẠI:
      enemy_gold >= min_gold VÀ enemy_elixir >= min_elixir.
    Tuyệt đối không cộng gộp và không bao giờ tự đánh bừa khi hết lượt tìm!
    """
    log(
        f"[FIND] Bắt đầu dò tìm mục tiêu: yêu cầu Vàng >= {min_gold:,} VÀ Tiên dược >= {min_elixir:,} (tối đa {max_searches} lượt)"
    )
    apply_ultra_battery_saver(keep_awake=True)

    img = capture_screen()
    if img is None:
        return {"ok": False, "found": False, "error": "ADB_DISCONNECTED"}

    # Nếu chưa ở trong màn hình dò trận thì từ Làng chính: Nhận quân Bánh Hội thành (nếu có) -> Bấm Attack đi tìm trận
    if not is_in_battle(img):
        close_all_modals()
        log("[FIND] Từ Làng chính: Kiểm tra Bánh Hội thành -> Attack đi tìm trận...")
        take_clan_castle_cake()

    history = []
    for idx in range(1, int(max_searches) + 1):
        img = None
        for _ in range(30):
            img = capture_screen()
            if img is not None and is_in_battle(img):
                break
            time.sleep(0.5)

        if img is None or not is_in_battle(img):
            log(f"[FIND] Lượt #{idx}: Không đọc được màn hình dò trận -> Dừng an toàn, KHÔNG thả quân!")
            return {
                "ok": False,
                "found": False,
                "searches": idx,
                "error": "NOT_IN_SCOUT_SCREEN",
                "history_tail": history[-5:],
            }

        e_gold, e_elix = read_enemy_loot(img)
        history.append({"index": idx, "gold": e_gold, "elixir": e_elix})
        log(f"  [Nhà #{idx}] Vàng = {e_gold:,} | Tiên dược = {e_elix:,}")

        if e_gold >= int(min_gold) and e_elix >= int(min_elixir):
            log(
                f"  => ĐẠT CHUẨN NHÀ GIÀU (Vàng {e_gold:,} >= {min_gold:,} & Dầu {e_elix:,} >= {min_elixir:,})! Tiến hành xả quân cố định siêu tốc!"
            )
            return {
                "ok": True,
                "found": True,
                "searches_used": idx,
                "enemy_gold": e_gold,
                "enemy_elixir": e_elix,
                "history_tail": history[-5:],
            }

        if idx < int(max_searches):
            log("[FIND] Nhà chưa đủ tài nguyên -> Bấm Next (2015, 769)...")
            tap(2015, 769, sleep_sec=4.0)

    # Hết số lượt tìm tối đa mà chưa có nhà đạt chuẩn -> Bấm End Battle rút về làng an toàn, TUYỆT ĐỐI KHÔNG THẢ QUÂN BỪA
    log(f"[FIND] Đã bấm Next {max_searches} nhà nhưng chưa gặp nhà đạt chuẩn -> Bấm End Battle (135,805) về làng an toàn!")
    tap(135, 805, sleep_sec=3.5)
    return {
        "ok": True,
        "found": False,
        "searches_used": int(max_searches),
        "action": "returned_home_without_attacking",
        "history_tail": history[-8:],
    }


def execute_attack_plan(
    yeti_points=None,
    wb_points=None,
    clone_points=None,
    rage_points=None,
    siege_point=(1550, 200),
    hero_points=None,
    wait_finish=True,
    max_battle_sec=65,
):
    """
    Thực thi rải quân + Cỗ máy Siege + 4 Tướng + Kích hoạt Kỹ năng + Phép siêu tốc qua /dev/input/event0:
    - Ô 1 (338, 900): Super Yeti (x8) rải vòng cung trên
    - Ô 2 (486, 900): Super Wall Breaker (x2) đục tường
    - Ô 3 (638, 900): Cỗ máy công thành (Siege Barracks)
    - Ô 4..7 (794, 940, 1089, 1235; 900): 4 Tướng (Minion Prince/Warden, Queen, King, Champion)
    - Kích hoạt Kỹ năng: chạm lại Ô 4..7 bung toàn bộ Equipment
    - Ô 8..10 (1391, 1540, 1696; 900): Clone Spell, Rage Spell, CC Spell dồn sát thương
    """
    img = capture_screen()
    if img is None or not is_in_battle(img):
        return {"ok": False, "error": "NOT_IN_BATTLE_CANNOT_DEPLOY"}

    default_yeti = [
        (540, 290), (670, 200), (800, 120), (930, 68),
        (1290, 68), (1420, 120), (1550, 200), (1680, 290),
    ]
    default_wb = [(800, 120), (1420, 120)]
    default_heroes = [(1120, 140), (1420, 120), (1290, 100), (1550, 200)]
    default_clone = [(880, 280), (1320, 280), (1110, 410)]
    default_rage = [(1110, 330)]

    yeti_pts = [clamp_battle_point(x, y) for x, y in (yeti_points or default_yeti)][:8]
    wb_pts = [clamp_battle_point(x, y) for x, y in (wb_points or default_wb)][:2]
    h_pts = [clamp_battle_point(x, y) for x, y in (hero_points or default_heroes)][:4]
    cl_pts = [clamp_battle_point(x, y) for x, y in (clone_points or default_clone)][:3]
    rg_pts = [clamp_battle_point(x, y) for x, y in (rage_points or default_rage)][:1]
    sg_pt = clamp_battle_point(siege_point[0], siege_point[1])

    t_deploy_start = time.perf_counter()

    # 1. Ô 1: Super Yeti (x8)
    log(f"[ATTACK] Rải Ô 1 Super Yeti (338,900) tại {len(yeti_pts)} điểm...")
    tap(338, 900, sleep_sec=0.15)
    for x, y in yeti_pts:
        tap(x, y, sleep_sec=0.06)

    # 2. Ô 2: Super Wall Breaker (x2)
    log(f"[ATTACK] Rải Ô 2 Super Wall Breaker (486,900) tại {len(wb_pts)} điểm...")
    tap(486, 900, sleep_sec=0.15)
    for x, y in wb_pts:
        tap(x, y, sleep_sec=0.07)

    # 3. Ô 3: Cỗ máy công thành (Siege Barracks)
    log(f"[ATTACK] Đặt Ô 3 Siege Barracks (638,900) tại {sg_pt}...")
    tap(638, 900, sleep_sec=0.15)
    tap(sg_pt[0], sg_pt[1], sleep_sec=0.10)

    # 4. Ô 4..7: Thả 4 Tướng
    hero_slots = [
        (4, "Minion Prince/Warden", (794, 900), h_pts[0]),
        (5, "Archer Queen", (940, 900), h_pts[1]),
        (6, "Barbarian King", (1089, 900), h_pts[2]),
        (7, "Royal Champion", (1235, 900), h_pts[3]),
    ]
    for slot_idx, h_name, slot_pos, drop_pos in hero_slots:
        log(f"[ATTACK] Thả Tướng Ô {slot_idx} ({h_name}) tại {drop_pos}...")
        tap(slot_pos[0], slot_pos[1], sleep_sec=0.12)
        tap(drop_pos[0], drop_pos[1], sleep_sec=0.08)

    # Chờ 2 giây cho tướng tiếp cận phòng thủ, sau đó kích hoạt Kỹ năng (Ability)
    time.sleep(2.0)
    log("[ATTACK] KÍCH HOẠT KỸ NĂNG 4 TƯỚNG (Bấm lại Ô 4, 5, 6, 7)...")
    for _, _, slot_pos, _ in hero_slots:
        tap(slot_pos[0], slot_pos[1], sleep_sec=0.10)

    # 5. Ô 8: Clone Spell
    log(f"[ATTACK] Thả Ô 8 Clone Spell (1391,900) tại {len(cl_pts)} điểm...")
    tap(1391, 900, sleep_sec=0.15)
    for cx, cy in cl_pts:
        tap(cx, cy, sleep_sec=0.08)

    # 6. Ô 9: Rage Spell
    log(f"[ATTACK] Thả Ô 9 Rage Spell (1540,900) tại {rg_pts}...")
    tap(1540, 900, sleep_sec=0.15)
    for rx, ry in rg_pts:
        tap(rx, ry, sleep_sec=0.08)

    # 7. Ô 10: CC Spell
    log("[ATTACK] Thả Ô 10 CC Spell (1696,900)...")
    tap(1696, 900, sleep_sec=0.15)
    cc_drop = rg_pts[0] if rg_pts else (1110, 330)
    tap(cc_drop[0], cc_drop[1], sleep_sec=0.10)

    deploy_ms = round((time.perf_counter() - t_deploy_start) * 1000.0, 1)
    log(f"[ATTACK] ĐÃ THẢ TRỌN VẸN 10 Ô + KÍCH HOẠT SKILL TƯỚNG TRONG {deploy_ms} ms ({deploy_ms/1000.0:.2f}s)!")

    # Vét bổ sung nếu thẻ nào còn vướng viền đỏ
    img_after = capture_screen("last_deployed.png")
    slots_after = inspect_army_slots(img_after)
    for s_info in slots_after:
        if s_info["available"]:
            sx, sy = s_info["tap"]
            log(f"[ATTACK] Ô {s_info['slot']} ({s_info['name']}) còn quân -> Thả vét rìa cỏ!")
            tap(sx, sy, sleep_sec=0.12)
            tap(1110, 80, sleep_sec=0.06)
            tap(1350, 100, sleep_sec=0.06)

    slots_final = inspect_army_slots(capture_screen("last_deployed.png"))

    if not wait_finish:
        return {
            "ok": True,
            "deployed": True,
            "slots_final": slots_final,
            "deployed_image": os.path.join(RUNTIME_DIR, "last_deployed.png"),
        }

    log(f"[ATTACK] Đang canh kết thúc trận (tối đa {max_battle_sec}s)...")
    won_early = False
    elapsed = 0
    for sec in range(0, int(max_battle_sec), 3):
        time.sleep(3.0)
        elapsed = sec + 3
        chk = capture_screen()
        if is_return_home_visible(chk):
            won_early = True
            log(f"[ATTACK] Chiến thắng kết thúc ở giây thứ ~{elapsed}!")
            break

    chk_end = capture_screen("last_battle_end.png")
    if won_early or is_return_home_visible(chk_end):
        for _ in range(3):
            tap(1120, 922, sleep_sec=1.5)
            chk_v = capture_screen()
            if is_battle_button_visible(chk_v):
                break
    elif is_in_battle(chk_end):
        log("[ATTACK] Hết thời gian cày -> Bấm End Battle (135,805) -> Okay (1320,680) -> Return Home (1120,922)")
        tap(135, 805, sleep_sec=0.9)
        tap(1320, 680, sleep_sec=1.8)
        for _ in range(3):
            tap(1120, 922, sleep_sec=1.5)
            chk_v = capture_screen()
            if is_battle_button_visible(chk_v):
                break
    else:
        for _ in range(3):
            tap(1120, 922, sleep_sec=1.5)
            chk_v = capture_screen()
            if is_battle_button_visible(chk_v):
                break

    # Chờ mây trắng tan hết khi về Làng chính để đọc số dư Vàng & Tiên dược
    home_gold, home_elixir = 0, 0
    for _ in range(12):
        h_img = capture_screen("home_after_battle.png")
        if h_img is not None and is_battle_button_visible(h_img):
            home_gold, home_elixir = read_home_resources(h_img)
            if home_gold > 0 or home_elixir > 0:
                break
        time.sleep(0.8)

    ready_wall = home_gold >= 10000000 and home_elixir >= 10000000
    log(
        f"[HOME] Đã về Làng chính! Vàng = {home_gold:,} | Tiên dược = {home_elixir:,} | Đủ >=10M mỗi loại: {ready_wall}"
    )
    return {
        "ok": True,
        "deployed": True,
        "won_100_percent": won_early,
        "battle_seconds": elapsed,
        "slots_final": slots_final,
        "home_gold": home_gold,
        "home_elixir": home_elixir,
        "ready_for_10m_wall_upgrade": ready_wall,
        "home_image": os.path.join(RUNTIME_DIR, "home_after_battle.png"),
    }


def prepare_village_wall_grid():
    """
    Thu nhỏ bản đồ Làng chính tối đa + khóa sát mép trên (Top-Stop) và kẻ lưới tọa độ (x,y)
    để Con số 1 (AI Planner) nhìn chọn chính xác tọa độ các viên Tường cần nâng.
    """
    close_all_modals()
    adb_shell("su -c 'sh /sdcard/do_pinch.sh'")
    time.sleep(1.0)
    adb_shell("input swipe 1110 250 1110 900 350")
    time.sleep(0.8)

    img = capture_screen("village_raw.png")
    if img is None:
        return {"ok": False, "error": "ADB_DISCONNECTED"}

    h_gold, h_elix = read_home_resources(img)
    grid_img = draw_coordinate_grid(img, show_battle_safe_box=False)
    grid_path = os.path.join(RUNTIME_DIR, "village_grid.png")
    cv2.imwrite(grid_path, grid_img)
    log(f"[VILLAGE-GRID] Đã chụp lưới Làng chính: Vàng={h_gold:,}, Tiên dược={h_elix:,} -> {grid_path}")
    return {
        "ok": True,
        "home_gold": h_gold,
        "home_elixir": h_elix,
        "ready_for_10m_wall_upgrade": (h_gold >= 10000000 and h_elix >= 10000000),
        "grid_image": grid_path,
    }


def upgrade_walls_batch(wall_points=None, use_gold=True, use_elixir=True):
    """
    Tự động nâng cấp tường bằng Vàng và Tiên dược tại danh sách tọa độ wall_points.
    Tự động phân bổ tài nguyên tối ưu, kiểm định nút xác nhận màu xanh lá (an toàn tuyệt đối 100% không đụng Gem).
    """
    if wall_points is None:
        wall_points = [
            (1195, 608), (1225, 585), (1255, 565), (1285, 545),
            (1060, 650), (1030, 630), (1000, 608), (970, 585), (945, 545),
            (1320, 750), (1350, 770), (1165, 630), (1135, 650)
        ]

    close_all_modals()
    img0 = capture_screen()
    if img0 is None:
        return {"ok": False, "error": "ADB_DISCONNECTED"}

    start_gold, start_elix = read_home_resources(img0)
    cur_gold, cur_elix = start_gold, start_elix
    batches = []

    for wx, wy in wall_points:
        for _ in range(8):
            close_all_modals()
            img_now = capture_screen()
            cur_gold, cur_elix = read_home_resources(img_now)
            if (not use_gold or cur_gold < 1500000) and (not use_elixir or cur_elix < 1500000):
                break

            tap(wx, wy, sleep_sec=0.6)
            img_bar = capture_screen("wall_bar_check.png")
            if not is_five_button_wall_bar(img_bar):
                break

            # Thứ tự ưu tiên tài nguyên: chọn tài nguyên nào >= 1.5M và đang có nhiều hơn
            choice_order = []
            if cur_gold >= 1500000 and (cur_elix < 1500000 or cur_gold >= cur_elix):
                if use_gold:
                    choice_order.append(("gold", 1213, 845))
                if use_elixir and cur_elix >= 1500000:
                    choice_order.append(("elixir", 1422, 845))
            else:
                if use_elixir and cur_elix >= 1500000:
                    choice_order.append(("elixir", 1422, 845))
                if use_gold and cur_gold >= 1500000:
                    choice_order.append(("gold", 1213, 845))

            upgraded_here = False
            for res_name, bx, by in choice_order:
                log(f"[WALL] Bấm nút nâng {res_name} tại ({bx}, {by})...")
                tap(bx, by, sleep_sec=0.8)
                img_modal = capture_screen()

                # Nếu hiện bảng hỏi mua bằng Gem (You Need More...) -> Lập tức đóng popup tại (1502, 339)
                crop_btn = img_modal[820:920, 1350:1600]
                hsv = cv2.cvtColor(crop_btn, cv2.COLOR_BGR2HSV)
                green_mask = cv2.inRange(hsv, (35, 80, 80), (85, 255, 255))
                green_cnt = int(np.sum(green_mask > 0))

                if green_cnt > 2000:
                    log(f"[WALL] Nút xác nhận XANH LÁ ({green_cnt} px) -> Xác nhận nâng cấp!")
                    tap(1482, 870, sleep_sec=1.5)
                    batches.append({"point": [wx, wy], "resource": res_name})
                    upgraded_here = True
                    break
                else:
                    log(f"[WALL] Nút không đạt chuẩn xanh ({green_cnt} px) -> Đóng hộp thoại an toàn!")
                    tap(1502, 339, sleep_sec=0.2)
                    tap(1830, 90, sleep_sec=0.4)

            if not upgraded_here:
                break

            # Kiểm chứng trực giao: chắc chắn Vàng hoặc Tiên dược đã giảm thực tế
            img_after = capture_screen()
            next_gold, next_elix = read_home_resources(img_after)
            if next_gold >= cur_gold and next_elix >= cur_elix:
                log(f"[WALL] Tài nguyên không giảm tại ({wx}, {wy}) -> chuyển sang tọa độ tường kế tiếp")
                break

    close_all_modals()
    img_end = capture_screen("last_wall_upgrade.png")
    end_gold, end_elix = read_home_resources(img_end)
    return {
        "ok": True,
        "before_gold": start_gold,
        "before_elixir": start_elix,
        "after_gold": end_gold,
        "after_elixir": end_elix,
        "gold_spent": max(0, start_gold - end_gold),
        "elixir_spent": max(0, start_elix - end_elix),
        "batches": batches,
        "proof_image": os.path.join(RUNTIME_DIR, "last_wall_upgrade.png"),
    }


def _parse_points(raw):
    pts = json.loads(raw)
    return [(int(p[0]), int(p[1])) for p in pts]


def main():
    parser = argparse.ArgumentParser(description="Clash of Clans V2 Action Executor (Con Gọi Tool Đánh)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Chụp màn hình kèm lưới tọa độ và kiểm tra trạng thái hiện tại")

    p_find = sub.add_parser("find-target", help="Tự bấm Next lọc nhà có Vàng >= min_gold VÀ Dầu >= min_elixir")
    p_find.add_argument("--min-gold", type=int, default=1000000)
    p_find.add_argument("--min-elixir", type=int, default=1000000)
    p_find.add_argument("--max-searches", type=int, default=60)

    p_atk = sub.add_parser("attack", help="Thực thi thả quân + thần chú theo tọa độ từ Con Báo Tọa Độ")
    p_atk.add_argument("--yeti", type=str, required=True, help="JSON list [[x,y], ...]")
    p_atk.add_argument("--wb", type=str, required=True, help="JSON list [[x,y], ...]")
    p_atk.add_argument("--clone", type=str, required=True, help="JSON list [[x,y], ...]")
    p_atk.add_argument("--rage", type=str, required=True, help="JSON list [[x,y], ...]")
    p_atk.add_argument("--no-wait", action="store_true")

    sub.add_parser("village-grid", help="Thu nhỏ làng Top-Stop và xuất ảnh kẻ lưới tọa độ để chọn Tường")

    p_zoom = sub.add_parser("zoom-out", help="Chụm 2 ngón tay thu nhỏ màn hình theo thao tác chuẩn của Sếp")
    p_zoom.add_argument("--repeats", type=int, default=1)

    p_scroll = sub.add_parser("scroll-upgrade", help="Lướt xuống danh sách nâng cấp Công trình / Nghiên cứu")
    p_scroll.add_argument("--repeats", type=int, default=1)

    p_wall = sub.add_parser("upgrade-walls", help="Nâng tường 1 thể tại danh sách tọa độ [[x,y], ...]")
    p_wall.add_argument("--points", type=str, required=True, help="JSON list [[x,y], ...]")

    sub.add_parser("power-save", help="Bật tối đa chế độ tiết kiệm pin + khôi phục sạc")
    sub.add_parser("sleep-screen", help="Tắt màn hình khi nghỉ để sạc pin nhanh")

    args = parser.parse_args()
    if args.cmd == "status":
        res = get_status(with_grid=True)
    elif args.cmd == "find-target":
        res = find_rich_target(args.min_gold, args.min_elixir, args.max_searches)
    elif args.cmd == "attack":
        res = execute_attack_plan(
            _parse_points(args.yeti),
            _parse_points(args.wb),
            _parse_points(args.clone),
            _parse_points(args.rage),
            wait_finish=not args.no_wait,
        )
    elif args.cmd == "village-grid":
        res = prepare_village_wall_grid()
    elif args.cmd == "zoom-out":
        res = zoom_out_pinch(repeats=args.repeats)
    elif args.cmd == "scroll-upgrade":
        res = scroll_upgrade_list(repeats=args.repeats)
    elif args.cmd == "upgrade-walls":
        res = upgrade_walls_batch(_parse_points(args.points))
    elif args.cmd == "power-save":
        res = apply_ultra_battery_saver(keep_awake=True)
    elif args.cmd == "sleep-screen":
        res = sleep_screen()
    else:
        res = {"ok": False, "error": "UNKNOWN_COMMAND"}

    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
