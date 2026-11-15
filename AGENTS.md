# AGENTS.md - Huong Dan Cho AI Agent Van Hanh He Thong

Tai lieu nay cung cap ngu canh va quy tac chuan de bat ky AI Agent nao khi tai repo nay ve deu co the ket noi thiet bi Android qua ADB, tu dong dieu phoi nang cap, chay vong lap cay va xu ly su co khong bi treo.

## 1. Quy Tac Khoi Dong Nhanh Cho Agent

1. Kiem tra thiet bi: chay `adb devices` (dam bao trang thai `device`), thu test offline `python -m pytest tests/test_offline_suite.py -v`.
2. Kiem tra cau hinh uu tien dong truoc khi chon nang cap:
   ```bash
   python upgrade_manager_tools.py --show-priority
   ```
   Doc `builder_focus.target_builders`, `priority_targets` (mac dinh: `Archer Tower` -> Max `Level 21`, sau do `Cannon` -> Max `Level 21`) va `resource_stop_thresholds`.
3. Luon thu thap trang thai bang `python upgrade_manager_tools.py --snapshot` va dung tool xem anh doc cac file trong `runtime/upgrade_snapshot/`:
   - `full_1_home.png`: kiem tra tho xay (`X/6`), Lab (`X/2`), Gold / Elixir / Dark Elixir.
   - `full_2_build.png` & `full_2b_build_scrolled.png`: danh sach Buildings & Heroes truoc va sau khi vuot.
   - `full_3_lab.png` & `full_3b_lab_scrolled.png`: danh sach Lab truoc va sau khi vuot.
   - `full_4_pets.png`: danh sach Hero Pets.

## 2. Quy Trinh Tim & Kiem Tra Cong Trinh Max Level (Khong Bam Mu)

1. Neu muc tieu uu tien (`Archer Tower`, `Cannon`, ...) chua thay ngay o trang dau:
   ```bash
   python upgrade_manager_tools.py --scan-build 5
   ```
   Doc lan luot `runtime/scan_build/page_0.png .. page_5.png` de xac dinh trang nao (`scrolls=K`) va dong nao (`scroll_pick_1..8`) chua muc tieu uu tien.
2. Truoc khi quyet dinh nang hoac kiem tra xem da **Max (Level 21)** hay chua:
   ```bash
   python upgrade_manager_tools.py --inspect-pick scroll_pick_<1..8> --scrolls <K> --inspect-mode build
   ```
   Doc anh `runtime/inspect_modal/modal_cropped.png` / `modal_title_level.png` / `modal_confirm_footer.png`:
   - Tieu de: `Upgrade <Ten> to Level <X>?`
   - Thanh mau xanh la: tien do cap do so voi Max (`Level 21`).
   - Nut `Confirm` xanh la + gia tien + thoi gian nang cap.
3. Chi khi xac nhan dung muc tieu, dung level chua Max va du tai nguyen moi goi:
   ```bash
   python upgrade_manager_tools.py --exec-build scroll_pick_<1..8> --scrolls <K>
   ```
4. Voi nha tuong (Heroes) hoac item mo giao dien dat biet giua man hinh: bam vao dong do -> chup man hinh -> xac nhan nut `Upgrade` duoi day man hinh theo toa do thuc te -> ve Home qua `--close-home`.

## 3. Bang Toa Do Chuan `2220x1080`

- **Mo Build & Filter**: Bua `(2093, 966)` -> Filter `(1672, 41)` -> Option `(1308, 741)` -> Out `(2020, 513)`.
- **Chon truoc khi vuot**: `select_product (1843, 644)`, `pick_alt_1 (1820, 737)`, `pick_alt_2 (1794, 831)`, `pick_alt_3 (1801, 898)`.
- **8 vi tri sau khi vuot (`scroll_pick_1..8`)**:
  - `scroll_pick_1`: `(1868, 137)`
  - `scroll_pick_2`: `(1728, 236)`
  - `scroll_pick_3`: `(1894, 333)`
  - `scroll_pick_4`: `(1839, 445)`
  - `scroll_pick_5`: `(1816, 528)`
  - `scroll_pick_6`: `(1780, 644)`
  - `scroll_pick_7`: `(1775, 722)`
  - `scroll_pick_8`: `(1797, 836)`
- **4 buoc Build**: `slot_1 (1748, 279)` -> `slot_2 (1754, 460)` -> `slot_3 (1758, 637)` -> `confirm_upgrade (1486, 959)`.
- **Lab & Pets**: Lab `(1812, 1011)` + `(1854, 561)` + confirm `(1470, 943)`; Pets `(2166, 1009)` + `(1849, 564)` + confirm `(1496, 949)`.
- **Thoat ve Home & Thu nho**: `(1800, 38)` hoac X `(2165, 41)`, tu dong goi `zoom_out_pinch`.

## 4. Xu Ly Su Co Khi Cac Vong Lap Goi AI Ra Giai Quyet

- Khi chạy `loop_cay_tai_nguyen_doc_lap.py --no-wall` nen:
  1. Theo doi `runtime/loop_farm_status.json` va `runtime/live_log.txt`.
  2. Neu xuat hien `runtime/loop_error_alert.json` hoac `runtime/upgrade_alert.json`, agent phai doc ngay JSON canh bao + mo anh trong `runtime/alerts/` de chan doan nguyen nhan (mat ket noi ADB, popup la, vang nha qua thap, ket Battle).
  3. Chay `python upgrade_manager_tools.py --restart-home` de reset app sach ve Lang chinh, sua nguyen nhan neu can, roi khoi dong lai vong lap va giu nguyen cac lich hen gio nang cap con hieu luc.
- Sau moi lan nang cap hoan tat, luon goi `--test-wakeup` de tinh `min_timer + 3 phut` roi dat lich kiem tra lai truoc khi bat lai `--no-wall`.
