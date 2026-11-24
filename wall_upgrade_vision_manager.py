# ==============================================================================
# HỆ THỐNG NÂNG CẤP TƯỜNG TỰ ĐỘNG - AI COMPUTER VISION (MAX LEVEL 17)
# Đọc trực tiếp cụm tường xanh xám Level 16, tự bỏ qua Level >= 17, không đụng Gem
# ==============================================================================
import os
import sys
import time
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import coc_executor_tools as cet
import coc_vision_grid as cvg

# ------------------------------------------------------------------------------
# 1. TỌA ĐỘ CÁC NÚT CỐ ĐỊNH TRONG MENU TƯỜNG (ĐÃ KIỂM CHỨNG THỰC TẾ)
# ------------------------------------------------------------------------------
BTN_UPGRADE_MORE = (1052, 842)          # Nút "Upgrade More" (hình trụ tường +)
BTN_ADD_10 = (798, 844)                # Nút "+10 Add Wall"
BTN_ADD_1 = (1005, 844)                # Nút "+1 Add Wall"
BTN_DOUBLE_HAMMER_GOLD = (1214, 844)   # Nút 2 Búa Vàng sau khi bấm Upgrade More
BTN_DOUBLE_HAMMER_ELIXIR = (1423, 844) # Nút 2 Búa Dầu sau khi bấm Upgrade More
BTN_SINGLE_HAMMER_GOLD = (1205, 800)   # Nút 1 Búa Vàng khi chưa bấm Upgrade More
BTN_SINGLE_HAMMER_ELIXIR = (1375, 800) # Nút 1 Búa Dầu khi chưa bấm Upgrade More
BTN_CONFIRM_OKAY = (1319, 698)         # Nút "Okay" màu xanh lá trong popup xác nhận nâng hàng tường
BTN_SINGLE_CONFIRM = (1491, 944)       # Nút "Confirm" màu xanh lá trong popup nâng 1 viên tường
POINT_SAFE_DESELECT = (2150, 750)      # Vùng mép ngoài viền biển cỏ an toàn (không có bẫy/công trình)

# ------------------------------------------------------------------------------
# 2. VÙNG CẮT AI VISION & VECTOR BƯỚC NHẢY MA TRẬN KHỐI TƯỜNG (19 x 16 = 304 VIÊN)
# ------------------------------------------------------------------------------
BOX_WALL_LEVEL = (820, 665, 1520, 758)
BOX_UPGRADE_BUTTONS = (1125, 755, 1494, 949)
BOX_RESOURCE_BAR = cvg.BOX_RESOURCE_BAR

# Gốc và vector chuẩn của khối tường chữ nhật (19 dọc x 16 ngang) ở mức zoom-out BlueStacks
WALL_GRID_ORIGIN = (810, 434)
DELTA_ROW_X = 19.89   # Trục dọc: 19 viên, dx=+19.89, dy=+11.00
DELTA_ROW_Y = 11.00
DELTA_COL_X = 18.53   # Trục ngang: 16 viên, dx=+18.53, dy=-14.20
DELTA_COL_Y = -14.20
GRID_NUM_ROWS = 19
GRID_NUM_COLS = 16

MAX_WALL_LEVEL = 18
WALL_STOP_THRESHOLD_DEFAULT = 0
KNOWN_L18_FILE = os.path.join(cet.RUNTIME_DIR, "known_level18_walls_v2.json")

INITIAL_VERIFIED_L18 = []


def load_known_l18_coords():
    """Đọc danh sách các tọa độ tường đã đạt Level 18 từ file lưu trữ."""
    base_set = set(INITIAL_VERIFIED_L18)
    if not os.path.exists(KNOWN_L18_FILE):
        return base_set
    try:
        import json
        with open(KNOWN_L18_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            coords = [tuple(c) for c in data.get("coords", [])]
            return base_set.union(set(coords))
    except Exception:
        return base_set


def save_known_l18_coords(coords_set):
    """Lưu danh sách tọa độ tường đã đạt Level 18 ra file JSON (an toàn với WinError 5)."""
    try:
        import json
        from datetime import datetime
        os.makedirs(cet.RUNTIME_DIR, exist_ok=True)
        coords_list = sorted(list(coords_set), key=lambda c: (c[0], c[1]))
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_l18_count": len(coords_list),
            "coords": coords_list,
        }
        tmp = KNOWN_L18_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        for attempt in range(4):
            try:
                os.replace(tmp, KNOWN_L18_FILE)
                return
            except PermissionError:
                try:
                    if os.path.exists(KNOWN_L18_FILE):
                        os.remove(KNOWN_L18_FILE)
                    os.rename(tmp, KNOWN_L18_FILE)
                    return
                except Exception:
                    time.sleep(0.1 * (attempt + 1))
    except Exception as e:
        cet.log(f"[WARN] Không thể lưu {KNOWN_L18_FILE}: {e}")


def generate_wall_grid_candidates(origin=WALL_GRID_ORIGIN, num_rows=GRID_NUM_ROWS, num_cols=GRID_NUM_COLS):
    """
    Sinh ma trận tọa độ toàn bộ khối tường chữ nhật (19 hàng dọc x 16 cột ngang = 304 viên).
    Duyệt tuần tự theo cột và hàng để quét phủ kín cả vùng tường.
    """
    candidates = []
    for c in range(num_cols):
        for r in range(num_rows):
            x = round(origin[0] + r * DELTA_ROW_X + c * DELTA_COL_X)
            y = round(origin[1] + r * DELTA_ROW_Y + c * DELTA_COL_Y)
            candidates.append((x, y))
    return candidates


def tap(coord, delay=1.0):
    x, y = coord
    cet.tap(x, y, sleep_sec=delay)


def capture_full_screen():
    return cet.capture_screen()


def ensure_clean_home_view():
    """Đảm bảo màn hình đang ở Làng chính sạch sẽ (không dính menu cũ hay popup)."""
    for _ in range(5):
        img = capture_full_screen()
        if img is None:
            time.sleep(1.0)
            continue
        if cvg.is_battle_button_visible(img):
            return img
        if cvg.is_reload_game_dialog(img):
            cet.tap(1038, 970, sleep_sec=6.0)
            continue
        if cvg.is_five_button_wall_bar(img):
            tap(POINT_SAFE_DESELECT, delay=0.6)
            continue
        cet.close_all_modals()
        time.sleep(0.6)
    return capture_full_screen()


def cmd_capture_three_regions(save_dir=None):
    """Chụp màn hình hiện tại và cắt 3 vùng Vision (Cấp tường, Nút nâng, Thanh kho)."""
    full = capture_full_screen()
    if full is None:
        raise RuntimeError("Không thể chụp màn hình từ điện thoại qua ADB")

    c1 = full[BOX_WALL_LEVEL[1]:BOX_WALL_LEVEL[3], BOX_WALL_LEVEL[0]:BOX_WALL_LEVEL[2]]
    c2 = full[BOX_UPGRADE_BUTTONS[1]:BOX_UPGRADE_BUTTONS[3], BOX_UPGRADE_BUTTONS[0]:BOX_UPGRADE_BUTTONS[2]]
    c3 = cvg.crop_home_resource_bar(full)

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        cv2.imwrite(os.path.join(save_dir, "vung1_cap_tuong.png"), c1)
        cv2.imwrite(os.path.join(save_dir, "vung2_hai_bua_nang_cap.png"), c2)
        cv2.imwrite(os.path.join(save_dir, "vung3_thanh_tai_nguyen.png"), c3)

    return c1, c2, c3, full


def ai_read_wall_level(img_or_crop):
    """Đọc cấp độ tường từ chuỗi 'Wall (Level XX)' trên ảnh toàn màn hình hoặc crop BOX_WALL_LEVEL."""
    if img_or_crop is None or img_or_crop.size == 0:
        return 0
    if img_or_crop.shape[0] >= 800 and img_or_crop.shape[1] >= 1600:
        crop = img_or_crop[BOX_WALL_LEVEL[1]:BOX_WALL_LEVEL[3], BOX_WALL_LEVEL[0]:BOX_WALL_LEVEL[2]]
    else:
        crop = img_or_crop

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (15, 15, 180), (45, 140, 255))
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    comps = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if 20 <= h <= 45 and 6 <= w <= 46 and area >= 120:
            comps.append((x, y, w, h))
    if not comps:
        return 0

    comps.sort(key=lambda c: c[0])
    clusters = [[comps[0]]]
    for c in comps[1:]:
        prev = clusters[-1][-1]
        if c[0] - (prev[0] + prev[2]) <= 45:
            clusters[-1].append(c)
        else:
            clusters.append([c])

    title = max(clusters, key=len)
    if len(title) < 6:
        return 0

    # Bỏ dấu ')' cuối cùng, tìm cụm số ngay sau khoảng trắng của chữ 'Level '
    body = title[:-1]
    start_idx = 0
    for idx in range(1, len(body)):
        if body[idx][0] - (body[idx - 1][0] + body[idx - 1][2]) >= 10:
            start_idx = idx
    digit_comps = body[start_idx:]
    if not (1 <= len(digit_comps) <= 2):
        return 0

    digits = []
    for x, y, w, h in digit_comps:
        patch = cv2.resize(mask[y:y + h, x:x + w], (16, 24)).astype(np.float32)
        best_ch = max(
            cvg.DIGIT_TPLS.keys(),
            key=lambda c: float(np.sum(patch * cvg.DIGIT_TPLS[c]))
            / (float(np.linalg.norm(patch) * np.linalg.norm(cvg.DIGIT_TPLS[c])) + 1e-6),
        )
        digits.append(best_ch)
    s = "".join(digits)
    return int(s) if s.isdigit() else 0


def is_valid_wall_menu(full_img):
    """Chỉ xác nhận hợp lệ khi có thanh 5 nút Tường chuẩn."""
    if full_img is None:
        return False
    return cvg.is_five_button_wall_bar(full_img)


def ai_read_hammer_cost(full_img):
    """Đọc giá tiền nâng 1 viên tường trên nút búa Vàng hoặc Dầu (hỗ trợ cả chữ trắng lẫn chữ đỏ)."""
    if full_img is None or full_img.size == 0:
        return 0
    if full_img.shape[0] < 800:
        return 0

    for x1, x2 in [(1120, 1300), (1330, 1510)]:
        crop = full_img[740:785, x1:x2]
        b, g, r = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        mask = ((r > 190) & (r >= b)).astype(np.uint8) * 255
        val = cvg._extract_digits_from_mask(
            mask, min_h=12, max_h=25, min_w=5, max_w=20, min_area=30, max_y_jitter=4
        )
        if 100_000 <= val <= 20_000_000:
            return val
    return 0


def find_l16_wall_candidates(full_img, max_points=36):
    """
    Phát hiện động khối tường xanh xám Level 16 bằng màu HSV bất kể mức zoom/pan.
    Sắp xếp các điểm ứng viên theo quy tắc: đi dọc cột từ trên xuống dưới, dịch dần từ trái sang phải.
    """
    candidates = []
    if full_img is not None:
        hsv = cv2.cvtColor(full_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (92, 40, 120), (112, 145, 240))
        mask[:115, :] = 0
        mask[735:, :] = 0
        mask[:, :300] = 0
        mask[:, 1840:] = 0

        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        closed = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        num, labels, stats, _ = cv2.connectedComponentsWithStats(closed)

        best = None
        best_area = 0
        for i in range(1, num):
            x, y, w, h, area = stats[i]
            if w > 60 and h > 40 and area > best_area:
                best_area = area
                best = (i, x, y, w, h)

        if best is not None and best_area >= 4000:
            comp_mask = (labels == best[0]).astype(np.uint8) * 255
            eroded = cv2.erode(comp_mask, np.ones((15, 15), np.uint8))
            ys, xs = np.where(eroded > 0)
            if len(xs) > 0:
                min_i = int(np.argmin(xs))
                anchor_x, anchor_y = int(xs[min_i]), int(ys[min_i])
                # Lưới 12 cột (dịch sang phải +23, -17) x 7 hàng (dọc xuống +20, +15) lọc chặt bên trong khối xanh xám
                h_img, w_img = eroded.shape
                for c in range(12):
                    for r in range(7):
                        px = anchor_x + c * DELTA_COL_X + r * DELTA_ROW_X
                        py = anchor_y + c * DELTA_COL_Y + r * DELTA_ROW_Y
                        if 0 <= px < w_img and 0 <= py < h_img and eroded[py, px] > 0:
                            candidates.append((px, py))
                # Dự phòng thêm tâm khối nếu lưới bước bị hụt ở zoom khác
                cx, cy = int(np.mean(xs)), int(np.mean(ys))
                if (cx, cy) not in candidates:
                    candidates.append((cx, cy))

    if not candidates:
        ox, oy = WALL_ORIGIN_FALLBACK
        for c in range(12):
            for r in range(6):
                candidates.append((ox + c * DELTA_COL_X + r * DELTA_ROW_X, oy + c * DELTA_COL_Y + r * DELTA_ROW_Y))

    return candidates[:max_points]


def find_l17_white_wall_candidates(full_img, max_points=45):
    """
    Phát hiện trực tiếp cụm tường trắng-kem Level 17 trên màn hình Làng chính (không phụ thuộc lưới tĩnh).
    Lấy các điểm nằm thực sự trên pixel tường trắng, sắp xếp theo cụm diện tích lớn nhất trước.
    """
    if full_img is None or full_img.size == 0:
        return []
    x1, y1, x2, y2 = 740, 200, 1400, 690
    roi = full_img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (12, 0, 215), (32, 90, 255))

    # Loại góc chữ 'Upgrade' trại lính bên phải trên và vùng icon kho góc phải dưới
    mask[:90, max(0, 1260 - x1):] = 0
    mask[max(0, 560 - y1):, max(0, 1220 - x1):] = 0

    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(closed)
    comps = []
    for i in range(1, num):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= 120:
            comps.append((area, i))
    comps.sort(key=lambda t: -t[0])

    pts = []
    for _, comp_id in comps:
        comp_mask = ((labels == comp_id) & (mask > 0))
        ys, xs = np.where(comp_mask)
        for py, px in zip(ys[::4], xs[::4]):
            fx, fy = int(px) + x1, int(py) + y1
            if all(abs(fx - ox) >= 18 or abs(fy - oy) >= 12 for ox, oy in pts):
                pts.append((fx, fy))
                if len(pts) >= max_points:
                    return pts
    return pts


def cmd_execute_wall_upgrade(start_coord=None, resource="auto", stop_threshold=WALL_STOP_THRESHOLD_DEFAULT):
    """
    Thực thi 1 đợt nâng tường AI Vision (Level < 18) từ kho tài nguyên thực tế, dừng trước Gem:
    - Ưu tiên bắt trực tiếp các điểm tường trắng Level 17 bằng Computer Vision.
    - Xác nhận đúng menu Wall và cấp < 18 (giá < 8,000,000).
    - Nâng hết mức tối đa 4 viên/lượt theo tài nguyên hiện có.
    """
    img_home = ensure_clean_home_view()
    if img_home is None:
        return "ERROR_NO_SCREEN"

    known_l18 = load_known_l18_coords()
    visual_pts = find_l17_white_wall_candidates(img_home, max_points=45)
    if start_coord is not None:
        grid_pts = generate_wall_grid_candidates(origin=start_coord)
    else:
        grid_pts = generate_wall_grid_candidates()

    grid_filtered = [pt for pt in grid_pts if pt not in known_l18]
    candidates = visual_pts + [pt for pt in grid_filtered if pt not in visual_pts]
    cet.log(
        f"[WALL-UPGRADE] Vision phát hiện {len(visual_pts)} điểm tường trắng Lv17; "
        f"dự phòng thêm {len(grid_filtered)} điểm lưới (đã loại {len(known_l18)} Lv18)."
    )

    for idx, (wx, wy) in enumerate(candidates, 1):
        cet.log(f"[WALL-UPGRADE] Quét tường #{idx}/{len(candidates)} tại ({wx}, {wy})...")
        tap((wx, wy), delay=0.8)
        full = capture_full_screen()
        if full is None:
            continue

        if not is_valid_wall_menu(full):
            cet.log(f"[WALL-UPGRADE] ({wx}, {wy}) chưa hiện menu Tường -> Bấm thẳng viên tiếp theo...")
            continue

        wall_lvl = ai_read_wall_level(full)
        if wall_lvl > 0:
            cet.log(f"[WALL-UPGRADE] Đọc thấy: Wall Level {wall_lvl}")
            if wall_lvl >= MAX_WALL_LEVEL:
                cet.log(f"[WALL-UPGRADE] Tường ({wx}, {wy}) đã Level {wall_lvl} (>= {MAX_WALL_LEVEL}) -> Thêm vào danh sách Level 18 và bỏ qua...")
                known_l18.add((wx, wy))
                save_known_l18_coords(known_l18)
                continue

        wall_cost = ai_read_hammer_cost(full)
        if wall_cost <= 0:
            cost_map = {13: 1_000_000, 14: 1_500_000, 15: 2_000_000, 16: 6_000_000, 17: 6_000_000}
            wall_cost = cost_map.get(wall_lvl, 6_000_000)
        cet.log(f"[WALL-UPGRADE] Giá nâng 1 tường: {wall_cost:,}")

        # Tường Level 18 nâng lên 19 có giá 8,000,000 -> Đã max Lv 18 theo yêu cầu, ghi nhận và bỏ qua
        if wall_cost >= 8_000_000:
            cet.log(f"[WALL-UPGRADE] Tường ({wx}, {wy}) giá {wall_cost:,} (đã đạt Level 18) -> Thêm vào danh sách Level 18 và bỏ qua...")
            known_l18.add((wx, wy))
            save_known_l18_coords(known_l18)
            continue

        current_gold, current_elixir = cvg.read_home_resources(full)
        cet.log(f"[WALL-UPGRADE] Kho hiện tại: Vàng = {current_gold:,} | Dầu = {current_elixir:,}")

        if current_gold < wall_cost and current_elixir < wall_cost:
            cet.close_all_modals()
            return "DONE_REACHED_STOP_THRESHOLD"

        target_res = resource
        if target_res == "auto":
            gold_ok = current_gold >= wall_cost
            elix_ok = current_elixir >= wall_cost
            if gold_ok and (not elix_ok or current_gold >= current_elixir):
                target_res = "gold"
            elif elix_ok:
                target_res = "elixir"
            else:
                return "INSUFFICIENT_RESOURCES"

        if target_res == "elixir":
            chosen_double_btn = BTN_DOUBLE_HAMMER_ELIXIR
            chosen_single_btn = BTN_SINGLE_HAMMER_ELIXIR
            avail_amount = current_elixir
            res_label = "Dầu tím"
        else:
            chosen_double_btn = BTN_DOUBLE_HAMMER_GOLD
            chosen_single_btn = BTN_SINGLE_HAMMER_GOLD
            avail_amount = current_gold
            res_label = "Vàng"

        if avail_amount < wall_cost:
            return f"INSUFFICIENT_{target_res.upper()}"

        # Nâng hết sạch tài nguyên (1 viên = 6M, kho 24M nâng được 4 viên tròn)
        max_walls = max(1, int(avail_amount // wall_cost))
        max_walls = min(max_walls, 4)

        upgraded_count = max_walls
        if max_walls > 1:
            cet.log(f"[WALL-UPGRADE] Nâng {max_walls} tường bằng {res_label} ({avail_amount:,} / {wall_cost:,})...")
            tap(BTN_UPGRADE_MORE, delay=1.2)
            time.sleep(0.8)
            img_more = capture_full_screen()
            if img_more is not None and is_valid_wall_menu(img_more):
                # Kiểm tra thanh gọn 5 nút (-1, +1, Gold, Elixir, Ring): nút Nhẫn xanh nằm ở x=1415..1595
                ring_crop = img_more[750:860, 1430:1570]
                rb, _, rr = ring_crop[:, :, 0], ring_crop[:, :, 1], ring_crop[:, :, 2]
                is_compact_bar = int(np.sum((rb > 170) & (rr < 70))) > 5000
                if is_compact_bar:
                    add1_btn = (895, 800)
                    dbl_btn = (1305, 800) if target_res == "elixir" else (1100, 800)
                else:
                    add1_btn = BTN_ADD_1
                    dbl_btn = chosen_double_btn

                for _ in range(max_walls - 1):
                    tap(add1_btn, delay=0.9)
                    time.sleep(0.7)
                tap(dbl_btn, delay=1.2)
                time.sleep(1.0)
                tap(BTN_CONFIRM_OKAY, delay=1.5)
                time.sleep(1.5)
            else:
                # Khi còn quá ít tường hoặc Upgrade More mở popup xác nhận trực tiếp -> Chuyển về nâng 1 viên
                cet.log(f"[WALL-UPGRADE] Upgrade More không mở thanh chọn nhiều -> Chuyển sang nâng 1 tường bằng {res_label}...")
                tap((890, 698), delay=0.6)
                tap(POINT_SAFE_DESELECT, delay=0.5)
                tap((wx, wy), delay=0.8)
                tap(chosen_single_btn, delay=0.9)
                tap(BTN_SINGLE_CONFIRM, delay=1.4)
                upgraded_count = 1
        else:
            cet.log(f"[WALL-UPGRADE] Nâng 1 tường bằng {res_label} ({avail_amount:,} / {wall_cost:,})...")
            tap(chosen_single_btn, delay=0.9)
            tap(BTN_SINGLE_CONFIRM, delay=1.4)
            upgraded_count = 1

        # Sau khi bấm nâng thành công, không tự suy đoán cộng dồn tọa độ hàng xóm vào known_l18
        # vì game tự chọn các viên kế tiếp không theo thứ tự mảng lưới.
        cet.log(f"[WALL-UPGRADE] Hoàn tất nâng {upgraded_count} tường bằng {res_label}.")

        return f"UPGRADE_{upgraded_count}_WALLS_{target_res.upper()}_SUCCESS"

    return "SEARCH_EXHAUSTED"


def run_wall_upgrade_session(stop_threshold=WALL_STOP_THRESHOLD_DEFAULT, max_rounds=10):
    """
    Chạy trọn vẹn phiên nâng tường khi kho đạt 24M cho tới khi cả Vàng & Dầu hạ xuống < 6,000,000.
    Sau khi xong tự trả về Làng chính sạch sẽ để gọi lại Con Loop Cày.
    """
    cet.log("==================================================")
    cet.log("🧱 BẮT ĐẦU PHIÊN NÂNG TƯỜNG AI VISION (NÂNG SẠCH TÀI NGUYÊN)")
    cet.log("==================================================")

    cet.adb_shell("settings put system pointer_location 0")
    ensure_clean_home_view()
    cet.zoom_out_pinch(1, sleep_sec=0.25)

    last_resources = None
    no_change_count = 0
    for r_idx in range(1, max_rounds + 1):
        img_home = ensure_clean_home_view()
        g_now, e_now = cvg.read_home_resources(img_home)
        cet.log(f"[WALL-SESSION Vòng #{r_idx}] Kho hiện tại: Vàng = {g_now:,} | Dầu = {e_now:,}")

        if g_now < 6_000_000 and e_now < 6_000_000:
            cet.log("✅ Cả Vàng và Dầu đều < 6,000,000 (đã nâng hết sạch)! Kết thúc nâng tường, chuyển về Loop Cày.")
            return {"ok": True, "reason": "REACHED_STOP_THRESHOLD", "gold": g_now, "elixir": e_now}

        if last_resources == (g_now, e_now):
            no_change_count += 1
            if no_change_count >= 2:
                cet.log("⚠️ Tài nguyên không thay đổi sau 2 lượt thử -> Thoát phiên nâng tường để về Loop Cày.")
                return {"ok": False, "reason": "NO_RESOURCE_CHANGE_GUARD", "gold": g_now, "elixir": e_now}
        else:
            no_change_count = 0
        last_resources = (g_now, e_now)

        res = cmd_execute_wall_upgrade(start_coord=None, resource="auto", stop_threshold=stop_threshold)
        cet.log(f"[WALL-SESSION Vòng #{r_idx}] Kết quả: {res}")
        time.sleep(1.5)

        if res in ("DONE_REACHED_STOP_THRESHOLD", "INSUFFICIENT_RESOURCES", "SEARCH_EXHAUSTED"):
            img_end = ensure_clean_home_view()
            g_end, e_end = cvg.read_home_resources(img_end)
            cet.log(f"🏁 Kết thúc phiên nâng tường ({res}) | Kho còn: Vàng = {g_end:,} | Dầu = {e_end:,}")
            return {"ok": True, "reason": res, "gold": g_end, "elixir": e_end}

    img_final = ensure_clean_home_view()
    g_fin, e_fin = cvg.read_home_resources(img_final)
    return {"ok": True, "reason": "MAX_ROUNDS_REACHED", "gold": g_fin, "elixir": e_fin}


if __name__ == "__main__":
    print("Testing AI Vision Wall Upgrade Manager (dry check only)...")
