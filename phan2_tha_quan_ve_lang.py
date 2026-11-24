# PHẦN 2: THỰC THI THẢ QUÂN COMBO CHUẨN XÁC & VỀ LÀNG AN TOÀN
# (CÓ VÒNG LẶP CHỐNG TREO RETURN HOME - TỰ ĐỘNG CHỜ HẾT ANIMATION VÀ BẤM CHO TỚI KHI VỀ LÀNG)
import time
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import coc_executor_tools as cet
import coc_vision_grid as cvg

def dismiss_return_home_safely():
    """Vòng lặp bấm nút Return Home chắc chắn 100% không bao giờ bị kẹt lại."""
    for attempt in range(8):
        img = cet.capture_screen()
        if img is None:
            time.sleep(1.0)
            continue
        if cvg.is_battle_button_visible(img):
            cet.log("[RETURN-HOME] Đã về tới Làng chính thành công!")
            return True
        if cvg.is_reload_game_dialog(img):
            cet.log("[RETURN-HOME] Phát hiện hộp thoại 'Reload game' -> Bấm nạp lại game...")
            cet.tap(1038, 970, sleep_sec=6.0)
            continue
        if cvg.is_return_home_visible(img):
            cet.log(f"[RETURN-HOME] Lần #{attempt+1}: Phát hiện màn hình kết quả trận -> Bấm Return Home (1111, 925)...")
            if attempt >= 2:
                cet.adb_shell("input tap 1111 925")
                # Dự phòng màn hình Rương/Event có nút Continue (1126, 986) & Skip (2007, 1011)
                cet.tap(1126, 986, sleep_sec=0.5)
                cet.tap(2007, 1011, sleep_sec=1.5)
            else:
                cet.tap(1111, 925, sleep_sec=2.0, hold_sec=0.1)
            continue
        if cvg.is_in_battle(img):
            cet.log("[RETURN-HOME] Vẫn còn ở trận đấu -> Bấm End Battle...")
            cet.tap(135, 805, sleep_sec=0.8)
            cet.tap(1320, 680, sleep_sec=1.5)
            time.sleep(1.0)
            continue
        
        # Dự phòng: Đóng modal cản trở nếu chưa về Làng
        cet.log(f"[RETURN-HOME] Lần #{attempt+1}: Chưa thấy Làng chính, thử đóng modal...")
        cet.close_all_modals()
        time.sleep(1.0)
    return False

# Kịch bản thả quân + tướng + phép + bật skill ghi nhận từ thao tác thực tế (18/11/2026 - 37 bước).
# Mỗi phần tử: (delay_truoc_khi_bam_giay, x, y, hold_giay)
BATTLE_COMBO_STEPS = [
    (0.500, 1588, 981, 0.059),   # #1
    (1.202, 487, 698, 0.084),    # #2
    (0.994, 569, 169, 0.075),    # #3
    (1.211, 1577, 161, 0.067),   # #4
    (1.144, 370, 956, 0.075),    # #5
    (0.535, 470, 713, 0.050),    # #6
    (0.752, 530, 132, 0.075),    # #7
    (1.446, 1648, 165, 0.100),   # #8
    (1.645, 641, 996, 0.059),    # #9
    (0.893, 1640, 152, 0.084),   # #10
    (2.380, 473, 669, 0.074),    # #11
    (0.610, 622, 141, 0.058),    # #12
    (2.606, 482, 1018, 0.050),   # #13 (góc chọn slot từ 480,1049 -> 482,1018)
    (1.328, 1833, 651, 0.092),   # #14
    (2.080, 608, 840, 0.075),    # #15
    (0.885, 398, 960, 0.118),    # #16
    (0.518, 564, 824, 0.083),    # #17
    (1.052, 1747, 748, 0.142),   # #18
    (0.626, 1958, 495, 0.109),   # #19
    (1.395, 1658, 744, 0.083),   # #20
    (1.011, 838, 945, 0.075),    # #21
    (1.278, 1819, 691, 0.092),   # #22
    (0.727, 983, 970, 0.067),    # #23
    (0.885, 1777, 230, 0.092),   # #24
    (0.743, 1130, 950, 0.067),   # #25
    (1.236, 680, 113, 0.100),    # #26
    (0.777, 1283, 962, 0.059),   # #27
    (1.077, 1787, 247, 0.117),   # #28
    (0.618, 1424, 973, 0.083),   # #29
    (0.969, 1804, 735, 0.100),   # #30
    (5.495, 344, 970, 0.110),    # #31
    (1.888, 1926, 586, 0.045),   # #32
    (0.025, 1929, 574, 0.101),   # #33
    (0.927, 1718, 994, 0.108),   # #34
    (0.935, 1469, 484, 0.093),   # #35
    (5.345, 952, 955, 0.074),    # #36
    (2.337, 1436, 968, 0.078),   # #37
]


def run_battle():
    cet.log("=== BẮT ĐẦU KÍCH HOẠT [PHẦN 2]: THẢ QUÂN COMBO CỦA SẾP ===")

    # 1. Chờ trận đấu thực sự sẵn sàng
    t0 = time.time()
    ready = False
    while time.time() - t0 < 15.0:
        img = cet.capture_screen()
        if img is not None and (cvg.is_in_battle(img) or cvg.is_next_button_visible(img)):
            ready = True
            break
        time.sleep(0.3)
    
    if not ready:
        cet.log("[PHẦN 2] CẢNH BÁO: Chưa vào được trận đấu sau 15s. Hủy chuỗi thả quân!")
        return False

    cet.log(f"[PHẦN 2] Trận đấu đã sẵn sàng! Thu nhỏ bản đồ đối thủ trước khi thả quân...")
    cet.zoom_out_pinch(repeats=1, sleep_sec=0.15)
    cet.log(f"[PHẦN 2] Thực thi combo mới ({len(BATTLE_COMBO_STEPS)} thao tác)...")

    for delay_sec, tx, ty, hold_sec in BATTLE_COMBO_STEPS:
        if delay_sec > 0:
            time.sleep(delay_sec)
        cet.tap(tx, ty, sleep_sec=0.0, hold_sec=hold_sec)

    # Sau khi thả hết quân, tướng, phép và bật hết kỹ năng (#37):
    # Bấm nút tốc độ 1x -> 2x -> 4x (2 lần tại (2141, 595)) nếu vẫn đang trong trận
    img_pre_speed = cet.capture_screen()
    if img_pre_speed is None or (
        not cvg.is_return_home_visible(img_pre_speed)
        and not cvg.is_battle_button_visible(img_pre_speed)
    ):
        cet.log("[PHẦN 2] Đã thả hết quân & kỹ năng -> Bấm nút 1x 2 lần (2141, 595) để tua nhanh 4x!")
        cet.tap(2141, 595, sleep_sec=0.25, hold_sec=0.06)
        cet.tap(2141, 595, sleep_sec=0.25, hold_sec=0.06)
        cet.capture_screen("after_speed_4x.png")

    # ĐỒNG BỘ KẾT THÚC TRẬN: Chờ tối đa 145s để xuất hiện nút Return Home
    cet.log("[PHẦN 2] Đã thả xong toàn bộ combo quân! Đang canh nút Return Home (tối đa 145s)...")
    t_battle_wait = time.time()
    while time.time() - t_battle_wait < 145.0:
        img = cet.capture_screen()
        if img is not None and cvg.is_return_home_visible(img):
            cet.log(f"[PHẦN 2] Trận đấu kết thúc sau {time.time() - t_battle_wait:.1f}s! Bắt đầu chuỗi bấm Return Home an toàn...")
            break
        time.sleep(1.5)

    # Bấm Return Home chắc chắn cho tới khi về Làng (không spam close_all_modals nếu đã về Làng)
    if not dismiss_return_home_safely():
        cet.close_all_modals()
    cet.log("=== [PHẦN 2] ĐÃ VỀ LÀNG CHÍNH HOÀN TẤT AN TOÀN ===")
    return True

if __name__ == "__main__":
    run_battle()
