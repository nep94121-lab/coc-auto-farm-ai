# CoC Auto Farm & AI Upgrade Manager (2220x1080)

He thong tu dong cay tai nguyen, soi nha Vision/OCR, danh theo combo ghi truc tiep tu tay nguoi dung, tu dong nang tuong Level 17 -> Level 18 va dieu phoi nang cap Clash of Clans qua ADB tren Android (hieu chuan cho Galaxy S9 `2220x1080`).

> **Danh cho AI Agent moi:** Doc file [AGENTS.md](AGENTS.md) ngay sau khi clone de nam toan bo ban do file, quy trinh van hanh tung buoc, toa do chuan, cach ghi lai combo danh va cach xu ly su co.

---

## 1. Cai Dat Tu Dau (Tren May Moi)

### Buoc 1: Cai dat Python, ADB & scrcpy
1. Cai thu vien Python:
   ```bash
   pip install -r requirements.txt
   ```
2. Cai **Android Platform Tools** (`adb.exe`) vao PATH hoac `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` (hoac set `$env:ADB_PATH`).
3. Cai **scrcpy** (`https://github.com/Genymobile/scrcpy/releases`) vao `%LOCALAPPDATA%\scrcpy\scrcpy.exe` (hoac them vao PATH / set `$env:SCRCPY_PATH`).

### Buoc 2: Ket noi dien thoai Android qua USB Debugging
1. Bat **Settings -> About phone -> Software information -> bam Build number 7 lan** de mo **Developer options**.
2. Bat **USB debugging**, cam cap USB va chap nhan *Always allow from this computer*.
3. Kiem tra ket noi:
   ```powershell
   adb devices
   ```
   Phai hien `<serial>    device`. (Thiet bi da root `su` ho tro ghi/phat `/dev/input/event0` toc do cao).

### Buoc 3: Tao Icon Desktop hien man hinh dien thoai (1 click)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\Tao_Icon_Desktop.ps1
```
Hoac nhay dup file [scripts/Tao_Icon_Desktop.bat](scripts/Tao_Icon_Desktop.bat).
- Ngoai Desktop se co ngay shortcut **`Man Hinh Dien Thoai CoC`**.
- Bam vao icon de mo cua so dien thoai (`scripts/Mo_Man_Hinh_CoC.bat`), tich hop san **vong lap tu ket noi lai (`adb reconnect` + mo lai `scrcpy`)** neu USB/ADB bi lag hoac mat ket noi tam thoi, dong thoi giu man hinh sang va dua Clash of Clans vao whitelist chong ngu Doze.

---

## 2. Cau Truc Du An

```text
coc-auto-farm-ai/
├── AGENTS.md                        # Cam nang van hanh chi tiet danh cho AI Agent moi
├── README.md                        # Tai lieu nay
├── config/
│   └── upgrade_priority.json        # Cau hinh uu tien nang cap & nguong dung cay (24M/24M)
├── assets/
│   ├── user_battle_combo.jsonl      # Ban ghi goc 37 buoc tha quan/tuong/phep cua nguoi dung
│   ├── coc_digit_templates.npz    # Mau OCR so Clash of Clans
│   ├── coc_battle_gold_icon.png
│   ├── coc_battle_elixir_icon.png
│   ├── return_home_template.png
│   ├── zoom_pinch_fast/             # Tap lenh da cham thu nho camera (26 frames)
│   └── swipe_list_fast/           # Tap lenh vuot danh sach Buildings/Lab (26 frames)
├── scripts/
│   ├── Mo_Man_Hinh_CoC.bat          # Mo scrcpy co tu dong reconnect chong out man hinh
│   ├── Tao_Icon_Desktop.ps1         # Script tao icon ngoai Desktop
│   ├── Tao_Icon_Desktop.bat         # Wrapper 1-click cho Tao_Icon_Desktop.ps1
│   └── record_combo.py              # Tool ghi/phat lai thao tac cham phan cung (/dev/input/event0)
├── runtime/
│   └── known_level18_walls.json     # Danh sach toa do cac vien tuong da dat Level 18
├── tests/
│   └── test_offline_suite.py        # Bo kiem thu offline OCR, toa do, combo, luoi tuong & ma nguon
├── loop_cay_tai_nguyen_doc_lap.py   # Vong lap cay khép kin <-> Tu dong nang tuong
├── phan1_vao_tran_soi_nha.py        # Vao tran va loc nha giau (>= 1M Gold & >= 1M Elixir)
├── phan2_tha_quan_ve_lang.py        # Thuc thi 37 thao tac danh & ve Lang chinh an toan
├── wall_upgrade_vision_manager.py   # Nang tuong Level 17 -> Max 18 tren ma tran 19x16 (304 vien)
├── upgrade_manager_tools.py         # Snapshot 6 anh, scan nha/Lab/Pets & nang cap cong trinh
├── coc_vision_grid.py               # Vision & OCR (Gold, Elixir, Dark Elixir, Shifted Bar, Guard)
├── coc_executor_tools.py            # ADB, raw screencap, /dev/input/event0, pin & chong out
└── coc_mcp_server.py                # MCP Server (JSON-RPC 2.0 stdio) cho AI Agent
```

---

## 3. Huong Dan Chay Nhanh

### Kiem thu offline truoc khi chay
```bash
python -m pytest tests/test_offline_suite.py -v --timeout=30
```

### Chay vong lap cay + Tu dong nang tuong (khuyen dung)
```bash
python -u loop_cay_tai_nguyen_doc_lap.py
```
- **Dieu kien danh tran:** Vang >= `1,000,000` VA Dau tim >= `1,000,000`.
- **Nguong goi nang tuong:** Vang >= `24,000,000` VA Dau tim >= `24,000,000` (bo dieu kien Dau den).
- **Nang tuong thong minh:** Quet ma tran `19 x 16 = 304` vien, bo qua tat ca cac vien da co trong `runtime/known_level18_walls.json`, tu dong bo qua va luu lai bat ky vien nao co gia `>= 8,000,000` (da Level 18), nang cum toi da 4 vien/nha (`6M/vien`) bang ca Vang va Dau xuong `< 6,000,000` roi quay ve cay tiep.

### Ghi lai combo danh moi (khi doi quan/tuong)
```bash
# Kiem tra doc cam ung phan cung khong bo dem
python -u scripts/record_combo.py --self-test

# Bat ghi thao tac tay nguoi dung ra runtime/recorded_taps_*.jsonl
python -u scripts/record_combo.py --record

# Phat lai thu 1 file da ghi
python -u scripts/record_combo.py --replay runtime/recorded_taps_YYYYMMDD_HHMMSS.jsonl
```

### Chay dieu phoi nang cap cong trinh / Lab
```bash
python upgrade_manager_tools.py --show-priority
python upgrade_manager_tools.py --snapshot --save-crops
python upgrade_manager_tools.py --scan-build 5
python upgrade_manager_tools.py --inspect-pick scroll_pick_3 --scrolls 1 --inspect-mode build
python upgrade_manager_tools.py --exec-build scroll_pick_3 --scrolls 1
```

---

## 4. Chong Vang / Chong Out & Tu Phuc Hoi

1. **Khong kill ADB Server bua bai (`coc_executor_tools.py`):** `reconnect_adb()` thu `adb get-state` va `adb reconnect` mem truoc, tranh lam tat dot ngot cua so `scrcpy` tren may tinh.
2. **Chong ngu Doze & giam tai CPU (`apply_ultra_battery_saver`):** Whitelist `com.supercell.clashofclans` trong `deviceidle` + `appops`, xoa loi `svc bluetooth disable` non-root, bo `am kill-all` spam moi chu ky va gian tan suat chay nang 15 phut/lan.
3. **Tu dong ve Lang chinh (`ensure_at_home`):** Tu xu ly khi lac sang Lang Tho (`Builder Base`), gap hop thoai `Reload game`, hoac ket tran, va luu canh bao vao `runtime/loop_error_alert.json` + `runtime/alerts/` de AI giam sat xu ly.
