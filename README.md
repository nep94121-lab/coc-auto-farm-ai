# CoC Auto Farm & AI Upgrade Manager (2220x1080)

He thong tu dong cay tai nguyen, soi nha Vision/OCR va dieu phoi nang cap Clash of Clans qua ADB tren thiet bi Android (hieu chuan cho Galaxy S9 `2220x1080`).

## 1. Yeu Cau & Ket Noi USB Debugging

### Buoc 1: Bat USB Debugging tren dien thoai Android
1. Vao **Settings -> About phone -> Software information**, bam **Build number** 7 lan de bat **Developer options**.
2. Vao **Settings -> Developer options**, bat:
   - **USB debugging**
   - *(Tuy chon khi do toa do)* **Pointer location** va **Show taps**
3. Cam cap USB vao may tinh, chap nhan hop thoai **Allow USB debugging** tren dien thoai (tick *Always allow from this computer*).
4. *(Doi voi thao tac pinch zoom-out va swipe nhanh qua `/dev/input/event0`)*: thiet bi da root (`su`) de nap `assets/zoom_pinch_fast/` va `assets/swipe_list_fast/` vao `/data/local/tmp/`.

### Buoc 2: Kiem tra ket noi ADB & Bien moi truong
```powershell
adb devices
```
Ket qua phai hien `<serial>    device` (khong phai `unauthorized` hay `offline`).

Neu co nhieu thiet bi hoac `adb` khong nam trong `PATH`:
```powershell
$env:ANDROID_SERIAL = "<serial_cua_ban>"
$env:ADB_PATH = "C:\Path\To\platform-tools\adb.exe"
```
He thong mac dinh tu dong tim `adb` trong `ADB_PATH` -> `PATH` -> Android SDK mac dinh.

### Buoc 3: Cai dat thu vien Python
```bash
pip install -r requirements.txt
```

---

## 2. Cau Truc Du An

```text
coc-auto-farm-ai/
├── config/
│   └── upgrade_priority.json      # Cau hinh uu tien nang cap & nguong dung cay dong
├── assets/
│   ├── coc_digit_templates.npz    # Mau OCR so Clash of Clans
│   ├── coc_battle_gold_icon.png   # Neo nhan dien Gold tran danh
│   ├── coc_battle_elixir_icon.png # Neo nhan dien Elixir tran danh
│   ├── return_home_template.png   # Mau nut Return Home
│   ├── zoom_pinch_fast/           # Tap lenh da cham thu nho camera (26 frames)
│   └── swipe_list_fast/           # Tap lenh vuot danh sach Buildings/Lab (26 frames)
├── tests/
│   └── test_offline_suite.py      # Bo kiem thu offline OCR, toa do, cau hinh & logic
├── coc_vision_grid.py             # Vision & OCR (Gold, Elixir, Dark Elixir, Shifted Bar, Guard)
├── coc_executor_tools.py          # Dieu khien ADB, raw screencap, thao tac cam ung, pin
├── upgrade_manager_tools.py       # Chup 6 anh trang thai, scan trang, soi popup & nang cap
├── phan1_vao_tran_soi_nha.py      # Vao tran va loc nha giàu (>= 1M Gold & Elixir)
├── phan2_tha_quan_ve_lang.py      # Tha quan theo ke hoach va ve Lang chinh an toan
├── loop_cay_tai_nguyen_doc_lap.py # Vong lap cay khép kin theo nguong dong
├── wall_upgrade_vision_manager.py # Nâng tường tự động (Level 16 -> Max 17)
├── coc_mcp_server.py              # MCP Server (JSON-RPC 2.0 stdio) cho AI Agent
├── AGENTS.md                      # Huong dan van hanh chuan danh cho AI Agent
└── README.md
```

---

## 3. Huong Dan Chay Lenh & Vao Game

### Kiem tra & Chup trang thai hien tai (Khong gay tac dong)
```bash
python upgrade_manager_tools.py --snapshot --save-crops
```
Lenh se tu mo game (hoac dam bao dang o Lang chinh co nut `Battle`), chup 6 anh toan man hinh:
- `runtime/upgrade_snapshot/full_1_home.png` (Lang chinh, tho xay `X/6`, Lab `X/2`)
- `runtime/upgrade_snapshot/full_2_build.png` & `full_2b_build_scrolled.png` (Buildings & Heroes truoc/sau vuot)
- `runtime/upgrade_snapshot/full_3_lab.png` & `full_3b_lab_scrolled.png` (Lab truoc/sau vuot)
- `runtime/upgrade_snapshot/full_4_pets.png` (Hero Pets)
- `runtime/upgrade_snapshot/snapshot_manifest.json` (doc san `home_resources`, `shifted_resources`, `priority_config`)

### Quet nhieu trang & Soi Popup truoc khi xac nhan nang cap
```bash
# Quet toi da 5 trang danh sach Buildings & Heroes de tim Archer Tower / Cannon
python upgrade_manager_tools.py --scan-build 5

# Bam chon vi tri scroll_pick_1..8 (sau khi vuot N nhip) NHUNG KHONG xac nhan,
# chup lai popup 'Upgrade <Ten> to Level X?' + thanh mau xanh la + chi phi + thoi gian
python upgrade_manager_tools.py --inspect-pick scroll_pick_3 --scrolls 1 --inspect-mode build
```

### Thuc thi nang cap
```bash
# Nang cong trinh sau khi vuot N nhip (vi du chon scroll_pick_1..8)
python upgrade_manager_tools.py --exec-build scroll_pick_3 --scrolls 1

# Nang nghien cuu trong Lab (co the dung pick_alt_1..3 hoac scroll_pick_1..8 + --scrolls N)
python upgrade_manager_tools.py --exec-research select_item

# Nang thu cung (Hero Pets)
python upgrade_manager_tools.py --exec-pet
```

### Cau hinh uu tiên dong (`config/upgrade_priority.json`) - Khong code cung
Mac dinh trong [config/upgrade_priority.json](config/upgrade_priority.json):
- **6 tho xay** uu tien tap trung **Archer Tower** toi **Max Level 21**, sau do **Cannon** toi **Max Level 21**.
- Nguong dung cay: `Gold >= 23,000,000`, `Elixir >= 23,000,000`, `Dark Elixir >= 300,000`.

Thay doi ngay qua CLI ma khong can sua code:
```bash
python upgrade_manager_tools.py --show-priority
python upgrade_manager_tools.py --set-priority "Archer Tower:21,Cannon:21" --set-builders 6
python upgrade_manager_tools.py --set-thresholds 23000000 23000000 300000
```

### Vong lap cay tai nguyen khép kin
```bash
# Chay vong lap cay chi dung khi dat du 3 nguong (khong tu dong xa tuong)
python -u loop_cay_tai_nguyen_doc_lap.py --no-wall

# Chay vong lap cay ket hop tu dong nang tuong khi kho day
python -u loop_cay_tai_nguyen_doc_lap.py
```

### Tinh thoi gian hen gio thuc day (+3 phut buffer)
```bash
python upgrade_manager_tools.py --test-wakeup "4H 19M" "5H 20M" "10H 57M"
```

---

## 4. Xu Ly Loi Tu Dong & Goi AI Giam Sat Khi Co Su Co

Moi script vong lap va dieu phoi deu co co che tu phuc hoi va ghi tin hieu canh bao ro rang de AI ben ngoai (hoac agent giam sat) phat hien va xu ly:
1. **Lech man hinh / ket popup trong nang cap**: `close_upgrade_panel_to_home` va `capture_upgrade_state_snapshots` tu dong chup man hinh su co vao `runtime/alerts/alert_<ts>.png`, ghi `runtime/upgrade_alert.json`, `am force-stop com.supercell.clashofclans` va khoi dong lai ve Lang chinh.
2. **Loi lien tiep trong vong lap cay (`loop_cay_tai_nguyen_doc_lap.py`)**: Sau 3 lan loi chup man hinh hoac ngoai le lien tiep, he thong luu `runtime/loop_error_alert.json` + anh `runtime/alerts/loop_err_<ts>.png`, dong thoi tu khoi dong lai game ve Lang chinh va ghi log `[ALERT-TO-AI]`.
3. **Bao ve dung o 23M/23M/300k & Chong cat so 24M Elixir**: `coc_vision_grid.py` cat rong khung `x=1905:2138, y=110:152` va dung loc khoang cach chu so tu phai sang trai (`max_x_gap=22`) de doc chinh xac `24,xxx,xxx` khong bi mat chu so `'2'` dau tien thanh `4M`.

---

## 5. Kiem Thu Offline

```bash
python -m pytest tests/test_offline_suite.py -v
```
