"""Kiểm thử bộ nạp CSV nhập tay (không cần cơ sở dữ liệu): tệp mẫu, kiểm tra từng quy tắc, chống nhìn trước tương lai."""

from datetime import date
from pathlib import Path

import pytest

from ingestion import manual_csv as mc

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "ingestion" / "templates"
TODAY = date(2026, 11, 27)

MACRO_HEADER = "period_end,indicator_code,value,unit,source,published_date,note\n"
INDIVIDUAL_HEADER = "week_start_date,buy_value_bn,sell_value_bn,source,note\n"
ETF_HEADER = "month_start_date,etf_name,net_flow_bn,source,note\n"


def write(tmp_path, text):
    path = tmp_path / "x.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_tep_mau_hop_le_nhung_bi_tu_choi_vi_la_du_lieu_mau():
    for kind, name in (
        ("macro", "macro_monthly.csv"),
        ("individual", "individual_investors_weekly.csv"),
        ("etf", "etf_flows_monthly.csv"),
    ):
        refused = mc.parse_file(kind, TEMPLATES / name, today=TODAY)
        assert refused.errors and refused.rejected_samples > 0 and not refused.rows
        assert all("dữ liệu mẫu" in e for e in refused.errors)
        allowed = mc.parse_file(kind, TEMPLATES / name, allow_sample=True, today=TODAY)
        assert not allowed.errors and allowed.rows, f"{name} phải hợp lệ khi cho phép dữ liệu mẫu"


def test_vi_mo_hop_le_va_ghi_dung_kieu():
    f = write(
        tmp := Path(__import__("tempfile").mkdtemp()),
        MACRO_HEADER
        + "2026-09-30,CPI_YOY,3.4,%,TCTK,2026-10-06,\n2026-09-30,EXPORT_USD_BN,36.2,tỷ USD,TCTK,2026-10-06,\n",
    )
    assert tmp
    r = mc.parse_file("macro", f, today=TODAY)
    assert not r.errors and len(r.rows) == 2
    period_end, code, value, unit, source, published, note = r.rows[0]
    assert (period_end, code, value, unit, published) == (
        date(2026, 9, 30),
        "CPI_YOY",
        3.4,
        "%",
        date(2026, 10, 6),
    )


@pytest.mark.parametrize(
    "line,fragment",
    [
        ("2026-09-15,CPI_YOY,3.4,%,TCTK,2026-10-06,", "cuối tháng"),
        ("2026-09-30,GDP,3.4,%,TCTK,2026-10-06,", "không hợp lệ"),
        ("2026-09-30,CPI_YOY,abc,%,TCTK,2026-10-06,", "không phải số"),
        (
            "2026-09-30,CPI_YOY,3.4,%,TCTK,2026-09-20,",
            "sớm hơn cuối kỳ",
        ),  # công bố trước khi kỳ kết thúc: nhìn trước tương lai
        ("2026-12-31,CPI_YOY,3.4,%,TCTK,2027-01-05,", "chưa kết thúc"),
        ("2026-09-30,CPI_YOY,3.4,%,TCTK,2026-12-30,", "tương lai"),
        ("30/09/2026,CPI_YOY,3.4,%,TCTK,2026-10-06,", "YYYY-MM-DD"),
    ],
)
def test_vi_mo_loai_dong_sai_va_bao_ly_do(tmp_path, line, fragment):
    r = mc.parse_file("macro", write(tmp_path, MACRO_HEADER + line + "\n"), today=TODAY)
    assert not r.rows and any(fragment in e for e in r.errors), r.errors


def test_thieu_cot_bat_buoc_va_trung_khoa_va_tep_rong(tmp_path):
    r = mc.parse_file("macro", write(tmp_path, "period_end,value\n2026-09-30,3\n"), today=TODAY)
    assert "Thiếu cột bắt buộc" in r.errors[0]
    dup = (
        MACRO_HEADER
        + "2026-09-30,CPI_YOY,3.4,%,TCTK,2026-10-06,\n2026-09-30,CPI_YOY,3.5,%,TCTK,2026-10-07,\n"
    )
    r = mc.parse_file("macro", write(tmp_path, dup), today=TODAY)
    assert len(r.rows) == 1 and any("trùng khóa" in e for e in r.errors)
    r = mc.parse_file("macro", write(tmp_path, MACRO_HEADER), today=TODAY)
    assert r.errors == ["Tệp không có dòng dữ liệu nào"]


def test_ca_nhan_theo_tuan_phai_thu_hai_khong_am_va_tuan_da_ket_thuc(tmp_path):
    ok = mc.parse_file(
        "individual",
        write(tmp_path, INDIVIDUAL_HEADER + "2026-11-16,18250.4,17980.2,BC tuần,\n"),
        today=TODAY,
    )
    assert not ok.errors and ok.rows[0][0] == date(2026, 11, 16)
    for line, fragment in (
        ("2026-11-17,100,90,BC,", "thứ Hai"),
        ("2026-11-23,100,90,BC,", "chưa kết thúc"),  # tuần 23-29/11 chưa hết vào 27/11
        ("2026-11-16,-5,90,BC,", "không được âm"),
    ):
        r = mc.parse_file(
            "individual", write(tmp_path, INDIVIDUAL_HEADER + line + "\n"), today=TODAY
        )
        assert any(fragment in e for e in r.errors), (line, r.errors)


def test_etf_theo_thang_phai_ngay_1_co_ten_quy_va_thang_da_ket_thuc(tmp_path):
    ok = mc.parse_file(
        "etf",
        write(
            tmp_path, ETF_HEADER + "2026-10-01,ETF A,-350.5,BC quỹ,\n2026-10-01,ETF B,120,BC quỹ,\n"
        ),
        today=TODAY,
    )
    assert not ok.errors and len(ok.rows) == 2
    for line, fragment in (
        ("2026-10-15,ETF A,1,BC,", "ngày 1"),
        ("2026-11-01,ETF A,1,BC,", "chưa kết thúc"),
        ("2026-10-01,,1,BC,", "etf_name trống"),
    ):
        r = mc.parse_file("etf", write(tmp_path, ETF_HEADER + line + "\n"), today=TODAY)
        assert any(fragment in e for e in r.errors), (line, r.errors)


def test_ngay_cuoi_thang_ke_ca_nam_nhuan():
    assert mc._is_month_end(date(2024, 2, 29)) and not mc._is_month_end(date(2024, 2, 28))
    assert mc._is_month_end(date(2025, 2, 28)) and mc._is_month_end(date(2026, 9, 30))
    assert not mc._is_month_end(date(2026, 9, 29))
