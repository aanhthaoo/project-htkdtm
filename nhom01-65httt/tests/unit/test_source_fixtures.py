"""Kiểm tra các phản hồi mẫu và ngưỡng chất lượng chốt ở N2 (không cần mạng).

Các test này ghi lại những điều đã quan sát ở nguồn (đơn vị, định dạng ngày, tên trường);
nếu nguồn đổi và fixture được chụp lại, test sẽ báo ngay chỗ lệch.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def load(rel: str):
    return json.loads((FIXTURES / rel).read_text(encoding="utf-8"))


def cafef_rows(rel: str) -> list[dict]:
    inner = load(rel)["Data"]["Data"]
    return inner["ListDataTudoanh"] if isinstance(inner, dict) else inner


# ---------- CafeF ----------


def test_ngay_trong_phan_hoi_la_dd_mm_yyyy():
    for rel in (
        "cafef/price_VNM_2024-01.json",
        "cafef/foreign_VNM_2024-01.json",
        "cafef/prop_VNM_2024-01.json",
    ):
        for row in cafef_rows(rel):
            raw = row.get("Ngay") or row.get("Date")
            parsed = datetime.strptime(raw, "%d/%m/%Y")
            assert parsed.year == 2024 and parsed.month == 1


def test_gia_tinh_bang_nghin_dong_va_gia_tri_bang_ty():
    row = cafef_rows("cafef/price_VNM_2024-01.json")[0]
    # VNM khoảng 55-75 nghìn đồng/cổ phiếu: nếu là đồng thì số sẽ lớn hơn 1000
    assert 10 < row["GiaDongCua"] < 200
    # Giá trị khớp lệnh gần bằng khối lượng x giá (đơn vị tỷ đồng)
    ty = row["KhoiLuongKhopLenh"] * row["GiaDongCua"] * 1000 / 1e9
    assert ty == pytest.approx(row["GiaTriKhopLenh"], rel=0.05)


def test_khoi_ngoai_va_tu_doanh_tinh_bang_dong():
    foreign = cafef_rows("cafef/foreign_VNM_2024-01.json")[0]
    assert abs(foreign["GtMua"]) > 1e6  # đồng, không phải tỷ
    assert foreign["GTDGRong"] == pytest.approx(foreign["GtMua"] - foreign["GtBan"], abs=1)
    assert foreign["KLGDRong"] == foreign["KLMua"] - foreign["KLBan"]

    prop = cafef_rows("cafef/prop_VNM_2024-01.json")[0]
    assert prop["GtMua"] > 1e6
    # Tên trường tự doanh viết hoa không đồng nhất (KLcpMua / KlcpBan) - nhớ khi nạp
    assert "KLcpMua" in prop and "KlcpBan" in prop
    assert "GTDGRong" not in prop  # tự doanh không có cột ròng, phải tự tính


def test_chi_so_vnindex_co_trong_endpoint_gia():
    rows = cafef_rows("cafef/price_VNINDEX_2024-01.json")
    assert rows and rows[0]["Symbol"] == "VNINDEX"
    assert rows[0]["GiaDongCua"] > 500


def test_pagesize_toi_da_30():
    assert len(cafef_rows("cafef/price_VNM_2024-01.json")) <= 30


# ---------- Vietcap ----------


def test_vietcap_co_san_va_nganh_icb_cap_2():
    stocks = load("vietcap/symbols_getAll_sample.json")
    assert stocks
    for s in stocks:
        assert s["type"] == "STOCK"
        assert s["board"] in ("HSX", "HNX", "UPCOM")
        # icbCode2 là mã siêu ngành 4 chữ số (hoặc rỗng với một số mã)
        assert s["icbCode2"] is None or (len(s["icbCode2"]) == 4 and s["icbCode2"].isdigit())


def test_nhom_vn30_la_danh_sach_ma():
    vn30 = load("vietcap/vn30_group.json")
    symbols = {x["symbol"] for x in vn30}
    assert {"VCB", "HPG", "FPT"} <= symbols
    assert 25 <= len(symbols) <= 35


# ---------- RSS ----------


@pytest.mark.parametrize("name", ["vneconomy", "vietstock", "vnexpress"])
def test_rss_co_cac_truong_can_dung(name):
    items = load(f"rss/{name}_sample.json")
    assert items
    for item in items:
        assert item["title"] and item["link"].startswith("http") and item["published"]


def test_vneconomy_dung_mui_gio_gmt_con_cac_nguon_khac_dung_07():
    assert load("rss/vneconomy_sample.json")[0]["published"].endswith("GMT")
    assert load("rss/vietstock_sample.json")[0]["published"].endswith("+0700")
    assert load("rss/vnexpress_sample.json")[0]["published"].endswith("+0700")


# ---------- Ngưỡng chất lượng ----------


def test_nguong_chat_luong_hop_le():
    cfg = yaml.safe_load(
        (ROOT / "src" / "etl" / "config" / "quality_thresholds.yml").read_text("utf-8")
    )
    assert cfg["timezone"] == "Asia/Ho_Chi_Minh"
    assert cfg["units"]["money"] == "ty_vnd"
    assert 0 < cfg["completeness"]["max_missing_price_rate"] < 0.05
    assert 0 < cfg["money_flow"]["max_other_negative_rate"] <= 0.05
    cc = cfg["cross_check"]
    assert cc["abs_tolerance_bn"] > 0 and 0 < cc["rel_tolerance"] < 0.2
    assert cfg["sentiment"]["min_cohen_kappa"] >= 0.4
    # Khối ngoại đủ từ 09/2020 (VNDirect); tự doanh theo mã chỉ từ 17/05/2022 (kết luận N2)
    assert cfg["coverage"]["money_flow_history_start"] == "2020-09-01"
    assert cfg["coverage"]["prop_history_start"] == "2022-05-17"
    assert cfg["latest_day"]["refetch_window_days"] >= 3


# ---------- VNDirect (nguồn chính cho giá, khối ngoại, tự doanh) ----------


def vnd(rel: str) -> list[dict]:
    return load(rel)["data"]


def test_vndirect_tinh_ca_thoa_thuan_con_cafef_chi_khop_lenh():
    """Phát hiện N2: khối ngoại của VNDirect gồm cả giao dịch thỏa thuận, CafeF chỉ khớp lệnh.

    Ngày không có thỏa thuận thì hai nguồn khớp nhau (sai khác nhỏ do lô lẻ). Ngày có thỏa thuận,
    mỗi chiều (mua hoặc bán) VNDirect lớn hơn CafeF một lượng không vượt giá trị thỏa thuận.
    """
    cafef = {r["Ngay"]: r for r in cafef_rows("cafef/foreign_VNM_2024-01.json")}
    price = {r["Ngay"]: r for r in cafef_rows("cafef/price_VNM_2024-01.json")}
    ndirect = {r["tradingDate"]: r for r in vnd("vndirect/foreign_VNM_2024-01.json")}
    seen_with_pt = seen_without_pt = 0
    for ngay, c in cafef.items():
        dd, mm, yy = ngay.split("/")
        v = ndirect[f"{yy}-{mm}-{dd}"]
        pt_vnd = price[ngay]["GtThoaThuan"] * 1e9  # tỷ -> đồng
        diff_buy, diff_sell = v["buyVal"] - c["GtMua"], v["sellVal"] - c["GtBan"]
        if pt_vnd == 0:
            assert v["buyVal"] == pytest.approx(c["GtMua"], rel=1e-3)
            assert v["sellVal"] == pytest.approx(c["GtBan"], rel=1e-3)
            seen_without_pt += 1
        else:
            assert -1e7 <= diff_buy <= pt_vnd * 1.001
            assert -1e7 <= diff_sell <= pt_vnd * 1.001
            seen_with_pt += 1
    assert seen_with_pt >= 1 and seen_without_pt >= 1


def test_vndirect_tu_doanh_khop_cafef_va_co_cot_rong():
    cafef = {r["Date"]: r for r in cafef_rows("cafef/prop_VNM_2024-01.json")}
    ndirect = {r["date"]: r for r in vnd("vndirect/prop_VNM_2024-01.json")}
    checked = 0
    for ngay, row in cafef.items():
        dd, mm, yy = ngay.split("/")
        v = ndirect.get(f"{yy}-{mm}-{dd}")
        if not v:
            continue
        assert v["buyingVal"] == pytest.approx(row["GtMua"])
        assert v["sellingVal"] == pytest.approx(row["GtBan"])
        assert v["netVal"] == pytest.approx(v["buyingVal"] - v["sellingVal"])  # có sẵn cột ròng
        checked += 1
    assert checked >= 1


def test_vndirect_gia_don_vi_va_truong_dieu_chinh():
    rows = vnd("vndirect/price_VNM_2024-01.json")
    assert rows == sorted(rows, key=lambda r: r["date"])  # yêu cầu sort asc
    row = rows[-1]
    assert row["code"] == "VNM" and row["floor"] == "HOSE"
    assert 10 < row["close"] < 200  # nghìn đồng
    assert row["nmValue"] > 1e6  # giá trị khớp lệnh tính bằng đồng
    assert {"adClose", "ptValue", "ptVolume", "ceilingPrice", "floorPrice"} <= set(row)


def test_vietcap_company_co_icb_cap_4_va_von_hoa():
    info = load("vietcap/company_VNM_sample.json")
    assert info["icbCodeLv2"] == "3500" and info["icbCodeLv4"] == "3577"
    # Mã cấp 4 phải thuộc đúng siêu ngành cấp 2: hai chữ số đầu trùng nhau
    assert info["icbCodeLv4"][:2] == info["icbCodeLv2"][:2]
    # Vốn hóa = giá x số cổ phiếu, khoảng vài trăm nghìn tỷ đồng
    assert info["marketCap"] > 1e12 and info["issueShare"] > 1e8


def test_tnck_rss_co_gio_dang_mui_gio_07():
    items = load("rss/tnck_sample.json")
    assert items and "+07:00" in items[0]["published"]
