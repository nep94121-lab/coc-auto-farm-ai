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
BTN_UPGRADE_GOLD = (1205, 854)
BTN_UPGRADE_ELIXIR = (1415, 844)
BTN_UPGRADE_CONFIRM = (1473, 935)
BTN_UPGRADE_MORE = (1028, 844)
BTN_ADD_1 = (1009, 868)
BTN_CONFIRM_OKAY = (1316, 680)
POINT_SAFE_DESELECT = (1815, 480)  # Vùng cỏ trống bên phải, tránh Trader (480, 120)

# ------------------------------------------------------------------------------
# 2. VÙNG CẮT AI VISION & VECTOR BƯỚC NHẢY CỤM TƯỜNG XANH XÁM (LEVEL 16)
# ------------------------------------------------------------------------------
BOX_WALL_LEVEL = (820, 665, 1520, 758)
BOX_UPGRADE_BUTTONS = (1125, 755, 1494, 949)
BOX_RESOURCE_BAR = cvg.BOX_RESOURCE_BAR

# Gốc và vector chuẩn của cụm tường xanh xám (đi dọc cột xuống, rồi dịch sang cột phải)
WALL_ORIGIN_FALLBACK = (1020, 450)
DELTA_ROW_X = 20   # Đi dọc từ trên xuống dưới trong 1 cột: X + 20, Y + 15
DELTA_ROW_Y = 15
DELTA_COL_X = 23   # Dịch từ cột trái sang cột bên phải: X + 23, Y - 17
DELTA_COL_Y = -17

MAX_WALL_LEVEL = 17
WALL_STOP_THRESHOLD_DEFAULT = 3_000_000


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
    """Chỉ xác nhận hợp lệ khi có thanh 5 nút Tường chuẩn và đọc được Level tường."""
    if full_img is None:
        return False
    if not cvg.is_five_button_wall_bar(full_img):
        return False
    return ai_read_wall_level(full_img) > 0


def ai_read_hammer_cost(full_img):
    """Đọc giá tiền nâng 1 viên tường trên nút búa Vàng hoặc Dầu (hỗ trợ cả chữ trắng lẫn chữ đỏ)."""
    if full_img is None or full_img.size == 0:
        return 0
    if full_img.shape[0] < 800:
        return 0

    for x1, x2 in [(1130, 1278), (1335, 1485)]:
        crop = full_img[758:795, x1:x2]
        b, g, r = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
        mask = ((r > 190) & (r >= b)).astype(np.uint8) * 255
        val = cvg._extract_digits_from_mask(
            mask, min_h=12, max_h=22, min_w=5, max_w=20, min_area=40, max_y_jitter=4
        )
        if val >= 100_000:
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


def cmd_execute_wall_upgrade(start_coord=None, resource="auto", stop_threshold=WALL_STOP_THRESHOLD_DEFAULT):
    """
    Thực thi 1 đợt nâng tường AI Vision (Level < 17) từ kho tài nguyên thực tế, dừng trước Gem:
    - Tự dò khối tường xanh xám bất kể zoom, đi dọc cột rồi sang phải.
    - Xác nhận đúng menu Wall và cấp < 17.
    - Chỉ tiêu phần tài nguyên vượt ngưỡng giữ an toàn (để hạ về quanh stop_threshold ~3M).
    """
    img_home = ensure_clean_home_view()
    if img_home is None:
        return "ERROR_NO_SCREEN"

    if start_coord is not None:
        candidates = [
            (start_coord[0] + c * DELTA_COL_X + r * DELTA_ROW_X, start_coord[1] + c * DELTA_COL_Y + r * DELTA_ROW_Y)
            for c in range(4)
            for r in range(6)
        ]
    else:
        candidates = find_l16_wall_candidates(img_home, max_points=30)

    for idx, (wx, wy) in enumerate(candidates, 1):
        cet.log(f"[WALL-UPGRADE] Quét tường #{idx}/{len(candidates)} tại ({wx}, {wy})...")
        tap((wx, wy), delay=0.9)
        full = capture_full_screen()
        if full is None:
            continue

        if not is_valid_wall_menu(full):
            cet.log(f"[WALL-UPGRADE] ({wx}, {wy}) không phải menu Tường hợp lệ -> Bỏ qua...")
            tap(POINT_SAFE_DESELECT, delay=0.4)
            continue

        wall_lvl = ai_read_wall_level(full)
        cet.log(f"[WALL-UPGRADE] Đọc thấy: Wall Level {wall_lvl}")
        if wall_lvl >= MAX_WALL_LEVEL:
            cet.log(f"[WALL-UPGRADE] Tường đã Level {wall_lvl} (>= {MAX_WALL_LEVEL}) -> Sang viên tiếp theo...")
            continue

        wall_cost = ai_read_hammer_cost(full)
        if wall_cost <= 0:
            cost_map = {13: 1_000_000, 14: 1_500_000, 15: 2_000_000, 16: 2_500_000}
            wall_cost = cost_map.get(wall_lvl, 2_500_000)
        cet.log(f"[WALL-UPGRADE] Giá nâng 1 tường: {wall_cost:,}")

        current_gold, current_elixir = cvg.read_home_resources(full)
        cet.log(f"[WALL-UPGRADE] Kho hiện tại: Vàng = {current_gold:,} | Dầu = {current_elixir:,}")

        if current_gold <= stop_threshold and current_elixir <= stop_threshold:
            tap(POINT_SAFE_DESELECT, delay=0.4)
            return "DONE_REACHED_STOP_THRESHOLD"

        target_res = resource
        if target_res == "auto":
            gold_ok = current_gold > stop_threshold and current_gold >= wall_cost
            elix_ok = current_elixir > stop_threshold and current_elixir >= wall_cost
            if gold_ok and (not elix_ok or current_gold >= current_elixir):
                target_res = "gold"
            elif elix_ok:
                target_res = "elixir"
            else:
                tap(POINT_SAFE_DESELECT, delay=0.4)
                return "INSUFFICIENT_RESOURCES"

        if target_res == "elixir":
            chosen_btn = BTN_UPGRADE_ELIXIR
            avail_amount = current_elixir
            res_label = "Dầu tím"
        else:
            chosen_btn = BTN_UPGRADE_GOLD
            avail_amount = current_gold
            res_label = "Vàng"

        if avail_amount <= stop_threshold or avail_amount < wall_cost:
            tap(POINT_SAFE_DESELECT, delay=0.4)
            return f"INSUFFICIENT_{target_res.upper()}"

        # Tính số tường cần nâng để hạ tài nguyên về vùng ~1.5M..3.0M (tránh thiếu 1 đồng gây bật popup Gem)
        if avail_amount > 4_000_000:
            max_walls = max(1, int((avail_amount - 1_500_000) // wall_cost))
        else:
            max_walls = 1
        max_walls = min(max_walls, 12)

        cet.log(f"[WALL-UPGRADE] Nâng {max_walls} tường bằng {res_label} ({avail_amount:,} / {wall_cost:,})...")

        if max_walls == 1:
            tap(chosen_btn, delay=1.0)
            tap(BTN_UPGRADE_CONFIRM, delay=1.2)
            tap(POINT_SAFE_DESELECT, delay=0.5)
            return f"UPGRADE_1_WALL_{target_res.upper()}_SUCCESS"

        tap(BTN_UPGRADE_MORE, delay=1.0)
        for _ in range(max_walls - 1):
            tap(BTN_ADD_1, delay=0.8)
        tap(chosen_btn, delay=1.0)
        tap(BTN_CONFIRM_OKAY, delay=1.2)
        tap(POINT_SAFE_DESELECT, delay=0.5)
        return f"UPGRADE_BATCH_{target_res.upper()}_SUCCESS"

    tap(POINT_SAFE_DESELECT, delay=0.4)
    return "SEARCH_EXHAUSTED"


def run_wall_upgrade_session(stop_threshold=WALL_STOP_THRESHOLD_DEFAULT, max_rounds=8):
    """
    Chạy trọn vẹn phiên nâng tường khi kho đạt 23M cho tới khi cả Vàng & Dầu hạ xuống <= stop_threshold (~3M).
    Sau khi xong tự trả về Làng chính sạch sẽ để gọi lại Con Loop Cày.
    """
    cet.log("==================================================")
    cet.log(f"🧱 BẮT ĐẦU PHIÊN NÂNG TƯỜNG AI VISION (DỪNG KHI KHO <= {stop_threshold:,})")
    cet.log("==================================================")

    cet.adb_shell("settings put system pointer_location 0")

    last_resources = None
    no_change_count = 0
    for r_idx in range(1, max_rounds + 1):
        img_home = ensure_clean_home_view()
        g_now, e_now = cvg.read_home_resources(img_home)
        cet.log(f"[WALL-SESSION Vòng #{r_idx}] Kho hiện tại: Vàng = {g_now:,} | Dầu = {e_now:,}")

        if g_now <= stop_threshold and e_now <= stop_threshold:
            cet.log(f"✅ ĐÃ HẠ TÀI NGUYÊN XUỐNG <= {stop_threshold:,}! Kết thúc nâng tường, chuyển về Loop Cày.")
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
