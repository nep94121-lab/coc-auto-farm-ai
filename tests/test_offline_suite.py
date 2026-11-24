import json
import os
import py_compile
import sys
import tempfile

import cv2
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import coc_executor_tools as cet
import coc_vision_grid as cvg
import loop_cay_tai_nguyen_doc_lap as loop_mod
import upgrade_manager_tools as umt


def _render_number_on_home_bar(img, value_str, y_top=119, x_right=2123, shifted=False):
    """Vẽ số CoC chuẩn kích thước 2220x1080 dùng bộ template chữ số để test OCR độc lập."""
    if shifted:
        x_right = 1523
    # Vẽ nền tím của thanh Elixir đầy (gồm cả vạch sáng nhẹ ở nửa trên)
    bar_x1 = 1860 if not shifted else 1255
    bar_x2 = 2145 if not shifted else 1555
    img[y_top - 4 : y_top + 27, bar_x1:bar_x2] = (205, 65, 200)
    # Vẽ 8 hoặc 7 chữ số căn phải với khoảng cách thật: 2px nội nhóm, 12px phân tách nghìn
    cur_x_end = x_right
    n = len(value_str)
    for rev_idx, ch in enumerate(reversed(value_str)):
        tpl = cvg.DIGIT_TPLS[ch]
        w_d = 16 if ch == "1" else 20
        h_d = 22
        patch = cv2.resize((tpl > 0.4).astype(np.uint8) * 255, (w_d, h_d), interpolation=cv2.INTER_NEAREST)
        x_start = cur_x_end - w_d
        # Vẽ viền đen mỏng rồi tô trắng tinh chữ số
        img[y_top - 1 : y_top + h_d + 1, x_start - 1 : cur_x_end + 1] = (15, 15, 15)
        ys, xs = np.where(patch > 0)
        img[y_top + ys, x_start + xs] = (255, 255, 255)
        gap = 12 if (rev_idx + 1) % 3 == 0 and rev_idx + 1 < n else 2
        cur_x_end = x_start - gap
    return cur_x_end


def test_elixir_ocr_24m_and_2m_no_clipping_and_noise_rejection():
    for digits_str, expected in [("24500000", 24500000), ("24888888", 24888888), ("2479734", 2479734)]:
        canvas = np.zeros((1080, 2220, 3), dtype=np.uint8)
        canvas[:, :] = (40, 120, 40)
        # Đặt một mảng nhiễu trắng ở rìa trái ngoài số (cách > 28px) để thử chống cộng nhầm số lạ
        canvas[119:141, 1898:1910] = (255, 255, 255)
        _render_number_on_home_bar(canvas, digits_str, y_top=119, x_right=2123, shifted=False)
        _render_number_on_home_bar(canvas, "24500000", y_top=45, x_right=2123, shifted=False)
        _render_number_on_home_bar(canvas, "306612", y_top=185, x_right=2123, shifted=False)

        gold, elixir, de = cvg.read_all_home_resources(canvas)
        assert gold == 24500000
        assert elixir == expected, f"Expected {expected}, got {elixir}"
        assert de == 306612


def test_shifted_elixir_ocr_24m():
    canvas = np.zeros((1080, 2220, 3), dtype=np.uint8)
    _render_number_on_home_bar(canvas, "24950000", y_top=119, shifted=True)
    _render_number_on_home_bar(canvas, "24259736", y_top=45, shifted=True)
    _render_number_on_home_bar(canvas, "306612", y_top=185, shifted=True)
    g, e, de = cvg.read_shifted_resources(canvas)
    assert g == 24259736
    assert e == 24950000
    assert de == 306612


def test_scroll_pick_coordinates_and_bounds():
    expected = {
        "scroll_pick_1": (1868, 137),
        "scroll_pick_2": (1728, 236),
        "scroll_pick_3": (1894, 333),
        "scroll_pick_4": (1839, 445),
        "scroll_pick_5": (1816, 528),
        "scroll_pick_6": (1780, 644),
        "scroll_pick_7": (1775, 722),
        "scroll_pick_8": (1797, 836),
    }
    assert umt.SCROLL_LIST_PICK_POSITIONS == expected
    for k, (x, y) in expected.items():
        assert umt.COORDS_BUILD[k] == (x, y)
        assert umt.COORDS_RESEARCH[k] == (x, y)
        assert 1616 <= x <= 2219
        assert 72 <= y <= 920


def test_dynamic_priority_config_and_thresholds():
    cfg = umt.load_upgrade_priority_config()
    bf = cfg["builder_focus"]
    assert bf["target_builders"] == 6
    names = [(t["name"], t["max_level"]) for t in bf["priority_targets"]]
    assert names[0] == ("Archer Tower", 21)
    assert names[1] == ("Cannon", 21)

    parsed = umt.parse_priority_spec("Cannon:21, X-Bow:11")
    assert parsed == [{"name": "Cannon", "max_level": 21}, {"name": "X-Bow", "max_level": 11}]

    with tempfile.TemporaryDirectory() as td:
        tmp_cfg = os.path.join(td, "priority.json")
        custom = json.loads(json.dumps(cfg))
        custom["resource_stop_thresholds"]["gold"] = 18000000
        custom["resource_stop_thresholds"]["elixir"] = 19000000
        custom["resource_stop_thresholds"]["dark_elixir"] = 250000
        umt.save_upgrade_priority_config(custom, config_path=tmp_cfg)

        old_env = os.environ.get("COC_PRIORITY_CONFIG")
        try:
            os.environ["COC_PRIORITY_CONFIG"] = tmp_cfg
            umt.DEFAULT_PRIORITY_CONFIG_PATH = tmp_cfg
            g_th, e_th, de_th, _ = loop_mod.load_dynamic_thresholds()
            assert (g_th, e_th, de_th) == (18000000, 19000000, 250000)
            assert loop_mod.all_three_thresholds_reached(18000000, 19000000, 250000, g_th, de_th, elixir_threshold=e_th)
            assert not loop_mod.all_three_thresholds_reached(18000000, 18999999, 250000, g_th, de_th, elixir_threshold=e_th)
        finally:
            if old_env is None:
                os.environ.pop("COC_PRIORITY_CONFIG", None)
            else:
                os.environ["COC_PRIORITY_CONFIG"] = old_env
            umt.DEFAULT_PRIORITY_CONFIG_PATH = os.path.join(REPO_ROOT, "config", "upgrade_priority.json")


def test_wakeup_duration_math():
    assert umt.parse_coc_duration_seconds("4H 19M") == 4 * 3600 + 19 * 60
    assert umt.parse_coc_duration_seconds("1d 9H") == 86400 + 9 * 3600
    assert umt.parse_coc_duration_seconds("2:35") == 2 * 3600 + 35 * 60
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "wakeup.json")
        plan = umt.compute_safe_wakeup(["4H 19M", "5H 20M", "10H 57M"], buffer_minutes=3, save_path=out)
        assert plan["min_timer_sec"] == 4 * 3600 + 19 * 60
        assert plan["wait_total_sec"] == 4 * 3600 + 22 * 60
        assert os.path.exists(out)


def test_builder_base_guard_blocks_false_home_village():
    # Làng Thợ giả lập: nút Battle vàng góc trái dưới + hộp sao trắng phía trên + nút '+' Gem xanh có dấu '+' trắng
    bb_img = np.zeros((1080, 2220, 3), dtype=np.uint8)
    bb_img[900:1030, 40:180] = (20, 180, 240)
    bb_img[810:855, 45:165] = (240, 240, 240)
    bb_img[175:215, 1860:1905] = (40, 210, 80)
    bb_img[185:205, 1875:1895] = (255, 255, 255)
    assert cvg.is_builder_base(bb_img) is True
    assert cvg.is_battle_button_visible(bb_img) is False

    # Làng chính giả lập: nút Battle vàng góc trái dưới, KHÔNG có '+' Gem ở y=165..225 hay hộp sao trắng
    home_img = np.zeros((1080, 2220, 3), dtype=np.uint8)
    home_img[900:1030, 40:180] = (20, 180, 240)
    assert cvg.is_builder_base(home_img) is False
    assert cvg.is_battle_button_visible(home_img) is True


def test_partially_dimmed_right_digits_ocr():
    """Hồi quy trường hợp toast/bóng mờ làm tối nửa phải thanh Elixir/DE (21536869 -> không bị rớt thành 215368)."""
    canvas = np.zeros((1080, 2220, 3), dtype=np.uint8)
    _render_number_on_home_bar(canvas, "21536869", y_top=119, x_right=2123, shifted=False)
    _render_number_on_home_bar(canvas, "293628", y_top=185, x_right=2123, shifted=False)
    # Làm tối nửa phải từ x=2072 về sau giống bóng overlay (giảm độ sáng còn ~65%)
    canvas[:, 2072:2150] = (canvas[:, 2072:2150].astype(np.float32) * 0.65).astype(np.uint8)
    _, elixir, de = cvg.read_all_home_resources(canvas)
    assert elixir == 21536869, f"Expected 21536869, got {elixir}"
    assert de == 293628, f"Expected 293628, got {de}"


def test_repo_portability_syntax_and_lf_encoding():
    assert cet._resolve_adb_path()
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache", "runtime")]
        for fn in files:
            path = os.path.join(root, fn)
            if fn.endswith(".py"):
                py_compile.compile(path, doraise=True)
            if fn.endswith((".py", ".md", ".json", ".txt", ".sh")):
                raw = open(path, "rb").read()
                assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM found in {path}"
                assert b"\r\n" not in raw, f"CRLF found in {path}"
            if fn.endswith(".py") and root == REPO_ROOT:
                txt = open(path, "r", encoding="utf-8").read()
                assert "504cdb97" not in txt, f"Hardcoded session id in {path}"
                assert "C:\\Users\\LENOVO" not in txt, f"Hardcoded user path in {path}"


def test_battle_combo_matches_recorded_jsonl():
    import phan2_tha_quan_ve_lang as p2

    combo_file = os.path.join(REPO_ROOT, "assets", "user_battle_combo.jsonl")
    assert os.path.exists(combo_file)
    records = [json.loads(line) for line in open(combo_file, "r", encoding="utf-8") if line.strip()]
    assert len(p2.BATTLE_COMBO_STEPS) == 37
    assert len(records) >= 37
    for delay_sec, x, y, hold_sec in p2.BATTLE_COMBO_STEPS:
        assert 0 <= x < 2220
        assert 0 <= y < 1080
        assert delay_sec >= 0.0
        assert hold_sec >= 0.045


def test_wall_grid_and_known_l18_skip(monkeypatch):
    import tempfile
    import wall_upgrade_vision_manager as wum

    all_cands = wum.generate_wall_grid_candidates()
    assert len(all_cands) == 19 * 16

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(wum, "KNOWN_L18_FILE", os.path.join(tmpdir, "known_level18_walls_v2.json"))
        known = wum.load_known_l18_coords()
        assert known == set()
        wum.save_known_l18_coords({(765, 415), (900, 500)})
        reloaded = wum.load_known_l18_coords()
        assert (765, 415) in reloaded
        assert len(reloaded) == 2


def test_calibrated_coords_and_triple_modal_helpers(monkeypatch):
    assert umt.COORDS_PET["pet_assigned_1"] == (1900, 180)
    assert umt.COORDS_PET["pet_assigned_2"] == (1900, 280)
    assert umt.COORDS_NAV["bb_boat_dock"] == (1770, 465)
    assert umt.COORDS_NAV["return_home_button"] == (118, 910)

    # Tạo ảnh danh sách giả lập 2220x1080 với mẫu duy nhất không trùng lặp để kiểm tra triple-match
    rng = np.random.default_rng(42)
    page = rng.integers(20, 230, size=(1080, 2220, 3), dtype=np.uint8)
    rx1, rx2 = umt.VISION_BOXES["row_card_x"]
    bx1, bx2 = umt.VISION_BOXES["row_badge_x"]
    cx1, cx2 = umt.VISION_BOXES["row_cost_x"]

    card_tmpl = page[400:465, rx1:rx2].copy()
    badge_tmpl = page[400:465, bx1:bx2].copy()
    cost_tmpl = page[400:465, cx1:cx2].copy()

    hit = umt.match_upgrade_row_triple(page, card_tmpl, badge_tmpl, cost_tmpl)
    assert hit["matched"] is True
    assert hit["aligned"] is True
    assert hit["y_row"] == 400
    assert hit["tap_point"] == [(rx1 + rx2) // 2, 432]

    # Lệch hàng (badge khác vị trí -> phải bị từ chối vì không đồng trục)
    bad_badge = page[700:765, bx1:bx2].copy()
    miss = umt.match_upgrade_row_triple(page, card_tmpl, bad_badge, cost_tmpl)
    assert miss["matched"] is False
    assert miss["aligned"] is False

    # Kiểm tra verify_modal_title_and_confirm nhận diện tiêu đề + nút xanh
    modal = rng.integers(20, 120, size=(1080, 2220, 3), dtype=np.uint8)
    tx1, ty1, tx2, ty2 = umt.VISION_BOXES["modal_title_canon"]
    title_tmpl = modal[ty1:ty2, tx1:tx2].copy()
    modal[880:950, 1200:1360] = (30, 190, 60)  # BGR green confirm button

    monkeypatch.setattr(umt.cet, "capture_screen", lambda: modal)
    res_ok = umt.verify_modal_title_and_confirm(title_tmpl, settle_sec=0)
    assert res_ok["ok"] is True
    assert res_ok["title_score"] >= 0.99

    # Tiêu đề sai (nhầm công trình) phải trả ok=False
    wrong_tmpl = rng.integers(0, 255, size=title_tmpl.shape, dtype=np.uint8)
    res_bad = umt.verify_modal_title_and_confirm(wrong_tmpl, settle_sec=0)
    assert res_bad["ok"] is False


def test_continuous_farm_no_stop_ignores_full_storages(monkeypatch):
    import json
    import tempfile
    import loop_cay_tai_nguyen_doc_lap as lct

    with tempfile.TemporaryDirectory() as tmpdir:
        status_path = os.path.join(tmpdir, "loop_farm_status.json")
        monkeypatch.setattr(lct, "STATUS_JSON", status_path)
        monkeypatch.setattr(lct, "confirm_home_threshold_reached", lambda g, e, de, g_th, de_th: (True, g, e, de))

        # Có điểm dừng (mặc định) -> dừng khi đạt 24.5M / 24.5M / 320k
        d_stop = lct.handle_home_resource_decision(
            24_500_000, 24_500_000, 320_000, cycle=1, phase_label="TEST", auto_upgrade_walls=False, no_stop=False
        )
        assert d_stop == "STOP_FARM_ONLY"

        # Chế độ liên tục (--no-stop) -> bỏ qua điểm dừng dù kho đầy tràn
        d_cont = lct.handle_home_resource_decision(
            24_500_000, 24_500_000, 320_000, cycle=2, phase_label="TEST", auto_upgrade_walls=False, no_stop=True
        )
        assert d_cont == "CONTINUE_FARM"
        with open(status_path, "r", encoding="utf-8") as f:
            st = json.load(f)
        assert st["phase"] == "farming_continuous"
        assert st["no_stop"] is True


def test_inactivity_reload_dialog_detection():
    img = np.zeros((1080, 2220, 3), dtype=np.uint8)
    # Khung hộp thoại Material xám tối (66, 66, 66) & chữ 'RELOAD GAME' màu teal
    img[415:660, 645:1575] = (66, 66, 66)
    img[605:630, 665:815] = (140, 145, 70)
    assert cvg.is_inactivity_reload_dialog(img) is True
    assert cvg.is_reload_game_dialog(img) is True
    # Không phải hộp thoại nếu màn hình Làng chính sáng bình thường
    normal = np.full((1080, 2220, 3), 180, dtype=np.uint8)
    assert cvg.is_inactivity_reload_dialog(normal) is False


def test_ensure_emulator_running_relaunch_bs5(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(umt.sys, "platform", "win32")
    monkeypatch.setattr(umt.time, "sleep", lambda _s: None)

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[0] == "tasklist":
            return SimpleNamespace(stdout="INFO: No tasks are running.", returncode=0)
        if cmd[0] == "schtasks":
            return SimpleNamespace(stdout="SUCCESS", returncode=0)
        if len(cmd) >= 2 and cmd[1] == "devices":
            return SimpleNamespace(stdout="List of devices attached\n127.0.0.1:5555\tdevice\n", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert umt.ensure_emulator_running_and_adb(wait_sec=5) is True
    assert any(c[:3] == ["schtasks", "/run", "/tn"] and c[3] == "BS5Launch" for c in calls)


def test_reconnect_adb_relaunches_bs5_when_emulator_missing(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    calls = []
    monkeypatch.setattr(cet.sys, "platform", "win32")
    monkeypatch.setattr(cet.time, "sleep", lambda _s: None)
    monkeypatch.setattr(cet, "SERIAL", "127.0.0.1:5555")

    bs5_started = {"flag": False}

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[0] == "tasklist":
            return SimpleNamespace(stdout="INFO: No tasks are running.", returncode=0)
        if cmd[0] == "schtasks":
            bs5_started["flag"] = True
            return SimpleNamespace(stdout="SUCCESS", returncode=0)
        if "get-state" in cmd:
            return SimpleNamespace(stdout="device\n" if bs5_started["flag"] else "", returncode=0 if bs5_started["flag"] else 1)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    cet.reconnect_adb()
    assert bs5_started["flag"] is True
    assert any(c[:3] == ["schtasks", "/run", "/tn"] and c[3] == "BS5Launch" for c in calls)

