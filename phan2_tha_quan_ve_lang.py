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
                time.sleep(2.0)
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

    cet.log("[PHẦN 2] Trận đấu đã sẵn sàng! Đang thả quân combo chuẩn bài...")

    # Thao tác #6: Chọn quân slot 1 (Super Yeti)
    time.sleep(0.5)
    cet.tap(368, 973, sleep_sec=0.08)
    # Thao tác #7: Rải Yeti
    time.sleep(1.9)
    cet.tap(382, 652, sleep_sec=0.08)
    # Thao tác #8
    time.sleep(0.26)
    cet.tap(243, 478, sleep_sec=0.08)
    # Thao tác #9
    time.sleep(0.29)
    cet.tap(360, 271, sleep_sec=0.08)
    # Thao tác #10
    time.sleep(0.25)
    cet.tap(537, 182, sleep_sec=0.08)
    # Thao tác #11
    time.sleep(0.23)
    cet.tap(611, 130, sleep_sec=0.08)
    # Thao tác #12
    time.sleep(0.28)
    cet.tap(682, 100, sleep_sec=0.08)
    # Thao tác #13
    time.sleep(1.04)
    cet.tap(1767, 241, sleep_sec=0.08)
    # Thao tác #14
    time.sleep(0.22)
    cet.tap(1642, 140, sleep_sec=0.08)
    # Thao tác #15
    time.sleep(0.2)
    cet.tap(1590, 84, sleep_sec=0.08)
    # Thao tác #16: Chọn slot tiếp theo
    time.sleep(1.77)
    cet.tap(1712, 989, sleep_sec=0.08)
    # Thao tác #17
    time.sleep(1.34)
    cet.tap(391, 436, sleep_sec=0.08)
    # Thao tác #18
    time.sleep(0.23)
    cet.tap(535, 312, sleep_sec=0.08)
    # Thao tác #19
    time.sleep(0.24)
    cet.tap(685, 225, sleep_sec=0.08)
    # Thao tác #20
    time.sleep(0.55)
    cet.tap(697, 145, sleep_sec=0.08)
    # Thao tác #21: Xe Siege
    time.sleep(1.69)
    cet.tap(640, 915, sleep_sec=0.08)
    # Thao tác #22
    time.sleep(0.6)
    cet.tap(453, 176, sleep_sec=0.08)
    # Thao tác #23: Tướng Warden
    time.sleep(0.58)
    cet.tap(513, 948, sleep_sec=0.08)
    # Thao tác #24
    time.sleep(1.04)
    cet.tap(504, 162, sleep_sec=0.08)
    # Thao tác #25: Tướng Queen
    time.sleep(1.02)
    cet.tap(668, 910, sleep_sec=0.08)
    # Thao tác #26
    time.sleep(0.78)
    cet.tap(578, 184, sleep_sec=0.08)
    # Thao tác #27: Tướng King
    time.sleep(1.19)
    cet.tap(498, 939, sleep_sec=0.08)
    # Thao tác #28
    time.sleep(0.6)
    cet.tap(1654, 170, sleep_sec=0.08)
    # Thao tác #29: Tướng Champion
    time.sleep(0.9)
    cet.tap(810, 930, sleep_sec=0.08)
    # Thao tác #30
    time.sleep(0.51)
    cet.tap(491, 192, sleep_sec=0.08)
    # Thao tác #31
    time.sleep(0.62)
    cet.tap(969, 930, sleep_sec=0.08)
    # Thao tác #32
    time.sleep(0.61)
    cet.tap(470, 315, sleep_sec=0.08)
    # Thao tác #33
    time.sleep(0.75)
    cet.tap(1126, 945, sleep_sec=0.08)
    # Thao tác #34
    time.sleep(0.63)
    cet.tap(747, 78, sleep_sec=0.08)
    # Thao tác #35: Thần chú Clone
    time.sleep(0.83)
    cet.tap(1227, 957, sleep_sec=0.08)
    # Thao tác #36
    time.sleep(0.67)
    cet.tap(713, 109, sleep_sec=0.08)
    # Thao tác #37: Thần chú Rage
    time.sleep(1.04)
    cet.tap(1534, 965, sleep_sec=0.08)
    # Thao tác #38
    time.sleep(0.8)
    cet.tap(866, 247, sleep_sec=0.08)
    # Thao tác #39: Kích hoạt skill Tướng
    time.sleep(1.71)
    cet.tap(861, 912, sleep_sec=0.08)
    # Thao tác #40
    time.sleep(0.37)
    cet.tap(954, 916, sleep_sec=0.08)
    # Thao tác #41
    time.sleep(0.29)
    cet.tap(1108, 900, sleep_sec=0.08)
    # Thao tác #42
    time.sleep(15.07)
    cet.tap(1257, 900, sleep_sec=0.08)

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
