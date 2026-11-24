import os
import sys
import json
import time
import cv2
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
STATUS_JSON = os.path.join(RUNTIME_DIR, "loop_farm_status.json")
RESOURCE_BAR_PNG = os.path.join(RUNTIME_DIR, "home_resource_bar_latest.png")
sys.path.insert(0, BASE_DIR)

import coc_executor_tools as cet
import coc_vision_grid as cvg
import phan1_vao_tran_soi_nha as p1
import phan2_tha_quan_ve_lang as p2
import upgrade_manager_tools as umt
import wall_upgrade_vision_manager as wum

BATTERY_MIN_THRESHOLD = 0
BATTERY_RESUME_THRESHOLD = 0
STOP_RESOURCE_THRESHOLD = 23_000_000
STOP_DARK_ELIXIR_THRESHOLD = 300_000
WALL_RETURN_TO_FARM_THRESHOLD = 0
ERROR_ALERT_JSON = os.path.join(RUNTIME_DIR, "loop_error_alert.json")


def load_dynamic_thresholds():
    """Đọc ngưỡng dừng cày động từ config/upgrade_priority.json (cho phép sửa không cần sửa code)."""
    try:
        cfg = umt.load_upgrade_priority_config()
        th = cfg.get("resource_stop_thresholds", {})
        return (
            int(th.get("gold", STOP_RESOURCE_THRESHOLD)),
            int(th.get("elixir", STOP_RESOURCE_THRESHOLD)),
            int(th.get("dark_elixir", STOP_DARK_ELIXIR_THRESHOLD)),
            int(th.get("wall_return_to_farm", WALL_RETURN_TO_FARM_THRESHOLD)),
        )
    except Exception:
        return (
            STOP_RESOURCE_THRESHOLD,
            STOP_RESOURCE_THRESHOLD,
            STOP_DARK_ELIXIR_THRESHOLD,
            WALL_RETURN_TO_FARM_THRESHOLD,
        )


def write_loop_error_alert(reason, cycle=0, exc_text="", screenshot=None):
    """Ghi cảnh báo lỗi có cấu trúc và ảnh chụp hiện trường để AI điều phối xử lý sự cố."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    shot_path = None
    if screenshot is not None:
        alert_dir = os.path.join(RUNTIME_DIR, "alerts")
        os.makedirs(alert_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot_path = os.path.join(alert_dir, f"loop_err_{ts}.png")
        cv2.imwrite(shot_path, screenshot)
    payload = {
        "alert": True,
        "source": "loop_cay_tai_nguyen_doc_lap",
        "cycle": cycle,
        "reason": reason,
        "detail": exc_text,
        "screenshot_path": shot_path,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    tmp_path = ERROR_ALERT_JSON + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, ERROR_ALERT_JSON)
    except Exception:
        pass
    return payload


def all_three_thresholds_reached(
    gold,
    elixir,
    dark_elixir,
    threshold=STOP_RESOURCE_THRESHOLD,
    de_threshold=STOP_DARK_ELIXIR_THRESHOLD,
    elixir_threshold=None,
):
    """Kiểm tra điều kiện dừng/nâng tường: Nếu de_threshold <= 0 thì chỉ cần Vàng >= ngưỡng VÀ Dầu tím >= ngưỡng."""
    e_th = threshold if elixir_threshold is None else elixir_threshold
    base_check = (gold >= threshold and elixir >= e_th)
    if de_threshold <= 0:
        return base_check
    return base_check and dark_elixir >= de_threshold


def write_farm_status(payload):
    """Lưu trạng thái vòng lặp cày và tài nguyên nhà mới nhất ra JSON."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp_path = STATUS_JSON + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        for _retry in range(3):
            try:
                os.replace(tmp_path, STATUS_JSON)
                break
            except PermissionError:
                time.sleep(0.5)
        else:
            try:
                os.remove(STATUS_JSON)
                os.rename(tmp_path, STATUS_JSON)
            except Exception:
                pass
    except Exception:
        pass


def ensure_at_home():
    for _ in range(10):
        if not cet.ensure_game_foreground():
            continue
        img = cet.capture_screen()
        if img is None:
            time.sleep(1.0)
            continue
        if cvg.is_inactivity_reload_dialog(img):
            cet.log("[RELOAD-GUARD] Phát hiện hộp thoại 'Anyone there? / RELOAD GAME' -> Bấm (740, 622)...")
            cet.tap(740, 622, sleep_sec=7.0)
            continue
        if cvg.is_reload_game_dialog(img):
            cet.log("[RELOAD-GUARD] Phát hiện hộp thoại 'Reload game' -> Bấm nạp lại game...")
            cet.tap(1038, 970, sleep_sec=6.0)
            continue
        if cvg.is_builder_base(img):
            cet.log("[BUILDER-BASE-GUARD] Phát hiện đang lạc sang Làng Thợ! Bấm thuyền quay về Làng chính...")
            if umt.return_from_builder_base_to_home(img):
                continue
            cet.log("[BUILDER-BASE-GUARD] Không thấy thuyền ngay -> Khởi động lại game để về đúng Làng chính...")
            umt.restart_game_to_home(reason="detected_builder_base", screenshot=img)
            continue
        if cvg.is_battle_button_visible(img):
            return img
        if cvg.is_return_home_visible(img):
            p2.dismiss_return_home_safely()
            continue
        if cvg.is_in_battle(img):
            cet.tap(135, 805, sleep_sec=0.9)
            cet.tap(1320, 680, sleep_sec=1.8)
            p2.dismiss_return_home_safely()
            continue
        cet.close_all_modals()
        time.sleep(1.0)
    return cet.capture_screen()


def inspect_home_resources(img_home=None):
    """
    Chụp màn hình Làng chính, cắt vùng thanh tài nguyên (BOX_RESOURCE_BAR)
    và dùng AI Vision đọc lượng Vàng / Dầu tím / Dầu đen còn lại ở nhà.
    """
    img = img_home if img_home is not None else ensure_at_home()
    if img is None:
        return 0, 0, 0

    for attempt in range(3):
        if attempt > 0:
            time.sleep(1.0)
            img = ensure_at_home()
            if img is None:
                continue
        gold, elixir, dark_elixir = cvg.read_all_home_resources(img)
        if gold > 0 or elixir > 0 or dark_elixir > 0:
            bar_crop = cvg.crop_home_resource_bar(img)
            if bar_crop is not None:
                os.makedirs(RUNTIME_DIR, exist_ok=True)
                cv2.imwrite(RESOURCE_BAR_PNG, bar_crop)
            return gold, elixir, dark_elixir
    return 0, 0, 0


def confirm_home_threshold_reached(
    gold,
    elixir,
    dark_elixir,
    threshold=STOP_RESOURCE_THRESHOLD,
    de_threshold=STOP_DARK_ELIXIR_THRESHOLD,
):
    """Xác nhận 2 lần liên tiếp nếu cả 3 tài nguyên đồng thời chạm ngưỡng dừng."""
    if not all_three_thresholds_reached(gold, elixir, dark_elixir, threshold, de_threshold):
        return False, gold, elixir, dark_elixir
    time.sleep(0.5)
    img_confirm = cet.capture_screen()
    if img_confirm is not None and cvg.is_battle_button_visible(img_confirm):
        g2, e2, de2 = cvg.read_all_home_resources(img_confirm)
        if g2 > 0 or e2 > 0 or de2 > 0:
            gold, elixir, dark_elixir = g2, e2, de2
    return (
        all_three_thresholds_reached(gold, elixir, dark_elixir, threshold, de_threshold),
        gold,
        elixir,
        dark_elixir,
    )


def handle_home_resource_decision(gold, elixir, dark_elixir, cycle, phase_label, auto_upgrade_walls=True, no_stop=False):
    """
    Đọc quyết định dựa trên cả 3 tài nguyên nhà và cấu hình ngưỡng động:
    - Chưa đủ CẢ 3: cày tiếp.
    - Đạt đủ CẢ 3:
      + Nếu no_stop=True và auto_upgrade_walls=False: bỏ qua điểm dừng, cày liên tục.
      + Ngược lại: dừng cày; nếu bật auto_upgrade_walls thì gọi Con Nâng Tường nâng xuống ngưỡng wall_return_to_farm rồi quay lại cày.
    """
    g_th, e_th, de_th, wall_th = load_dynamic_thresholds()
    de_msg = f", DE >= {de_th:,}" if de_th > 0 else " (Đã tắt điều kiện Dầu đen)"
    cet.log(
        f"[VISION LÀNG CHÍNH - {phase_label}] Vàng = {gold:,} | Dầu tím = {elixir:,} | Dầu đen = {dark_elixir:,} "
        f"(Ngưỡng nâng tường: Vàng >= {g_th:,}, Dầu tím >= {e_th:,}{de_msg})"
    )
    reached, gold, elixir, dark_elixir = confirm_home_threshold_reached(
        gold, elixir, dark_elixir, g_th, de_th
    )
    reached = all_three_thresholds_reached(gold, elixir, dark_elixir, g_th, de_th, elixir_threshold=e_th)
    if not reached:
        cond_str = f"{g_th:,}/{e_th:,}/{de_th:,}" if de_th > 0 else f"Vàng {g_th:,} & Dầu tím {e_th:,}"
        cet.log(f"➡️ [QUYẾT ĐỊNH] Chưa đủ ngưỡng ({cond_str}) -> Tiếp tục cày!")
        write_farm_status({
            "phase": "farming_continue",
            "cycle": cycle,
            "home_gold": gold,
            "home_elixir": elixir,
            "home_dark_elixir": dark_elixir,
            "stop_threshold": g_th,
            "stop_elixir_threshold": e_th,
            "stop_dark_elixir_threshold": de_th,
        })
        return "CONTINUE_FARM"

    reached_str = "CẢ 3 NGƯỠNG" if de_th > 0 else "CẢ 2 NGƯỠNG (Vàng & Dầu tím >= 23M)"
    cet.log(
        f"🚨 [QUYẾT ĐỊNH] Kho đạt đủ {reached_str} (Vàng = {gold:,} | Dầu tím = {elixir:,} | Dầu đen = {dark_elixir:,})!"
    )
    if not auto_upgrade_walls:
        if no_stop:
            cet.log("♾️ [CHẾ ĐỘ LIÊN TỤC] Đã bật --no-stop -> Không dừng khi đầy kho, tiếp tục cày!")
            write_farm_status({
                "phase": "farming_continuous",
                "cycle": cycle,
                "home_gold": gold,
                "home_elixir": elixir,
                "home_dark_elixir": dark_elixir,
                "stop_threshold": g_th,
                "stop_elixir_threshold": e_th,
                "stop_dark_elixir_threshold": de_th,
                "no_stop": True,
            })
            return "CONTINUE_FARM"
        cet.log("🛑 Đã dừng vòng lặp cày (chế độ chỉ cày, đạt đủ 3 ngưỡng).")
        write_farm_status({
            "phase": "stopped_resource_target_reached",
            "cycle": cycle,
            "home_gold": gold,
            "home_elixir": elixir,
            "home_dark_elixir": dark_elixir,
            "stop_threshold": g_th,
            "stop_elixir_threshold": e_th,
            "stop_dark_elixir_threshold": de_th,
        })
        return "STOP_FARM_ONLY"

    cet.log(f"🧱 >>> DỪNG CÀY -> GỌI CON NÂNG TƯỜNG RA NÂNG XUỐNG KHOẢNG {wall_th:,}! <<<")
    write_farm_status({
        "phase": "calling_wall_upgrade_bot",
        "cycle": cycle,
        "home_gold": gold,
        "home_elixir": elixir,
        "home_dark_elixir": dark_elixir,
        "wall_stop_threshold": wall_th,
    })

    import importlib
    importlib.reload(wum)
    wall_res = wum.run_wall_upgrade_session(stop_threshold=wall_th)
    cet.log(f"🧱 [KẾT QUẢ CON NÂNG TƯỜNG]: {wall_res}")

    img_after_wall = ensure_at_home()
    g_post, e_post, de_post = inspect_home_resources(img_after_wall)
    cet.log(
        f"🌾 [CHUYỂN GIAO] Sau khi nâng tường còn Vàng = {g_post:,} | Dầu tím = {e_post:,} | Dầu đen = {de_post:,} -> GỌI LẠI CON LOOP CÀY!"
    )
    write_farm_status({
        "phase": "wall_finished_resuming_farm",
        "cycle": cycle,
        "home_gold": g_post,
        "home_elixir": e_post,
        "home_dark_elixir": de_post,
        "wall_result": wall_res,
    })
    return "UPGRADED_RESUME_FARM"


def _check_home_and_maybe_upgrade(cycle, phase_label, auto_upgrade_walls, img_home=None, no_stop=False):
    """Kiểm tra kho 3 tài nguyên ở Làng chính; trả về (should_stop, gold, elixir, dark_elixir)."""
    img = img_home if img_home is not None else ensure_at_home()
    h_gold, h_elix, h_de = inspect_home_resources(img)
    decision = handle_home_resource_decision(
        h_gold, h_elix, h_de, cycle, phase_label, auto_upgrade_walls=auto_upgrade_walls, no_stop=no_stop
    )
    if decision == "STOP_FARM_ONLY":
        return True, h_gold, h_elix, h_de
    if decision == "UPGRADED_RESUME_FARM":
        g_th, e_th, de_th, _ = load_dynamic_thresholds()
        img_chk = ensure_at_home()
        g_chk, e_chk, de_chk = inspect_home_resources(img_chk)
        if all_three_thresholds_reached(g_chk, e_chk, de_chk, g_th, de_th, elixir_threshold=e_th):
            cet.log(f"⚠️ Kho vẫn đạt đủ 3 ngưỡng ({g_th:,}/{e_th:,}/{de_th:,}) sau nâng cấp -> Tạm dừng an toàn.")
            return True, g_chk, e_chk, de_chk
        return False, g_chk, e_chk, de_chk
    return False, h_gold, h_elix, h_de


def run_pure_farm_loop(auto_upgrade_walls=True, no_stop=False):
    cet.reset_live_session_log()
    g_th, e_th, de_th, wall_th = load_dynamic_thresholds()
    cet.log("==================================================")
    cet.log("🚀 BẮT ĐẦU VÒNG LẶP CÀY TÀI NGUYÊN KHÉP KÍN (VISION + AUTO HANDOFF)")
    cet.log("   - Đánh trận: Vàng >= 1,000,000 VÀ Dầu >= 1,000,000")
    if no_stop and not auto_upgrade_walls:
        cet.log("   - Chế độ: CHẠY LIÊN TỤC KHÔNG ĐIỂM DỪNG (--no-stop)")
    else:
        cet.log(
            f"   - Dừng khi ĐỒNG THỜI: Vàng >= {g_th:,} VÀ Dầu tím >= {e_th:,} "
            f"VÀ Dầu đen >= {de_th:,}"
        )
    if auto_upgrade_walls:
        cet.log(f"   - Con Nâng Tường hạ kho xuống <= {wall_th:,} rồi gọi lại Con Loop Cày")
    cet.log("==================================================")

    cet.adb_shell("settings put system pointer_location 0")

    cycle = 0
    consecutive_errors = 0
    while True:
        batt = cet.get_battery_info()
        cap = batt.get("capacity", 100)
        if 0 < cap < BATTERY_MIN_THRESHOLD:
            cet.log(f"[BATTERY-GUARD] Pin {cap}% < {BATTERY_MIN_THRESHOLD}%! Nghỉ sạc lên {BATTERY_RESUME_THRESHOLD}%...")
            cet.sleep_and_fast_charge_until(target_percent=BATTERY_RESUME_THRESHOLD, check_interval_sec=45)
            ensure_at_home()
            continue

        cet.apply_ultra_battery_saver(keep_awake=True)
        img_home = ensure_at_home()
        if img_home is None:
            consecutive_errors += 1
            cet.log(f"[WARN] Không chụp được ảnh Làng chính (lần {consecutive_errors}/3)")
            if consecutive_errors >= 3:
                alert = write_loop_error_alert("home_screen_capture_failed_3x", cycle=cycle)
                cet.log(f"🚨 [ALERT-TO-AI] Ghi {ERROR_ALERT_JSON} -> tự khởi động lại CoC...")
                umt.restart_game_to_home(reason="loop_home_capture_failed_3x")
                consecutive_errors = 0
            time.sleep(2.0)
            continue

        should_stop, h_gold, h_elix, h_de = _check_home_and_maybe_upgrade(
            cycle, "TRƯỚC TRẬN", auto_upgrade_walls, img_home=img_home, no_stop=no_stop
        )
        if should_stop:
            break

        cycle += 1
        cet.log(f"\n>>> [CHU KỲ CÀY #{cycle}] Bắt đầu dò trận...")
        write_farm_status({
            "phase": "scouting_and_battling",
            "cycle": cycle,
            "home_gold": h_gold,
            "home_elixir": h_elix,
            "home_dark_elixir": h_de,
            "stop_threshold": g_th,
            "stop_elixir_threshold": e_th,
            "stop_dark_elixir_threshold": de_th,
        })

        try:
            res_scout = p1.run_scout_loop_and_attack(min_gold=1_000_000, min_elixir=1_000_000, max_searches=60)
            cet.log(f"[CHU KỲ CÀY #{cycle}] Kết quả: {res_scout}")
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            cet.log(f"[CHU KỲ CÀY #{cycle}] Ngoại lệ ({consecutive_errors}/3): {e}")
            write_loop_error_alert("scout_or_battle_exception", cycle=cycle, exc_text=str(e), screenshot=cet.capture_screen())
            if consecutive_errors >= 3:
                cet.log("🚨 [ALERT-TO-AI] Vòng cày gặp lỗi liên tiếp 3 lần -> tự reset app về Làng chính và báo cảnh báo!")
                umt.restart_game_to_home(reason="loop_exception_3x", screenshot=cet.capture_screen())
                consecutive_errors = 0

        # Về Làng chính an toàn, chờ HUD ổn định rồi bật Vision đọc tài nguyên còn lại ở nhà
        time.sleep(2.0)
        should_stop_after, _, _, _ = _check_home_and_maybe_upgrade(
            cycle, f"SAU TRẬN #{cycle}", auto_upgrade_walls, no_stop=no_stop
        )
        if should_stop_after:
            break

        time.sleep(3.0)


if __name__ == "__main__":
    import traceback
    no_wall = "--no-wall" in sys.argv
    no_stop = "--no-stop" in sys.argv
    try:
        run_pure_farm_loop(auto_upgrade_walls=not no_wall, no_stop=no_stop)
    except Exception:
        tb = traceback.format_exc()
        cet.log(f"🚨 [FATAL-CRASH] Vòng lặp gặp lỗi nghiêm trọng:\n{tb}")
        try:
            write_loop_error_alert("fatal_loop_crash", cycle=0, exc_text=tb, screenshot=cet.capture_screen())
        except Exception:
            pass
        raise
