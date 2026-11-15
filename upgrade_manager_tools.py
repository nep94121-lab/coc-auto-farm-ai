"""
Tool điều phối tọa độ Xây dựng / Nâng cấp Công trình, Nghiên cứu Lab và Thú cưng (Galaxy S9 2220x1080).
Tất cả tọa độ bấm do Sếp hiệu chuẩn trực tiếp; khung ảnh OCR/Vision được cập nhật theo từng ảnh mẫu.
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta

import cv2
import numpy as np

import coc_executor_tools as cet
import coc_vision_grid as cvg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PRIORITY_CONFIG_PATH = os.environ.get(
    "COC_PRIORITY_CONFIG",
    os.path.join(BASE_DIR, "config", "upgrade_priority.json"),
)
DEFAULT_PRIORITY_CONFIG = {
    "builder_focus": {
        "target_builders": 6,
        "focus_mode": "focus_until_max",
        "priority_targets": [
            {"name": "Archer Tower", "max_level": 21, "notes": "Nang toi Max Level 21"},
            {"name": "Cannon", "max_level": 21, "notes": "Nang toi Max Level 21"},
        ],
        "fallback_targets": [
            "Grand Warden",
            "Barbarian King",
            "Archer Queen",
            "Royal Champion",
            "Minion Prince",
            "Dragon Duke",
        ],
        "max_scrolls_to_search": 5,
    },
    "research_priority": {
        "notes": "AI doc full_3_lab.png va full_3b_lab_scrolled.png de chon muc nghien cuu"
    },
    "resource_stop_thresholds": {
        "gold": 23000000,
        "elixir": 23000000,
        "dark_elixir": 300000,
        "wall_return_to_farm": 3000000,
    },
}


# =====================================================================
# 1. TỌA ĐỘ CỐ ĐỊNH DO SẾP CUNG CẤP (2220x1080)
# =====================================================================
# 3 vị trí chọn mục nâng cấp bổ sung dùng chung cho cả Công trình (Build) và Nghiên cứu (Lab)
SHARED_UPGRADE_PICK_POSITIONS = {
    "pick_alt_1": (1820, 737),
    "pick_alt_2": (1794, 831),
    "pick_alt_3": (1801, 898),
}

# 8 vị trí hàng danh sách SAU KHI lướt xuống (scroll_upgrade_list), dùng chung cho Công trình & Nghiên cứu
SCROLL_LIST_PICK_POSITIONS = {
    "scroll_pick_1": (1868, 137),
    "scroll_pick_2": (1728, 236),
    "scroll_pick_3": (1894, 333),
    "scroll_pick_4": (1839, 445),
    "scroll_pick_5": (1816, 528),
    "scroll_pick_6": (1780, 644),  # Chuẩn hóa từ 'x 178, y 644' (nằm trong danh sách x=1616..2219)
    "scroll_pick_7": (1775, 722),
    "scroll_pick_8": (1797, 836),
}

COORDS_BUILD = {
    "open_build_menu": (2093, 966),     # Ấn vào cái búa để mở bảng xây dựng / nâng cấp
    "filter_button": (1672, 41),        # Chọn vào phần lọc (nút phễu trên bảng)
    "filter_option": (1308, 741),       # Chọn vào tùy chọn trong phần lọc
    "tap_outside": (2020, 513),         # Chọn ra ngoài
    "select_product": (1843, 644),      # Chọn sản phẩm để nâng cấp
    "slot_1": (1748, 279),              # Vị trí nâng cấp thứ 1
    "slot_2": (1754, 460),              # Vị trí nâng cấp thứ 2
    "slot_3": (1758, 637),              # Vị trí nâng cấp thứ 3
    "confirm_upgrade": (1486, 959),     # Vị trí thứ 4 (Xác nhận nâng cấp)
    "modal_close": (1846, 85),          # Nút X đỏ đóng popup chi tiết nâng cấp
    "close_upgrade_panel": (1800, 38),  # Thoát bảng nâng cấp để về Làng chính (hiện nút Battle)
    **SHARED_UPGRADE_PICK_POSITIONS,
    **SCROLL_LIST_PICK_POSITIONS,
}

COORDS_RESEARCH = {
    "open_lab": (1812, 1011),           # Vào kho nghiên cứu (Laboratory)
    "select_item": (1854, 561),         # Chọn nghiên cứu mặc định
    "confirm": (1470, 943),             # Xác nhận nghiên cứu
    "modal_close": (1846, 85),          # Nút X đỏ đóng popup chi tiết nghiên cứu
    **SHARED_UPGRADE_PICK_POSITIONS,
    **SCROLL_LIST_PICK_POSITIONS,
}

COORDS_PET = {
    "open_pet_house": (2166, 1009),     # Vào nghiên cứu thú cưng (Hero Pets)
    "select_item": (1849, 564),         # Chọn thú cưng cần nâng
    "confirm": (1496, 949),             # Xác nhận nâng cấp thú cưng
}

# Khung vùng nhìn (x1, y1, x2, y2) của các ảnh trạng thái & khung popup xác nhận nâng cấp
VISION_BOXES = {
    "img1_builder_lab_badge": (1974, 740, 2208, 1065),
    "img1_builder_count": (1988, 766, 2086, 860),
    "img1_lab_count": (2096, 766, 2194, 860),
    "img1_build_button": (1988, 864, 2194, 1052),
    "shifted_resources": (1175, 25, 1612, 240),
    "img2_buildings_list": (1616, 72, 2219, 920),
    "img3_research_list": (1610, 71, 2205, 920),
    "img4_hero_pets_list": (1622, 35, 2220, 209),
    "modal_full": (320, 35, 1900, 1045),
    "modal_title_level": (420, 45, 1780, 165),
    "modal_confirm_footer": (950, 845, 1890, 1035),
}


def _tap_pt(pt, sleep_sec=0.8, label=""):
    x, y = pt
    if label:
        cet.log(f"[UPGRADE-TOOL] {label} -> ({x}, {y})")
    return cet.tap(x, y, sleep_sec=sleep_sec)


# =====================================================================
# 2. CÁC HÀM THAO TÁC THEO QUY TRÌNH
# =====================================================================
def open_build_panel(sleep_sec=0.9):
    """Mở bảng xây dựng / nâng cấp từ Làng chính (nút cái búa)."""
    return _tap_pt(COORDS_BUILD["open_build_menu"], sleep_sec=sleep_sec, label="Mở búa Build")


def close_upgrade_panel_to_home(verify=True, sleep_sec=0.8, zoom_out=True):
    """Thoát khỏi vùng nâng cấp về Làng chính, bỏ chọn công trình và tự động thu nhỏ camera."""
    for idx, (pt, lbl) in enumerate(
        (
            (COORDS_BUILD["close_upgrade_panel"], "Thoát vùng nâng cấp về Làng chính"),
            ((2165, 41), "Bấm nút X đỏ đóng ngăn kéo về Làng chính"),
        ),
        1,
    ):
        _tap_pt(pt, sleep_sec=sleep_sec, label=lbl)
        if not verify:
            if zoom_out:
                cet.zoom_out_pinch(repeats=1)
                cet.tap(1800, 420, sleep_sec=0.25)
            return {"ok": True, "screen": "unverified", "method": lbl, "zoom_out": zoom_out}
        img = cet.capture_screen()
        if img is not None and cvg.is_battle_button_visible(img):
            zoom_res = None
            if zoom_out:
                zoom_res = cet.zoom_out_pinch(repeats=1)
                cet.tap(1800, 420, sleep_sec=0.25)
            return {"ok": True, "screen": "home", "attempts": idx, "closed_by": pt, "zoom_out": zoom_res}
    rec = restart_game_to_home(reason="close_panel_failed_to_show_battle", screenshot=cet.capture_screen())
    return rec


def apply_build_filter(sleep_sec=0.7):
    """Mở phần lọc, chọn mục lọc, rồi bấm ra ngoài để đóng menu lọc."""
    _tap_pt(COORDS_BUILD["filter_button"], sleep_sec=sleep_sec, label="Mở phần lọc")
    _tap_pt(COORDS_BUILD["filter_option"], sleep_sec=sleep_sec, label="Chọn phần lọc")
    _tap_pt(COORDS_BUILD["tap_outside"], sleep_sec=sleep_sec, label="Chọn ra ngoài")


def load_upgrade_priority_config(config_path=None):
    """Đọc cấu hình ưu tiên nâng cấp động từ JSON; tự hợp nhất mặc định nếu thiếu trường."""
    path = config_path or DEFAULT_PRIORITY_CONFIG_PATH
    cfg = json.loads(json.dumps(DEFAULT_PRIORITY_CONFIG))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            for section in ("builder_focus", "research_priority", "resource_stop_thresholds"):
                if isinstance(loaded.get(section), dict):
                    cfg[section].update(loaded[section])
    return cfg


def save_upgrade_priority_config(cfg, config_path=None):
    """Lưu cấu hình ưu tiên nâng cấp ra file JSON (UTF-8, LF)."""
    path = config_path or DEFAULT_PRIORITY_CONFIG_PATH
    _save_json_atomic(path, cfg)
    return path


def parse_priority_spec(spec_text):
    """Phân tích chuỗi cấu hình ưu tiên dạng 'Archer Tower:21,Cannon:21'."""
    targets = []
    for raw in str(spec_text or "").split(","):
        item = raw.strip()
        if not item:
            continue
        if ":" in item:
            name, lvl_txt = item.rsplit(":", 1)
            max_lvl = int(lvl_txt.strip()) if lvl_txt.strip().isdigit() else 21
        else:
            name, max_lvl = item, 21
        targets.append({"name": name.strip(), "max_level": max_lvl})
    if not targets:
        raise ValueError("Chuỗi ưu tiên không có mục hợp lệ")
    return targets


def select_upgrade_pick(mode="build", pick_key=None, scrolls=0, sleep_sec=0.8):
    """Tùy chọn lướt xuống N nhịp rồi chọn mục cần nâng cấp cho Build ('build') hoặc Research ('research')."""
    if mode == "build":
        table = COORDS_BUILD
        key = pick_key or "select_product"
        label = f"Chọn công trình nâng cấp ({key})"
    elif mode == "research":
        table = COORDS_RESEARCH
        key = pick_key or "select_item"
        label = f"Chọn nghiên cứu ({key})"
    else:
        raise ValueError(f"mode không hợp lệ: {mode}")
    if key not in table:
        raise ValueError(f"Không tìm thấy pick_key='{key}' trong mode='{mode}'")
    if scrolls and int(scrolls) > 0:
        cet.scroll_upgrade_list(repeats=int(scrolls), sleep_sec=0.35)
    return _tap_pt(table[key], sleep_sec=sleep_sec, label=label)


def select_build_product(pick_key="select_product", scrolls=0, sleep_sec=0.8):
    """Chọn sản phẩm cần nâng cấp trong danh sách Build."""
    return select_upgrade_pick(mode="build", pick_key=pick_key, scrolls=scrolls, sleep_sec=sleep_sec)


def upgrade_build_slot(slot_index=1, confirm=True, sleep_sec=0.8):
    """
    Chọn vị trí nâng cấp (1..3) và tùy chọn bấm xác nhận vị trí thứ 4.
    """
    slot_key = f"slot_{slot_index}"
    if slot_key not in COORDS_BUILD:
        raise ValueError(f"slot_index phải từ 1..3, nhận {slot_index}")
    _tap_pt(COORDS_BUILD[slot_key], sleep_sec=sleep_sec, label=f"Chọn vị trí nâng cấp #{slot_index}")
    if confirm:
        _tap_pt(COORDS_BUILD["confirm_upgrade"], sleep_sec=sleep_sec, label="Xác nhận nâng cấp (vị trí 4)")


def run_research_upgrade(pick_key="select_item", scrolls=0, confirm=True, open_hammer_first=False, sleep_sec=0.8):
    """Mở tab Kho nghiên cứu, tùy chọn lướt xuống N nhịp, chọn mục nghiên cứu và xác nhận."""
    if open_hammer_first:
        open_build_panel(sleep_sec=sleep_sec)
    _tap_pt(COORDS_RESEARCH["open_lab"], sleep_sec=sleep_sec, label="Vào kho nghiên cứu")
    select_upgrade_pick(mode="research", pick_key=pick_key, scrolls=scrolls, sleep_sec=sleep_sec)
    if confirm:
        _tap_pt(COORDS_RESEARCH["confirm"], sleep_sec=sleep_sec, label="Xác nhận nghiên cứu")


def run_pet_upgrade(confirm=True, open_hammer_first=False, sleep_sec=0.8):
    """Mở tab Nghiên cứu thú cưng, chọn thú cưng và xác nhận."""
    if open_hammer_first:
        open_build_panel(sleep_sec=sleep_sec)
    _tap_pt(COORDS_PET["open_pet_house"], sleep_sec=sleep_sec, label="Vào nghiên cứu thú cưng")
    _tap_pt(COORDS_PET["select_item"], sleep_sec=sleep_sec, label="Chọn thú cưng cần nâng")
    if confirm:
        _tap_pt(COORDS_PET["confirm"], sleep_sec=sleep_sec, label="Xác nhận nâng cấp thú cưng")


def open_and_filter_build_menu(sleep_sec=0.8):
    """Quy trình chuẩn của Sếp: Bấm Búa -> Phần lọc -> Mục lọc -> Bấm ra ngoài đóng menu lọc."""
    open_build_panel(sleep_sec=sleep_sec)
    apply_build_filter(sleep_sec=sleep_sec)


def execute_build_4step_confirm(pick_key="select_product", scrolls=0, confirm=True, sleep_sec=0.8):
    """Chọn sản phẩm nâng cấp (có thể lướt trước) rồi bấm lần lượt 4 vị trí (slot_1..3 -> confirm_upgrade)."""
    select_build_product(pick_key=pick_key, scrolls=scrolls, sleep_sec=sleep_sec)
    _tap_pt(COORDS_BUILD["slot_1"], sleep_sec=sleep_sec, label="Xác nhận bước 1 (slot_1)")
    _tap_pt(COORDS_BUILD["slot_2"], sleep_sec=sleep_sec, label="Xác nhận bước 2 (slot_2)")
    _tap_pt(COORDS_BUILD["slot_3"], sleep_sec=sleep_sec, label="Xác nhận bước 3 (slot_3)")
    if confirm:
        _tap_pt(COORDS_BUILD["confirm_upgrade"], sleep_sec=sleep_sec, label="Xác nhận bước 4 (confirm_upgrade)")


def _check_confirm_button_color(img):
    """Đo nhanh vùng nút Confirm bên dưới popup để biết có nút xanh lá hợp lệ hay đang thiếu tài nguyên/đã Max."""
    if img is None:
        return "unknown"
    btn_crop = img[890:1015, 1180:1570]
    b, g, r = btn_crop[:, :, 0], btn_crop[:, :, 1], btn_crop[:, :, 2]
    green_px = int(np.sum((g > 150) & (g > r + 20) & (g > b + 35)))
    if green_px >= 2500:
        return "green_confirm_available"
    red_px = int(np.sum((r > 160) & (g < 100) & (b < 100)))
    if red_px >= 1200:
        return "red_or_insufficient"
    return "no_confirm_button_visible"


def scan_upgrade_pages(mode="build", max_scrolls=None, apply_filter=True, out_dir=None):
    """
    Lướt nhiều trang trong danh sách Buildings & Heroes hoặc Lab để AI tìm chính xác công trình ưu tiên (vd Archer Tower / Cannon).
    Trả về đường dẫn từng trang page_0.png .. page_N.png kèm cấu hình priority hiện hành.
    """
    cfg = load_upgrade_priority_config()
    scroll_limit = int(max_scrolls if max_scrolls is not None else cfg["builder_focus"].get("max_scrolls_to_search", 5))
    save_dir = out_dir or os.path.join(cet.RUNTIME_DIR, f"scan_{mode}")
    os.makedirs(save_dir, exist_ok=True)

    img_home = _ensure_home_or_restart()
    if img_home is None:
        return {"ok": False, "reason": "home_unreachable"}

    if mode == "build":
        if apply_filter:
            open_and_filter_build_menu(sleep_sec=0.8)
        else:
            open_build_panel(sleep_sec=0.9)
    elif mode == "research":
        open_build_panel(sleep_sec=0.9)
        _tap_pt(COORDS_RESEARCH["open_lab"], sleep_sec=0.9, label="Mở Lab để quét trang")
    else:
        raise ValueError(f"mode không hợp lệ: {mode}")

    img_first = cet.capture_screen()
    if not cvg.is_upgrade_drawer_open(img_first):
        rec = restart_game_to_home(reason=f"scan_{mode}_drawer_missing", screenshot=img_first)
        return {"ok": False, "reason": "out_of_scope_restarted", "recovery": rec}

    pages = []
    p0 = os.path.join(save_dir, "page_0.png")
    cv2.imwrite(p0, img_first)
    pages.append({"scrolls": 0, "path": p0})

    for step in range(1, scroll_limit + 1):
        cet.scroll_upgrade_list(repeats=1, sleep_sec=0.35)
        img_p = cet.capture_screen()
        ppath = os.path.join(save_dir, f"page_{step}.png")
        if img_p is not None:
            cv2.imwrite(ppath, img_p)
            pages.append({"scrolls": step, "path": ppath})

    exit_res = close_upgrade_panel_to_home(verify=True)
    result = {
        "ok": bool(exit_res.get("ok")),
        "mode": mode,
        "priority_config": cfg["builder_focus"],
        "pages": pages,
        "home": exit_res,
    }
    _save_json_atomic(os.path.join(save_dir, "scan_manifest.json"), result)
    return result


def inspect_upgrade_modal(pick_key="scroll_pick_1", mode="build", scrolls=0, apply_filter=True, out_dir=None, close_modal=True):
    """
    Mở bảng nâng cấp -> lướt N nhịp -> bấm chọn pick_key NHƯNG KHÔNG bấm Confirm,
    chụp toàn cảnh popup 'Upgrade <Tên> to Level X?' cùng thanh tiến độ màu xanh & chi phí/thời gian,
    giúp AI kiểm tra cấp hiện tại so với max_level trước khi quyết định xác nhận nâng.
    """
    cfg = load_upgrade_priority_config()
    save_dir = out_dir or os.path.join(cet.RUNTIME_DIR, "inspect_modal")
    os.makedirs(save_dir, exist_ok=True)

    img_home = _ensure_home_or_restart()
    if img_home is None:
        return {"ok": False, "reason": "home_unreachable"}

    if mode == "build":
        if apply_filter:
            open_and_filter_build_menu(sleep_sec=0.8)
        else:
            open_build_panel(sleep_sec=0.9)
    elif mode == "research":
        open_build_panel(sleep_sec=0.9)
        _tap_pt(COORDS_RESEARCH["open_lab"], sleep_sec=0.9, label="Mở Lab để kiểm tra popup")
    else:
        raise ValueError(f"mode không hợp lệ: {mode}")

    img_drawer = cet.capture_screen()
    if not cvg.is_upgrade_drawer_open(img_drawer):
        rec = restart_game_to_home(reason=f"inspect_{mode}_drawer_missing", screenshot=img_drawer)
        return {"ok": False, "reason": "out_of_scope_restarted", "recovery": rec}

    select_upgrade_pick(mode=mode, pick_key=pick_key, scrolls=scrolls, sleep_sec=1.0)
    img_modal = cet.capture_screen()

    full_path = os.path.join(save_dir, "modal_screen_full.png")
    if img_modal is not None:
        cv2.imwrite(full_path, img_modal)

    crops = {}
    for box_key, fname in (
        ("modal_full", "modal_cropped.png"),
        ("modal_title_level", "modal_title_level.png"),
        ("modal_confirm_footer", "modal_confirm_footer.png"),
    ):
        c = _crop_box(img_modal, box_key)
        if c is not None:
            cpath = os.path.join(save_dir, fname)
            cv2.imwrite(cpath, c)
            crops[box_key] = cpath

    confirm_status = _check_confirm_button_color(img_modal)
    exit_res = None
    if close_modal:
        _tap_pt(COORDS_BUILD["modal_close"], sleep_sec=0.6, label="Đóng popup chi tiết (X)")
        exit_res = close_upgrade_panel_to_home(verify=True)

    result = {
        "ok": True,
        "mode": mode,
        "pick_key": pick_key,
        "scrolls": int(scrolls),
        "confirm_button_status": confirm_status,
        "priority_config": cfg["builder_focus"],
        "full_screen": full_path,
        "crops": crops,
        "home": exit_res,
    }
    _save_json_atomic(os.path.join(save_dir, "inspect_manifest.json"), result)
    return result


def _crop_box(img, box_name):
    if img is None or box_name not in VISION_BOXES:
        return None
    x1, y1, x2, y2 = VISION_BOXES[box_name]
    h, w = img.shape[:2]
    return img[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]


def _save_json_atomic(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse_coc_duration_seconds(duration_text):
    """Chuyển chuỗi thời gian Clash of Clans ('2H 51M', '1d 9H', '15M 0s', '2:35') sang tổng giây."""
    if isinstance(duration_text, (int, float)):
        return max(0, int(duration_text))
    s = str(duration_text or "").strip().lower()
    if not s:
        return 0
    if ":" in s and all(p.strip().isdigit() for p in s.split(":")):
        parts = [int(p.strip()) for p in s.split(":")]
        if len(parts) == 2:
            # Mặc định H:MM (vd 2:35 -> 2 giờ 35 phút)
            return parts[0] * 3600 + parts[1] * 60
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    total = 0
    matched = False
    for val, unit in re.findall(r"(\d+)\s*([dhms])", s):
        matched = True
        n = int(val)
        if unit == "d":
            total += n * 86400
        elif unit == "h":
            total += n * 3600
        elif unit == "m":
            total += n * 60
        elif unit == "s":
            total += n
    return total if matched else 0


def compute_safe_wakeup(durations, buffer_minutes=3, save_path=None):
    """
    Chọn thời gian đếm ngược nhỏ nhất đang chạy và cộng thêm buffer an toàn (mặc định +3 phút)
    để đặt lịch hẹn giờ thức dậy kiểm tra lại.
    """
    parsed = [parse_coc_duration_seconds(d) for d in durations]
    active = [sec for sec in parsed if sec > 0]
    min_sec = min(active) if active else 0
    buffer_sec = max(0, int(buffer_minutes * 60))
    wait_total_sec = (min_sec + buffer_sec) if min_sec > 0 else 0
    now = datetime.now()
    wakeup_dt = now + timedelta(seconds=wait_total_sec)
    plan = {
        "ok": True,
        "min_timer_sec": min_sec,
        "buffer_sec": buffer_sec,
        "wait_total_sec": wait_total_sec,
        "wait_human": f"{wait_total_sec // 3600}h {(wait_total_sec % 3600) // 60}m {wait_total_sec % 60}s",
        "computed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "wakeup_at": wakeup_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "source_durations": [str(d) for d in durations],
    }
    target_path = save_path or os.path.join(cet.RUNTIME_DIR, "upgrade_wakeup_plan.json")
    _save_json_atomic(target_path, plan)
    return plan


def return_from_builder_base_to_home(img=None):
    """Bấm thuyền ở Làng Thợ (góc trên phải bờ biển) để quay về Làng chính."""
    boat_candidates = [(1665, 165), (1740, 195), (1580, 175)]
    for attempt in range(2):
        if attempt > 0:
            cet.close_all_modals()
            cet.zoom_out_pinch(repeats=1)
            # Kéo tay từ trên-phải xuống dưới-trái để lộ góc bờ biển trên-phải của Làng Thợ
            cet.swipe(1650, 260, 650, 760, 350)
            time.sleep(0.6)
        for bx, by in boat_candidates:
            cet.tap(bx, by, sleep_sec=2.3)
            cur = cet.capture_screen()
            if cur is not None and cvg.is_battle_button_visible(cur):
                return True
            if cur is not None and not cvg.is_builder_base(cur):
                cet.close_all_modals()
    return False


def restart_game_to_home(reason="out_of_scope", screenshot=None, timeout_sec=55):
    """
    Khi giao diện bị lệch khỏi phạm vi điều khiển: ghi log + lưu ảnh báo thức AI,
    tắt hẳn Clash of Clans rồi mở lại cho tới khi về đúng màn hình Làng chính.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    alert_dir = os.path.join(cet.RUNTIME_DIR, "alerts")
    os.makedirs(alert_dir, exist_ok=True)
    shot_path = None
    if screenshot is not None:
        shot_path = os.path.join(alert_dir, f"alert_{ts}.png")
        cv2.imwrite(shot_path, screenshot)

    alert_payload = {
        "alert_triggered": True,
        "reason": reason,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "screenshot_path": shot_path,
    }
    _save_json_atomic(os.path.join(cet.RUNTIME_DIR, "upgrade_alert.json"), alert_payload)
    cet.log(f"[ALERT-OUT-OF-SCOPE] Phát hiện lệch phạm vi ({reason})! Khởi động lại app để về trang chính...")

    cet.adb_shell("am force-stop com.supercell.clashofclans", timeout=10)
    time.sleep(1.5)
    cet.launch_clash_of_clans()

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        img = cet.capture_screen()
        if img is not None:
            if cvg.is_builder_base(img):
                cet.log("[ALERT-RECOVERY] Game mở ở Làng Thợ -> Bấm thuyền quay về Làng chính...")
                if return_from_builder_base_to_home(img):
                    cet.log("[ALERT-RECOVERY] Đã đi thuyền từ Làng Thợ về đúng Làng chính.")
                    zoom_res = cet.zoom_out_pinch(repeats=1)
                    return {"ok": True, "screen": "home", "alert": alert_payload, "zoom_out": zoom_res}
                continue
            if cvg.is_battle_button_visible(img):
                cet.log("[ALERT-RECOVERY] Đã khởi động lại và về đúng Làng chính an toàn.")
                zoom_res = cet.zoom_out_pinch(repeats=1)
                return {"ok": True, "screen": "home", "alert": alert_payload, "zoom_out": zoom_res}
            if cvg.is_reload_game_dialog(img):
                cet.tap(1038, 970, sleep_sec=4.0)
                continue
            cet.close_all_modals()
        time.sleep(2.0)

    cet.log("[ALERT-RECOVERY] Quá thời gian chờ về Làng chính sau khi khởi động lại game.")
    return {"ok": False, "screen": "unknown", "alert": alert_payload}


def _ensure_home_or_restart():
    for _ in range(4):
        cet.ensure_game_foreground()
        img = cet.capture_screen()
        if img is not None and cvg.is_battle_button_visible(img):
            return img
        cet.close_all_modals()
        time.sleep(1.0)
    res = restart_game_to_home(reason="cannot_reach_home_before_upgrade", screenshot=cet.capture_screen())
    return cet.capture_screen() if res.get("ok") else None


def capture_upgrade_state_snapshots(apply_filter=True, out_dir=None, save_crops=False):
    """
    Chụp 4 ảnh TOÀN MÀN HÌNH (2220x1080) để AI tự nhìn trực tiếp & quyết định:
    1) full_1_home.png (Làng chính) -> mở Búa (+ Lọc) -> full_2_build.png (Công trình + Tài nguyên dạt trái)
    2) Tab Lab -> full_3_lab.png -> Tab Thú cưng -> full_4_pets.png -> thoát về Làng chính (1800, 38).
    Nếu lệch phạm vi (không mở được ngăn kéo) tự tắt mở lại app về trang chính.
    """
    save_dir = out_dir or os.path.join(cet.RUNTIME_DIR, "upgrade_snapshot")
    os.makedirs(save_dir, exist_ok=True)

    img_home = _ensure_home_or_restart()
    if img_home is None:
        return {"ok": False, "reason": "home_unreachable_even_after_restart"}

    hg, he, hde = cvg.read_all_home_resources(img_home)
    f1 = os.path.join(save_dir, "full_1_home.png")
    cv2.imwrite(f1, img_home)

    if apply_filter:
        open_and_filter_build_menu(sleep_sec=0.8)
    else:
        open_build_panel(sleep_sec=0.9)

    img_build = cet.capture_screen()
    if not cvg.is_upgrade_drawer_open(img_build):
        rec = restart_game_to_home(reason="build_drawer_failed_to_open", screenshot=img_build)
        return {"ok": False, "reason": "out_of_scope_restarted", "recovery": rec}

    sg, se, sde = cvg.read_shifted_resources(img_build)
    f2 = os.path.join(save_dir, "full_2_build.png")
    cv2.imwrite(f2, img_build)

    cet.scroll_upgrade_list(repeats=1, sleep_sec=0.35)
    img_build_scrolled = cet.capture_screen()
    f2b = os.path.join(save_dir, "full_2b_build_scrolled.png")
    cv2.imwrite(f2b, img_build_scrolled)

    _tap_pt(COORDS_RESEARCH["open_lab"], sleep_sec=0.9, label="Chụp tab Lab")
    img_lab = cet.capture_screen()
    if not cvg.is_upgrade_drawer_open(img_lab):
        rec = restart_game_to_home(reason="lab_drawer_out_of_scope", screenshot=img_lab)
        return {"ok": False, "reason": "out_of_scope_restarted", "recovery": rec}
    f3 = os.path.join(save_dir, "full_3_lab.png")
    cv2.imwrite(f3, img_lab)

    cet.scroll_upgrade_list(repeats=1, sleep_sec=0.35)
    img_lab_scrolled = cet.capture_screen()
    f3b = os.path.join(save_dir, "full_3b_lab_scrolled.png")
    cv2.imwrite(f3b, img_lab_scrolled)

    _tap_pt(COORDS_PET["open_pet_house"], sleep_sec=0.9, label="Chụp tab Thú cưng")
    img_pet = cet.capture_screen()
    if not cvg.is_upgrade_drawer_open(img_pet):
        rec = restart_game_to_home(reason="pet_drawer_out_of_scope", screenshot=img_pet)
        return {"ok": False, "reason": "out_of_scope_restarted", "recovery": rec}
    f4 = os.path.join(save_dir, "full_4_pets.png")
    cv2.imwrite(f4, img_pet)

    files = {
        "full_1_home": f1,
        "full_2_build": f2,
        "full_2b_build_scrolled": f2b,
        "full_3_lab": f3,
        "full_3b_lab_scrolled": f3b,
        "full_4_pets": f4,
    }
    if save_crops:
        crop_pairs = [
            ("img1_builders", img_home, "img1_builder_count", "snap_1_builders.png"),
            ("img1_fullbadge", img_home, "img1_builder_lab_badge", "snap_1_fullbadge.png"),
            ("shifted_resources", img_build, "shifted_resources", "snap_resources_shifted.png"),
            ("img2_buildings", img_build, "img2_buildings_list", "snap_2_buildings.png"),
            ("img3_research", img_lab, "img3_research_list", "snap_3_research.png"),
            ("img4_pets", img_pet, "img4_hero_pets_list", "snap_4_pets.png"),
        ]
        for key, src_img, box_name, fname in crop_pairs:
            c = _crop_box(src_img, box_name)
            if c is not None:
                cpath = os.path.join(save_dir, fname)
                cv2.imwrite(cpath, c)
                files[key] = cpath

    exit_res = close_upgrade_panel_to_home(verify=True)
    cfg = load_upgrade_priority_config()

    result = {
        "ok": bool(exit_res.get("ok")),
        "returned_home_battle_visible": exit_res,
        "home_resources": {"gold": hg, "elixir": he, "dark_elixir": hde},
        "shifted_resources": {"gold": sg, "elixir": se, "dark_elixir": sde},
        "priority_config": cfg["builder_focus"],
        "files": files,
    }
    _save_json_atomic(os.path.join(save_dir, "snapshot_manifest.json"), result)
    return result


def format_coord_summary():
    """Trả về bảng tóm tắt toàn bộ tọa độ và cấu hình ưu tiên hiện hành."""
    cfg = load_upgrade_priority_config()
    bf = cfg.get("builder_focus", {})
    prio_desc = ", ".join(f"{t['name']} (Max Lv {t.get('max_level', 21)})" for t in bf.get("priority_targets", []))
    lines = [
        "=== TOOL TỌA ĐỘ NÂNG CẤP (2220x1080) ===",
        f"[0] Ưu tiên động ({bf.get('target_builders', 6)} thợ xây): {prio_desc}",
        "[1] Xây dựng & Nâng cấp công trình:",
        f"  - Búa Build            : {COORDS_BUILD['open_build_menu']}",
        f"  - Chọn phần lọc (trên) : {COORDS_BUILD['filter_button']}",
        f"  - Chọn phần lọc (mục)  : {COORDS_BUILD['filter_option']}",
        f"  - Chọn ra ngoài        : {COORDS_BUILD['tap_outside']}",
        f"  - Chọn sản phẩm nâng   : {COORDS_BUILD['select_product']}",
        f"  - Vị trí 1..3          : {COORDS_BUILD['slot_1']}, {COORDS_BUILD['slot_2']}, {COORDS_BUILD['slot_3']}",
        f"  - Vị trí 4 (Xác nhận)  : {COORDS_BUILD['confirm_upgrade']}",
        f"  - Đóng popup (X)       : {COORDS_BUILD['modal_close']}",
        f"  - Thoát về Battle      : {COORDS_BUILD['close_upgrade_panel']}",
        "[2] Kho nghiên cứu (Lab):",
        f"  - Vào kho nghiên cứu   : {COORDS_RESEARCH['open_lab']}",
        f"  - Chọn nghiên cứu      : {COORDS_RESEARCH['select_item']}",
        f"  - Xác nhận nghiên cứu  : {COORDS_RESEARCH['confirm']}",
        "[3] 3 Vị trí chọn nâng cấp bổ sung (chưa lướt):",
        f"  - pick_alt_1..3        : {SHARED_UPGRADE_PICK_POSITIONS['pick_alt_1']}, {SHARED_UPGRADE_PICK_POSITIONS['pick_alt_2']}, {SHARED_UPGRADE_PICK_POSITIONS['pick_alt_3']}",
        "[4] 8 Vị trí chọn hàng SAU KHI lướt xuống (dùng chung Build & Lab):",
    ]
    for k, pt in SCROLL_LIST_PICK_POSITIONS.items():
        lines.append(f"  - {k:14s}       : {pt}")
    lines.extend([
        "[5] Nghiên cứu thú cưng (Hero Pets):",
        f"  - Vào thú cưng         : {COORDS_PET['open_pet_house']}",
        f"  - Chọn thú cưng        : {COORDS_PET['select_item']}",
        f"  - Xác nhận thú cưng    : {COORDS_PET['confirm']}",
        "[6] Khung cắt AI Vision (x1, y1, x2, y2):",
        f"  - Ảnh 1 (Thợ xây X/6)  : {VISION_BOXES['img1_builder_count']}",
        f"  - Tài nguyên (dạt trái): {VISION_BOXES['shifted_resources']}",
        f"  - Popup chi tiết (Lv)  : {VISION_BOXES['modal_title_level']}",
        f"  - Popup Confirm footer : {VISION_BOXES['modal_confirm_footer']}",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool tọa độ & Vòng lặp nâng cấp Build / Research / Hero Pets")
    parser.add_argument("--print-coords", action="store_true", help="In bảng tọa độ & cấu hình ưu tiên")
    parser.add_argument("--snapshot", action="store_true", help="Chụp 6 ảnh toàn màn hình (kèm ảnh đã lướt) để AI đọc và quyết định")
    parser.add_argument("--save-crops", action="store_true", help="Lưu kèm thêm các ảnh cắt nhỏ khi chạy --snapshot")
    parser.add_argument("--no-filter", action="store_true", help="Bỏ qua bước bấm lọc khi chạy --snapshot, --scan-build hoặc --exec-build")
    parser.add_argument("--scrolls", type=int, default=0, help="Số nhịp lướt xuống trước khi chọn (dùng với --exec-build, --exec-research, --inspect-pick)")
    parser.add_argument(
        "--exec-build",
        nargs="?",
        const="select_product",
        help="Mở Búa (+ Lọc) -> tùy chọn --scrolls N -> chọn vị trí (select_product, pick_alt_1..3, scroll_pick_1..8) -> 4 bước xác nhận -> về Home",
    )
    parser.add_argument(
        "--exec-research",
        nargs="?",
        const="select_item",
        help="Mở Búa -> Lab -> tùy chọn --scrolls N -> chọn vị trí (select_item, pick_alt_1..3, scroll_pick_1..8) -> xác nhận -> về Home",
    )
    parser.add_argument("--exec-pet", action="store_true", help="Mở Búa -> Hero Pets -> chọn thú cưng -> xác nhận -> về Home")
    parser.add_argument("--scan-build", nargs="?", const=5, type=int, help="Quét N trang danh sách Buildings & Heroes để tìm công trình ưu tiên")
    parser.add_argument("--scan-lab", nargs="?", const=3, type=int, help="Quét N trang danh sách Lab")
    parser.add_argument("--inspect-pick", type=str, help="Mở popup xác nhận nâng cấp ở pick_key (KHÔNG bấm Confirm) để đọc Level/Max/thanh xanh lá")
    parser.add_argument("--inspect-mode", choices=("build", "research"), default="build", help="Chế độ mở cho --inspect-pick (build hoặc research)")
    parser.add_argument("--show-priority", action="store_true", help="Hiển thị cấu hình ưu tiên nâng cấp & ngưỡng tài nguyên động")
    parser.add_argument("--set-priority", type=str, help="Đổi danh sách ưu tiên động, vd: 'Archer Tower:21,Cannon:21'")
    parser.add_argument("--set-builders", type=int, help="Đổi số thợ xây mục tiêu trong cấu hình ưu tiên (vd: 6)")
    parser.add_argument("--set-thresholds", nargs=3, type=int, metavar=("GOLD", "ELIXIR", "DARK"), help="Đổi 3 ngưỡng dừng cày tài nguyên")
    parser.add_argument("--close-home", action="store_true", help="Bấm thoát vùng nâng cấp (1800, 38) về Làng chính và thu nhỏ camera")
    parser.add_argument("--zoom-out", action="store_true", help="Thu nhỏ camera Làng chính theo thao tác chuẩn của Sếp")
    parser.add_argument("--scroll-list", nargs="?", const=1, type=int, help="Lướt xuống danh sách nâng cấp (Build/Lab) N nhịp")
    parser.add_argument("--test-wakeup", nargs="+", help="Tính thời gian hẹn kiểm tra +3 phút (vd: '2:35' '8H 51M')")
    parser.add_argument("--restart-home", action="store_true", help="Tắt và mở lại Clash of Clans về Làng chính")
    args = parser.parse_args()

    if args.show_priority or args.set_priority or args.set_builders is not None or args.set_thresholds is not None:
        cfg = load_upgrade_priority_config()
        changed = False
        if args.set_priority:
            cfg["builder_focus"]["priority_targets"] = parse_priority_spec(args.set_priority)
            changed = True
        if args.set_builders is not None:
            cfg["builder_focus"]["target_builders"] = int(args.set_builders)
            changed = True
        if args.set_thresholds is not None:
            g_th, e_th, de_th = args.set_thresholds
            cfg["resource_stop_thresholds"]["gold"] = int(g_th)
            cfg["resource_stop_thresholds"]["elixir"] = int(e_th)
            cfg["resource_stop_thresholds"]["dark_elixir"] = int(de_th)
            changed = True
        if changed:
            save_path = save_upgrade_priority_config(cfg)
            print(json.dumps({"ok": True, "updated": True, "config_path": save_path, "config": cfg}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"ok": True, "config_path": DEFAULT_PRIORITY_CONFIG_PATH, "config": cfg}, ensure_ascii=False, indent=2))
    elif args.snapshot:
        res = capture_upgrade_state_snapshots(apply_filter=not args.no_filter, save_crops=args.save_crops)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.scan_build is not None:
        res = scan_upgrade_pages(mode="build", max_scrolls=args.scan_build, apply_filter=not args.no_filter)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.scan_lab is not None:
        res = scan_upgrade_pages(mode="research", max_scrolls=args.scan_lab, apply_filter=False)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.inspect_pick:
        res = inspect_upgrade_modal(
            pick_key=args.inspect_pick,
            mode=args.inspect_mode,
            scrolls=args.scrolls,
            apply_filter=not args.no_filter,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.exec_build:
        img_h = _ensure_home_or_restart()
        if img_h is None:
            print(json.dumps({"ok": False, "reason": "home_unreachable"}))
        else:
            if args.no_filter:
                open_build_panel(sleep_sec=0.8)
            else:
                open_and_filter_build_menu(sleep_sec=0.8)
            if not cvg.is_upgrade_drawer_open(cet.capture_screen()):
                print(json.dumps(restart_game_to_home("exec_build_drawer_missing"), ensure_ascii=False, indent=2))
            else:
                execute_build_4step_confirm(pick_key=args.exec_build, scrolls=args.scrolls, confirm=True, sleep_sec=0.8)
                exit_res = close_upgrade_panel_to_home(verify=True)
                print(json.dumps({"ok": True, "action": "exec_build", "pick": args.exec_build, "scrolls": args.scrolls, "home": exit_res}, ensure_ascii=False, indent=2))
    elif args.exec_research:
        img_h = _ensure_home_or_restart()
        if img_h is None:
            print(json.dumps({"ok": False, "reason": "home_unreachable"}))
        else:
            run_research_upgrade(pick_key=args.exec_research, scrolls=args.scrolls, confirm=True, open_hammer_first=True, sleep_sec=0.8)
            exit_res = close_upgrade_panel_to_home(verify=True)
            print(json.dumps({"ok": True, "action": "exec_research", "pick": args.exec_research, "scrolls": args.scrolls, "home": exit_res}, ensure_ascii=False, indent=2))
    elif args.exec_pet:
        img_h = _ensure_home_or_restart()
        if img_h is None:
            print(json.dumps({"ok": False, "reason": "home_unreachable"}))
        else:
            run_pet_upgrade(confirm=True, open_hammer_first=True, sleep_sec=0.8)
            exit_res = close_upgrade_panel_to_home(verify=True)
            print(json.dumps({"ok": True, "action": "exec_pet", "home": exit_res}, ensure_ascii=False, indent=2))
    elif args.close_home:
        print(json.dumps(close_upgrade_panel_to_home(verify=True), ensure_ascii=False, indent=2))
    elif args.zoom_out:
        print(json.dumps(cet.zoom_out_pinch(repeats=1), ensure_ascii=False, indent=2))
    elif args.scroll_list is not None:
        print(json.dumps(cet.scroll_upgrade_list(repeats=args.scroll_list), ensure_ascii=False, indent=2))
    elif args.test_wakeup:
        plan = compute_safe_wakeup(args.test_wakeup, buffer_minutes=3)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif args.restart_home:
        res = restart_game_to_home(reason="manual_cli_reset")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_coord_summary())
