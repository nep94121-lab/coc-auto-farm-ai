# PHẦN 1: TỰ ĐỘNG VÀO TRẬN, TÌM & LỌC TÀI NGUYÊN (CHỈ ĐÁNH KHI CẢ VÀNG >= 1M VÀ DẦU >= 1M)
# KHI ĐẠT CHUẨN -> TỰ ĐỘNG GỌI [PHẦN 2] RA THẢ QUÂN TIÊU DIỆT ĐỐI THỦ
import time
import os
import sys
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import coc_executor_tools as cet
import coc_vision_grid as cvg
import phan2_tha_quan_ve_lang as p2

def enter_first_match():
    """Từ Làng chính thu nhỏ camera trước, rồi bấm chuỗi 5 bước để vào mây tìm trận."""
    cet.log("[PHẦN 1] Thu nhỏ camera Làng chính trước khi vào Battle...")
    cet.zoom_out_pinch(repeats=1, sleep_sec=0.25)
    cet.log("[PHẦN 1] Bắt đầu vào tìm trận từ Làng chính...")
    
    # 1. Bấm nút Battle ở Làng
    cet.log("[PHẦN 1 - Thao tác 1] Bấm nút Battle (184, 934)...")
    cet.tap(184, 934, sleep_sec=0.08)

    # 2. Bấm vào giao diện quân
    time.sleep(2.93)
    cet.log("[PHẦN 1 - Thao tác 2] Bấm mở giao diện quân (334, 793)...")
    cet.tap(334, 793, sleep_sec=0.08)

    # 3. Bấm nhận bánh Clan Castle
    time.sleep(1.92)
    cet.log("[PHẦN 1 - Thao tác 3] Bấm nhận bánh Clan Castle (1738, 848)...")
    cet.tap(1738, 848, sleep_sec=0.08)

    # 4. Xác nhận nhận bánh
    time.sleep(1.91)
    cet.log("[PHẦN 1 - Thao tác 4] Bấm xác nhận bánh (1306, 749)...")
    cet.tap(1306, 749, sleep_sec=0.08)

    # 5. Bấm nút Attack!
    time.sleep(2.59)
    cet.log("[PHẦN 1 - Thao tác 5] Bấm nút Attack! màu xanh (1828, 990)...")
    cet.tap(1828, 990, sleep_sec=0.08)
    return True

def run_scout_loop_and_attack(min_gold=1_000_000, min_elixir=1_000_000, max_searches=60):
    """
    Vòng lặp tìm kiếm đối thủ thông minh:
    - AI nhìn đọc tài nguyên Vàng & Dầu góc trên bên trái.
    - Nếu CẢ 2 BÊN >= min_gold VÀ >= min_elixir -> Gọi ngay Phần 2 ra đánh!
    - Nếu chưa đạt -> Tự bấm nút Next (1950, 720) để tìm tiếp.
    """
    cet.log(f"=== BẮT ĐẦU [PHẦN 1]: TÌM TRẬN & LỌC TÀI NGUYÊN (YÊU CẦU: VÀNG >= {min_gold:,} & DẦU >= {min_elixir:,}) ===")
    
    # Kiểm tra xem đang ở Làng hay đã ở trong trận sẵn
    img_init = cet.capture_screen()
    if cvg.is_battle_button_visible(img_init) or (
        not cvg.is_in_battle(img_init) and not cvg.is_next_button_visible(img_init)
    ):
        enter_first_match()

    search_count = 0
    while search_count < max_searches:
        search_count += 1
        cet.log(f"--- [LƯỢT #{search_count}] Đang chờ mây tan... ---")
        
        # Chờ mây tan (nút End Battle đỏ và Next cam xuất hiện, không phải màn hình Làng chính)
        t_wait = time.time()
        in_battle_ready = False
        img = None
        while time.time() - t_wait < 25.0:
            img = cet.capture_screen()
            if (
                img is not None
                and not cvg.is_battle_button_visible(img)
                and (cvg.is_in_battle(img) or cvg.is_next_button_visible(img))
            ):
                in_battle_ready = True
                break
            time.sleep(0.4)

        if not in_battle_ready or img is None:
            cet.log(f"[PHẦN 1] CẢNH BÁO: Mây xoay quá 25s ở lượt #{search_count}!")
            break

        # AI nhìn đọc số tài nguyên góc trên trái
        gold, elix = cvg.read_enemy_loot(img)
        cet.log(f"[LƯỢT #{search_count}] Nhà đối thủ có: VÀNG = {gold:,} | DẦU = {elix:,}")

        # Kiểm tra điều kiện CẢ 2 BÊN ĐỀU >= 1M
        if gold >= min_gold and elix >= min_elixir:
            cet.log("==================================================")
            cet.log(f"🎯🎯🎯 [LƯỢT #{search_count}] TÌM THẤY MỤC TIÊU KHỦNG ĐẠT CHUẨN!")
            cet.log(f"   💰 VÀNG = {gold:,} (>= {min_gold:,})")
            cet.log(f"   💧 DẦU  = {elix:,} (>= {min_elixir:,})")
            cet.log(">>> GỌI [PHẦN 2] RA XẢ QUÂN TIÊU DIỆT ĐỐI THỦ NGAY! <<<")
            cet.log("==================================================")
            
            # GỌI PHẦN 2 NGAY LẬP TỨC
            p2.run_battle()
            return {"ok": True, "target_found": True, "gold": gold, "elixir": elix, "searches": search_count}
        else:
            cet.log(f"[LƯỢT #{search_count}] Chưa đạt chuẩn (Cần cả 2 >= 1M) -> Bấm nút Next tìm nhà tiếp theo...")
            # Bấm nút Next màu cam ở góc phải dưới (1950, 720)
            cet.tap(1950, 720, sleep_sec=0.2)
            time.sleep(1.5)

    cet.log(f"[PHẦN 1] Đã tìm {max_searches} lượt chưa gặp nhà >= 1M, đưa game về Làng chính an toàn...")
    img_end = cet.capture_screen()
    if cvg.is_in_battle(img_end):
        cet.tap(135, 805, sleep_sec=0.8)   # End Battle
        cet.tap(1320, 680, sleep_sec=1.5)  # OK confirm
        time.sleep(1.0)
    
    if not p2.dismiss_return_home_safely():
        cet.close_all_modals()
    return {"ok": False, "target_found": False, "searches": search_count}

if __name__ == "__main__":
    run_scout_loop_and_attack()
