"""Unit test cho phần trích số liệu khối ngoại từ bài tổng hợp phiên."""

import pytest

from etl.news import crosscheck


def test_parse_so_theo_dinh_dang_viet():
    assert crosscheck.parse_vn_number("1.200") == 1200
    assert crosscheck.parse_vn_number("138,5") == 138.5
    assert crosscheck.parse_vn_number("1.234,5") == 1234.5
    assert crosscheck.parse_vn_number("45") == 45


def test_trich_ban_rong_va_mua_rong():
    text = (
        "Khối ngoại bán ròng đột biến lên 1.200 tỷ đồng. "
        "Ở chiều ngược lại, khối ngoại mua ròng 138,5 tỷ đồng ở nhóm thép."
    )
    claims = crosscheck.extract_foreign_net(text)
    assert [c.signed_bn for c in claims] == [-1200.0, 138.5]


def test_don_vi_nghin_ty_va_trieu():
    big = crosscheck.extract_foreign_net("Khối ngoại bán ròng hơn 1,2 nghìn tỷ đồng trong tuần.")
    assert big[0].signed_bn == pytest.approx(-1200)
    small = crosscheck.extract_foreign_net("Khối ngoại mua ròng 500 triệu đồng.")
    assert small[0].signed_bn == pytest.approx(0.5)


def test_khong_trich_khi_khong_phai_khoi_ngoai():
    assert crosscheck.extract_foreign_net("Tự doanh bán ròng 300 tỷ đồng.") == []
    assert crosscheck.extract_foreign_net("Khối ngoại giao dịch sôi động trong phiên.") == []


def test_dung_sai_tuyet_doi_hoac_tuong_doi():
    assert crosscheck.within_tolerance(-1200, -1203, abs_tol=5, rel_tol=0.02)  # lệch 3 tỷ
    assert crosscheck.within_tolerance(-1200, -1220, abs_tol=5, rel_tol=0.02)  # lệch 1,6%
    assert not crosscheck.within_tolerance(-1200, -1300, abs_tol=5, rel_tol=0.02)
