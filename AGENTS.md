# AGENTS.md - Cam Nang Huong Dan Toan Tap Cho AI Agent Moi

Tai lieu nay giup bat ky AI Agent (hoac nguoi dung) nao sau khi clone repo nay ve deu nam duoc toan bo cau truc ma nguon, quy trinh cai dat tu con so 0, cach khoi dong man hinh dien thoai, cach ghi lai combo danh moi va cach van hanh vong lap cay + nang tuong tu dong 24/7 khong bi out.

---

## 1. Ban Do Du An (Moi Thu Nam O Dau?)

```text
coc-auto-farm-ai/
├── AGENTS.md                        # Tai lieu huong dan chuan cho AI Agent (file nay)
├── README.md                        # Huong dan cai dat nhanh & tong quan he thong
├── requirements.txt                 # Thu vien Python (opencv-python, numpy, pytest, pytest-timeout)
├── config/
│   └── upgrade_priority.json        # Cau hinh dong: nguong dung cay (24M/24M), uu tien tho xay (7 tho)
├── assets/
│   ├── user_battle_combo.jsonl      # Ban sao luu goc 37 thao tac danh do nguoi dung ghi lai
│   ├── coc_digit_templates.npz      # Mau nhan dien chu so OCR (Vang / Dau / Cap tuong / Gia bua)
│   ├── coc_battle_gold_icon.png     # Icon neo doc tai nguyen dich khi soi nha
│   ├── coc_battle_elixir_icon.png
│   ├── return_home_template.png     # Mau nhan dien nut Return Home sau tran
│   ├── zoom_pinch_fast/             # Macro da cham thu nho camera (26 frames /dev/input/event0)
│   └── swipe_list_fast/             # Macro vuot danh sach cong trinh/Lab
├── scripts/
│   ├── Mo_Man_Hinh_CoC.bat          # Mo cua so scrcpy hien man hinh dien thoai (TU DONG KET NOI LAI neu out)
│   ├── Tao_Icon_Desktop.ps1         # Tao shortcut Icon ngoai Desktop tro vao Mo_Man_Hinh_CoC.bat
│   ├── Tao_Icon_Desktop.bat         # File bam 1 click de chay Tao_Icon_Desktop.ps1
│   └── record_combo.py              # Tool ghi/phat lai thao tac cham phan cung (doc thang /dev/input/event0)
├── runtime/
│   └── known_level18_walls.json     # Danh sach toa do cac vien tuong da dat Level 18 (bo qua khi quet)
├── loop_cay_tai_nguyen_doc_lap.py   # DIEM CHAY CHINH: Vong lap cay khép kin <-> Tu dong goi nang tuong
├── phan1_vao_tran_soi_nha.py        # Phan 1: Thu nho -> Battle -> Banh Clan -> Attack -> Loc nha >= 1M/1M
├── phan2_tha_quan_ve_lang.py        # Phan 2: Thuc thi BATTLE_COMBO_STEPS (37 buoc) -> Cho Return Home
├── wall_upgrade_vision_manager.py   # Nang tuong Level 17 -> Max 18 tren luoi 19x16 (304 vien) + ghi nho L18
├── upgrade_manager_tools.py         # Snapshot 6 anh, scan nha/Lab/Pets, sua loi ve Lang chinh
├── coc_vision_grid.py               # Module AI Vision + OCR thanh kho & man hinh game
├── coc_executor_tools.py            # Dieu khien ADB, raw screencap, /dev/input/event0, pin & chong out
├── coc_mcp_server.py                # MCP server (tuy chon) cho cac agent ho tro MCP
└── tests/
    └── test_offline_suite.py        # Bo kiem thu offline bat buoc chay truoc khi bat loop
```

---

## 2. Quy Trinh Set Up Tu Dau Cho May Moi / AI Moi

### Buoc 1: Cai dat cong cu he thong
1. **Python 3.10+**: `pip install -r requirements.txt`
2. **Android Platform Tools (`adb.exe`)**:
   - Cai vao `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` hoac them vao `PATH`, hoac set `$env:ADB_PATH`.
3. **scrcpy (Hien man hinh dien thoai len PC)**:
   - Tai ban Windows tai `https://github.com/Genymobile/scrcpy/releases` va giai nen vao `%LOCALAPPDATA%\scrcpy\scrcpy.exe` (hoac them vao `PATH` / set `$env:SCRCPY_PATH`).
4. **Dien thoai Android (Da chuan hoa Galaxy S9 do phan giai `2220x1080`, co Root `su`)**:
   - Bat **Developer Options -> USB Debugging** va cam cap USB, chon *Always allow from this computer*.
   - Kiem tra bang `adb devices` phai hien trang thai `device`.

### Buoc 2: Tao Icon Desktop hien man hinh dien thoai (1 click)
Chay 1 lan duy nhat:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Tao_Icon_Desktop.ps1
```
Hoac nhay dup vao `scripts\Tao_Icon_Desktop.bat`.
- Ngoai Desktop se xuat hien icon **`Man Hinh Dien Thoai CoC`**.
- Bam vao icon nay de mo cua so dien thoai. Script `scripts\Mo_Man_Hinh_CoC.bat` da co **vong lap tu dong ket noi lai** (`adb reconnect` -> mo lai `scrcpy`) neu cap USB hay ADB bi nhay mat ket noi, dong thoi giu man hinh sang (`stayon true`) va them Clash of Clans vao Doze whitelist. (Chi khi bam nut `X` dong cua so voi `exit code 0` thi moi tat han).

### Buoc 3: Kiem thu truoc khi chay
```bash
python -m pytest tests/test_offline_suite.py -v --timeout=30
```
Bat buoc tat ca test phai `PASSED`.

---

## 3. Quy Trinh Van Hanh & Luong Xu Ly Khép Kin

### Luong 1: Vong lap cay + Tu dong nang tuong (`loop_cay_tai_nguyen_doc_lap.py`)
Chay lenh sau o che do chay nen (unbuffered `-u`):
```bash
python -u loop_cay_tai_nguyen_doc_lap.py
```
He thong se tu dong thuc hien tuan tu:
1. **Kiem tra an toan & Pin:** Chay `cet.apply_ultra_battery_saver(keep_awake=True)` (da duoc gioi han tan suat 15 phut/lan, bo `am kill-all` gay lag, xoa loi Bluetooth non-root va ep Doze whitelist cho `com.supercell.clashofclans`).
2. **Dam bao ve dung Lang chinh (`ensure_at_home()`):**
   - Neu man hinh bi lac sang **Lang Tho (Builder Base)**: tu dong bam thuyen (`return_from_builder_base_to_home`) hoac restart app ve Lang chinh.
   - Neu gap bang **Reload game**: tu dong bam Reload va cho vao lai.
3. **Doc kho tai nguyen (`inspect_home_resources()`):** Doc từ `config/upgrade_priority.json`:
   - Hien tai: dung cay khi dong thoi **Vang >= 24,000,000 VA Dau tim >= 24,000,000** (`dark_elixir: 0` da tat).
4. **Phan 1 (`phan1_vao_tran_soi_nha.py`):**
   - Zoom-out -> Bam `Battle (184, 934)` -> Mo quan `(334, 793)` -> Nhan banh Clan Castle `(1738, 848)` -> Xac nhan `(1306, 749)` -> `Attack! (1828, 990)`.
   - Soi tung nha (toi da 60 luot `Next (1950, 720)`). Chi danh khi **Vang >= 1,000,000 VA Dau >= 1,000,000**.
5. **Phan 2 (`phan2_tha_quan_ve_lang.py`):**
   - Thuc thi `BATTLE_COMBO_STEPS` (37 buoc thao tac thuc te qua `/dev/input/event0`, tong ~52.6s).
   - Quet nut `Return Home` moi 1.5s (toi da 145s) -> goi `dismiss_return_home_safely()` de ve Lang chinh an toan.

### Luong 2: Tu dong nang tuong Level 17 -> Max 18 (`wall_upgrade_vision_manager.py`)
Khi kho dat **>= 24,000,000 Vang & >= 24,000,000 Dau tim**:
1. `loop_cay_tai_nguyen_doc_lap.py` goi `importlib.reload(wum)` roi chay `wum.run_wall_upgrade_session(stop_threshold=0)`.
2. Quet toan bo khoi chu nhat **19 hang doc x 16 cot ngang = 304 vien** tu goc `(765, 415)` theo 2 vector:
   - Buoc doc: `dx = +19.89, dy = +11.00`
   - Buoc ngang: `dx = +18.53, dy = -14.20`
3. Doc `runtime/known_level18_walls.json` de **bo qua ngay lap tuc** cac vien da dat Level 18 (khong bam lai mat thoi gian).
4. Cham vien moi:
   - Neu gia bua **>= 8,000,000** (tuc da Level 18, nang len 19 ton 8M) -> ghi ngay vao `runtime/known_level18_walls.json` va chuyen thang sang vien tiep theo.
   - Neu gia bua **<= 6,000,000** (Level 17 -> 18) -> tinh so vien (`min(4, kho // gia)`), bam:
     - `Upgrade More`: `(1052, 842)`
     - `+1 Add Wall`: `(1005, 844)` (lap `max_walls - 1` lan, moi buoc nghi ~1s)
     - `Double Hammer Gold`: `(1214, 844)` hoac `Double Hammer Elixir`: `(1423, 844)`
     - `Okay` (xac nhan): `(1319, 736)`
   - Ghi ngay toan bo cum vua nang vao `runtime/known_level18_walls.json`.
5. Nang sach ca Vang lan Dau xuong `< 6,000,000`, sau do tu tra quyen cho vong lap cay tiep tuc. Neu tai nguyen khong giam sau khi nang, vong lap tu dung an toan de danh thuc AI kiem tra.

---

## 4. Cach Ghi Lai Combo Danh Moi Bang Tay (`scripts/record_combo.py`)

Khi nguoi dung doi doi hinh quan va muon thu lai combo tha quan moi:
1. Dung vong lap cay va dua game ve Lang chinh.
2. Kiem tra ket noi phan cung cam ung khong bo dem:
   ```bash
   python -u scripts/record_combo.py --self-test
   ```
3. Bat ghi khi nguoi dung bao "bat dau" (co the bat `adb shell settings put system show_touches 1`):
   ```bash
   python -u scripts/record_combo.py --record
   ```
   Script doc truc tiep goi nhi phan 24-byte tu `/dev/input/event0` (`0ms` bo dem) va ghi tung cu cham vao `runtime/recorded_taps_<ts>.jsonl`.
4. Khi nguoi dung bao "xong", tat `show_touches 0`, kiem tra file JSONL (bo buoc cuoi neu la nut `Return Home`), luu ban sao vao `assets/user_battle_combo.jsonl` va cap nhat `BATTLE_COMBO_STEPS` trong `phan2_tha_quan_ve_lang.py`.

---

## 5. Xu Ly Loi "Hay Bi Out Ra" (Da Khac Phuc Triet De)

He thong truoc day hay bi vang/out vi 3 nguyen nhan, tat ca da duoc va trong `coc_executor_tools.py` va `scripts/Mo_Man_Hinh_CoC.bat`:
1. **`reconnect_adb()` tung goi `adb kill-server` ngay khi lag nhe:** Lam sap kenh ADB va **vang luon cua so `scrcpy`** tren may tinh. Nay da sua thanh kiem tra `adb get-state` -> thu `adb reconnect` mem truoc; chi `kill-server` khi mat ket noi hoan toan.
2. **Thieu Doze Whitelist & `am kill-all` + loi Bluetooth moi chu ky:** `svc bluetooth disable` chay bang shell khong root gay `FATAL EXCEPTION SecurityException` moi 3 phut, con `am kill-all` lam tai he thong tang vot (`load average ~18`). Nay da chuyen vao `su -c sh`, gian cach `15 phut/lan` (tranh spam moi chu ky), bo `am kill-all` trong loop, va them `dumpsys deviceidle whitelist +com.supercell.clashofclans` + `screen_off_timeout` vo han.
3. **Cua so `scrcpy` khong tu mo lai neu USB nhay:** `scripts/Mo_Man_Hinh_CoC.bat` boc trong vong lap `:RECONNECT_LOOP`, tu dong `adb reconnect` va bat lai man hinh sau 2 giay neu dut ket noi dot ngot.

---

## 6. Quan Ly Cong Trinh / Lab Khi Co Tho Xay Ranh (`upgrade_manager_tools.py`)

Xem them quy trinh chup 6 anh va soi popup an toan:
- Chup trang thai: `python upgrade_manager_tools.py --snapshot --save-crops`
- Quet danh sach: `python upgrade_manager_tools.py --scan-build 5`
- Soi truoc khi bam: `python upgrade_manager_tools.py --inspect-pick scroll_pick_3 --scrolls 1 --inspect-mode build`
- Thuc thi: `python upgrade_manager_tools.py --exec-build scroll_pick_3 --scrolls 1`
- Tinh hen gio ngu: `python upgrade_manager_tools.py --test-wakeup "4H 19M" "5H 20M"`
