import os
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_PATH = os.path.join(BASE_DIR, "assets", "coc_digit_templates.npz")
RETURN_HOME_TPL_PATH = os.path.join(BASE_DIR, "assets", "return_home_template.png")
COIN_TPL_PATH = os.path.join(BASE_DIR, "assets", "coc_battle_gold_icon.png")
ELIX_TPL_PATH = os.path.join(BASE_DIR, "assets", "coc_battle_elixir_icon.png")

DIGIT_TPLS = dict(np.load(TPL_PATH))
_RETURN_HOME_TPL = cv2.imread(RETURN_HOME_TPL_PATH, cv2.IMREAD_GRAYSCALE) if os.path.exists(RETURN_HOME_TPL_PATH) else None
_COIN_TPL = cv2.imread(COIN_TPL_PATH) if os.path.exists(COIN_TPL_PATH) else None
_ELIX_TPL = cv2.imread(ELIX_TPL_PATH) if os.path.exists(ELIX_TPL_PATH) else None

SLOTS_META = [
    {"slot": 1, "name": "Super Yeti", "box": (275, 830, 400, 980), "tap": (338, 900)},
    {"slot": 2, "name": "Super Wall Breaker", "box": (420, 830, 550, 980), "tap": (486, 900)},
    {"slot": 3, "name": "Siege Barracks", "box": (575, 830, 700, 980), "tap": (638, 900)},
    {"slot": 4, "name": "Minion Prince (Warden)", "box": (730, 830, 855, 980), "tap": (794, 900)},
    {"slot": 5, "name": "Archer Queen", "box": (875, 830, 1005, 980), "tap": (940, 900)},
    {"slot": 6, "name": "Barbarian King", "box": (1025, 830, 1155, 980), "tap": (1089, 900)},
    {"slot": 7, "name": "Royal Champion", "box": (1170, 830, 1300, 980), "tap": (1235, 900)},
    {"slot": 8, "name": "Clone Spell", "box": (1325, 830, 1455, 980), "tap": (1391, 900)},
    {"slot": 9, "name": "Rage Spell", "box": (1475, 830, 1605, 980), "tap": (1540, 900)},
    {"slot": 10, "name": "Clan Castle Spell", "box": (1630, 830, 1760, 980), "tap": (1696, 900)},
]


def _extract_digits_from_mask(mask, min_h=16, max_h=25, min_w=6, max_w=26, min_area=80, max_y_jitter=None, max_x_gap=None):
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    cands = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if min_h <= h <= max_h and min_w <= w <= max_w and area >= min_area:
            cands.append((x, y, w, h))
    if not cands:
        return 0
    if max_y_jitter is not None:
        med_y = float(np.median([c[1] for c in cands]))
        cands = [c for c in cands if abs(c[1] - med_y) <= max_y_jitter]
        if not cands:
            return 0
    cands.sort(key=lambda item: item[0])
    if max_x_gap is not None and len(cands) > 1:
        # Số trên thanh tài nguyên luôn căn phải; loại bỏ nhiễu nền lọt ở mép trái nếu cách > max_x_gap
        kept = [cands[-1]]
        for idx in range(len(cands) - 2, -1, -1):
            cur = cands[idx]
            nxt = kept[0]
            gap = nxt[0] - (cur[0] + cur[2])
            if gap > max_x_gap:
                break
            kept.insert(0, cur)
        cands = kept
    digits = []
    for x, y, w, h in cands:
        patch = cv2.resize(mask[y : y + h, x : x + w], (16, 24)).astype(np.float32)
        best_ch = max(
            DIGIT_TPLS.keys(),
            key=lambda c: float(np.sum(patch * DIGIT_TPLS[c]))
            / (float(np.linalg.norm(patch) * np.linalg.norm(DIGIT_TPLS[c])) + 1e-6),
        )
        digits.append(best_ch)
    s = "".join(digits)
    return int(s) if s.isdigit() else 0


def read_coc_number(crop):
    """Đọc số trắng viền đen của Clash of Clans bằng connected-components + template matching."""
    if crop is None or crop.size == 0:
        return 0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # 1. Otsu — tự động tìm ngưỡng sáng/tối tối ưu (hoạt động với cả số vàng, trắng, tím)
    _, mask_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    res = _extract_digits_from_mask(mask_otsu, min_h=15, max_h=28, min_w=5, max_w=28, min_area=70)
    if res > 0:
        return res

    # 2. Dự phòng: threshold cứng gray>100 (màn hình sáng)
    mask_gray = (gray > 100).astype(np.uint8) * 255
    res = _extract_digits_from_mask(mask_gray, min_h=15, max_h=28, min_w=5, max_w=28, min_area=70)
    if res > 0:
        return res

    # 3. Dự phòng: ngưỡng RGB cũ
    b, g_ch, r = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    mask_rgb = ((r > 190) & (g_ch > 185) & (b > 170)).astype(np.uint8) * 255
    return _extract_digits_from_mask(mask_rgb, min_h=15, max_h=28, min_w=5, max_w=28, min_area=50)


def read_enemy_loot(img):
    """
    Trả về (enemy_gold, enemy_elixir) riêng rẽ từ góc trên bên trái màn hình trận đánh.
    Sử dụng neo biểu tượng động (Gold coin & Elixir droplet) để định vị tuyệt đối 100%.
    """
    if img is None:
        return 0, 0

    h_img, w_img = img.shape[:2]
    search_h = min(400, h_img)
    search_w = min(500, w_img)
    region = img[:search_h, :search_w]

    # 1. Tìm neo biểu tượng đồng tiền Vàng
    gold = 0
    if _COIN_TPL is not None and search_h >= 60 and search_w >= 80:
        r_coin = cv2.matchTemplate(region, _COIN_TPL, cv2.TM_CCOEFF_NORMED)
        _, max_c, _, loc_c = cv2.minMaxLoc(r_coin)
        if max_c >= 0.70:
            x_c, y_c = loc_c
            crop_g = region[max(0, y_c + 5) : min(search_h, y_c + 45), x_c + 50 : min(search_w, x_c + 320)]
            gold = read_coc_number(crop_g)

    # 2. Tìm neo biểu tượng giọt dầu Tiên dược
    elixir = 0
    if _ELIX_TPL is not None and search_h >= 60 and search_w >= 80:
        r_elix = cv2.matchTemplate(region, _ELIX_TPL, cv2.TM_CCOEFF_NORMED)
        _, max_e, _, loc_e = cv2.minMaxLoc(r_elix)
        if max_e >= 0.70:
            x_e, y_e = loc_e
            crop_e = region[max(0, y_e + 5) : min(search_h, y_e + 45), x_e + 50 : min(search_w, x_e + 320)]
            elixir = read_coc_number(crop_e)

    # 3. Dự phòng theo tọa độ cố định mở rộng nếu không khớp mẫu icon
    if gold == 0 and h_img >= 260 and w_img >= 380:
        gold = read_coc_number(img[125:175, 90:350])
    if elixir == 0 and h_img >= 260 and w_img >= 380:
        elixir = read_coc_number(img[180:235, 90:350])

    return gold, elixir


BOX_RESOURCE_BAR = (1849, 43, 2206, 228)


def crop_home_resource_bar(img):
    """Cắt vùng thanh tài nguyên Vàng, Dầu tím & Dầu đen góc trên bên phải màn hình Làng chính."""
    if img is None:
        return None
    x1, y1, x2, y2 = BOX_RESOURCE_BAR
    return img[y1:y2, x1:x2]


def _read_home_bar_number(crop):
    """Đọc số trắng trên thanh tài nguyên Làng chính, ưu tiên tách chữ trắng tinh và chống đứt nét chữ số đầu."""
    if crop is None or crop.size == 0:
        return 0
    b, g, r = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    kwargs = dict(min_h=18, max_h=27, min_w=5, max_w=26, min_area=65, max_y_jitter=4, max_x_gap=22)
    best_res = 0
    for thresh in (210, 185):
        mask = ((r > thresh) & (g > thresh) & (b > thresh)).astype(np.uint8) * 255
        res = _extract_digits_from_mask(mask, **kwargs)
        if res > best_res:
            best_res = res
        if res >= 10_000_000:
            return res
    if best_res > 0:
        return best_res

    # Fallback khi màn hình bị làm tối do popup: chữ xám trung tính (R~G~B)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    max_c = np.maximum(np.maximum(r, g), b).astype(np.int16)
    min_c = np.minimum(np.minimum(r, g), b).astype(np.int16)
    neutral = ((gray > 105) & ((max_c - min_c) < 25)).astype(np.uint8) * 255
    res = _extract_digits_from_mask(neutral, **kwargs)
    if res > 0:
        return res
    return read_coc_number(crop)


def read_home_dark_elixir(img):
    """Đọc lượng Dầu đen (Dark Elixir) ở góc trên bên phải Làng chính."""
    if img is None:
        return 0
    return _read_home_bar_number(img[170:225, 1960:2140])


def read_home_resources(img):
    """Trả về (home_gold, home_elixir) từ góc trên bên phải màn hình làng chính."""
    if img is None:
        return 0, 0
    # Cắt rộng từ x=1905: ôm trọn cả 24,8xx,xxx..25M+ lẫn chống cắt đáy y=142 của Dầu tím
    gold = _read_home_bar_number(img[38:76, 1905:2138])
    elixir = _read_home_bar_number(img[110:152, 1905:2138])
    return gold, elixir


def read_all_home_resources(img):
    """Trả về đầy đủ (home_gold, home_elixir, home_dark_elixir) tại màn hình Làng chính."""
    if img is None:
        return 0, 0, 0
    gold, elixir = read_home_resources(img)
    dark_elixir = read_home_dark_elixir(img)
    return gold, elixir, dark_elixir


def read_shifted_resources(img):
    """Đọc (gold, elixir, dark_elixir) ở vùng dạt trái khi bảng Búa / Lab / Thú cưng đang mở."""
    if img is None:
        return 0, 0, 0
    gold = _read_home_bar_number(img[38:76, 1295:1550])
    elixir = _read_home_bar_number(img[110:152, 1295:1550])
    dark_elixir = _read_home_bar_number(img[170:222, 1355:1550])
    return gold, elixir, dark_elixir


def is_upgrade_drawer_open(img):
    """Xác nhận ngăn kéo bên phải (Buildings & Heroes / Army Upgrades / Hero Pets) đang mở qua nút X đỏ."""
    if img is None:
        return False
    crop = img[5:80, 2115:2205]
    red_px = np.sum((crop[:, :, 2] > 170) & (crop[:, :, 1] < 70) & (crop[:, :, 0] < 70))
    return int(red_px) > 350


def is_battle_button_visible(img):
    """Kiểm tra nút Battle màu vàng cam góc trái dưới ở Làng chính."""
    if img is None:
        return False
    crop = img[885:1055, 25:195]
    yellow_px = np.sum((crop[:, :, 2] > 210) & (crop[:, :, 1] > 140) & (crop[:, :, 0] < 80))
    return int(yellow_px) > 4000


def is_in_battle(img):
    """Kiểm tra nút đỏ End Battle / Surrender ở góc trái dưới (x=30..240, y=770..840)."""
    if img is None:
        return False
    red_px = np.sum(
        (img[770:840, 30:240, 2] > 190)
        & (img[770:840, 30:240, 1] < 60)
        & (img[770:840, 30:240, 0] < 60)
    )
    return int(red_px) > 1200


def is_next_button_visible(img):
    """Kiểm tra nút Next màu cam ở góc phải dưới (chỉ hợp lệ khi đã vào trận và không ở Làng chính)."""
    if img is None or is_battle_button_visible(img) or not is_in_battle(img):
        return False
    crop = img[660:790, 1890:2180]
    orange_px = np.sum((crop[:, :, 2] > 200) & (crop[:, :, 1] > 110) & (crop[:, :, 0] < 80))
    return int(orange_px) > 1500


def is_reload_game_dialog(img):
    """Kiểm tra hộp thoại mất kết nối / Anyone there? có nút Reload game màu xanh dương."""
    if img is None:
        return False
    crop = img[930:1010, 890:1190]
    b, g, r = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    blue_px = np.sum((b > 180) & (g > 100) & (r < 110))
    return int(blue_px) > 800


def is_return_home_visible(img):
    """Kiểm tra nút Return Home màu xanh lá giữa đáy màn hình tổng kết trận (hỗ trợ cả Victory và Defeat)."""
    if img is None:
        return False
    if is_battle_button_visible(img):
        return False
    
    # 1. Đối sánh mẫu template chính xác tuyệt đối
    if _RETURN_HOME_TPL is not None:
        try:
            region = img[780:990, 940:1280]
            if region.shape[0] >= _RETURN_HOME_TPL.shape[0] and region.shape[1] >= _RETURN_HOME_TPL.shape[1]:
                region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                res = cv2.matchTemplate(region_gray, _RETURN_HOME_TPL, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val >= 0.72:
                    return True
        except Exception:
            pass

    # 2. Dự phòng nhận diện dải màu xanh lá và chữ trắng (nút Return Home thực tế nằm ở y=880..979)
    btn = img[850:980, 960:1260]
    b, g, r = btn[:, :, 0], btn[:, :, 1], btn[:, :, 2]
    green = np.sum((g > 110) & (g > r + 15) & (g > b + 15))
    white = np.sum((r > 190) & (g > 190) & (b > 190))
    return int(green) > 3500 and int(white) > 500


def is_five_button_wall_bar(img):
    """Xác nhận chính xác 100% thanh 5 nút của Tường (Wall) trải rộng từ x=500..1520."""
    if img is None:
        return False
    b1 = img[750:855, 520:660]
    b5 = img[750:855, 1350:1490]
    tan1 = np.sum((b1[:, :, 2] > 165) & (b1[:, :, 1] > 155) & (b1[:, :, 0] > 130))
    tan5 = np.sum((b5[:, :, 2] > 165) & (b5[:, :, 1] > 155) & (b5[:, :, 0] > 130))
    return int(tan1) > 2000 and int(tan5) > 2000


def is_upgrade_button_affordable(img, use_gold=True):
    """Kiểm tra nút nâng cấp màu xanh lá cây sáng (>2000 px), chứng minh đủ tiền nâng."""
    if img is None:
        return False
    crop = img[740:870, 1280:1440] if use_gold else img[740:870, 1450:1620]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, (35, 80, 80), (85, 255, 255))
    return int(np.sum(green_mask > 0)) > 2000


def is_confirm_wall_modal_green(img):
    """Xác nhận bảng lớn Upgrade Wall có nền trắng bên phải (>210) và nút xanh cốm Confirm (1500,875) sáng (>8000 px)."""
    if img is None:
        return False
    panel_white = float(np.mean(img[300:580, 1100:1750]))
    btn = img[820:930, 1360:1640].astype(np.int16)
    lime = np.sum((btn[:, :, 1] > 185) & (btn[:, :, 1] >= btn[:, :, 2] - 10) & (btn[:, :, 1] - btn[:, :, 0] > 65))
    return panel_white > 210.0 and int(lime) > 8000


def inspect_army_slots(img):
    """Kiểm tra trạng thái còn quân (available=True) hay đã xám hết quân (available=False) của 4 ô."""
    results = []
    if img is None:
        return results
    for item in SLOTS_META:
        x1, y1, x2, y2 = item["box"]
        crop = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mean_sat = float(np.mean(hsv[:, :, 1]))
        results.append(
            {
                "slot": item["slot"],
                "name": item["name"],
                "tap": list(item["tap"]),
                "available": mean_sat > 45.0,
                "saturation": round(mean_sat, 1),
            }
        )
    return results


def draw_coordinate_grid(img, step=100, major_step=200, show_battle_safe_box=False):
    """
    Vẽ lưới tọa độ (x, y) trực quan lên ảnh 2220x1080 để AI Planner ('Con Báo Tọa Độ')
    nhìn mắt thường đọc chính xác từng điểm thả quân / nâng tường.
    """
    if img is None:
        return None
    h, w = img.shape[:2]
    overlay = img.copy()

    # Đường lưới phụ mỗi 100px (trắng mờ) và đường lưới chính mỗi 200px (vàng/cyan rõ)
    for x in range(0, w, step):
        is_major = (x % major_step == 0)
        color = (0, 255, 255) if is_major else (200, 200, 200)
        thickness = 2 if is_major else 1
        cv2.line(overlay, (x, 0), (x, h), color, thickness)

    for y in range(0, h, step):
        is_major = (y % major_step == 0)
        color = (255, 255, 0) if is_major else (200, 200, 200)
        thickness = 2 if is_major else 1
        cv2.line(overlay, (0, y), (w, y), color, thickness)

    out = cv2.addWeighted(overlay, 0.38, img, 0.62, 0)

    # Nếu đang trong trận, vẽ khung an toàn được phép chạm thả quân (tránh bấm thanh lính & nút Next/End)
    if show_battle_safe_box:
        cv2.rectangle(out, (120, 55), (2100, 835), (0, 255, 0), 2)

    font = cv2.FONT_HERSHEY_SIMPLEX
    # Gắn nhãn trục X ở viền trên và dưới
    for x in range(major_step, w, major_step):
        lbl = f"X={x}"
        for y_pos in (26, h - 14):
            cv2.rectangle(out, (x - 34, y_pos - 18), (x + 38, y_pos + 5), (0, 0, 0), -1)
            cv2.putText(out, lbl, (x - 31, y_pos - 2), font, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

    # Gắn nhãn trục Y ở viền trái và phải
    for y in range(major_step, h, major_step):
        lbl = f"Y={y}"
        for x_pos in (8, w - 78):
            cv2.rectangle(out, (x_pos, y - 16), (x_pos + 70, y + 6), (0, 0, 0), -1)
            cv2.putText(out, lbl, (x_pos + 3, y), font, 0.45, (255, 255, 0), 1, cv2.LINE_AA)

    # Gắn nhãn tọa độ (x,y) ngay tại các nút giao chính bên trong vùng bản đồ (400..1800, 200..800)
    for y in range(major_step, 850, major_step):
        for x in range(400, 1900, major_step):
            tag = f"{x},{y}"
            cv2.circle(out, (x, y), 4, (0, 0, 255), -1)
            cv2.rectangle(out, (x + 4, y - 13), (x + 68, y + 3), (0, 0, 0), -1)
            cv2.putText(out, tag, (x + 6, y - 1), font, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

    return out
