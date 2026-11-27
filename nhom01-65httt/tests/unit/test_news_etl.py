"""Unit test cho đường ống làm sạch tin tức (không cần DB)."""

from datetime import UTC, date, datetime, timedelta, timezone

from etl.news import entities, normalize, relevance, session

VN = timezone(timedelta(hours=7))


# ---------- Chuẩn hóa ----------


def test_clean_text_bo_html_giai_ma_entity_va_dong_rac():
    raw = (
        "<p>Cổ phiếu VNM tăng mạnh &amp; thanh khoản cải thiện rõ rệt trong phiên.</p>\n"
        "Nguồn: Vietstock\n"
        "Xem thêm: tin liên quan đến cổ phiếu\n"
        "Ngắn\n"
        "Khối ngoại bán ròng  mạnh   ở nhóm ngân hàng trong tuần này."
    )
    out = normalize.clean_text(raw)
    assert "<p>" not in out and "&amp;" not in out and "& thanh khoản" in out
    assert "Nguồn:" not in out and "Xem thêm" not in out and "Ngắn" not in out.splitlines()
    assert "Khối ngoại bán ròng mạnh ở nhóm" in out  # khoảng trắng được gộp


def test_clean_text_chuan_hoa_unicode_nfc():
    text = "Ngân hàng Việt Nam tăng trưởng tín dụng"
    decomposed = text.replace("â", "â")
    assert decomposed != text
    assert normalize.clean_text(decomposed) == normalize.clean_text(text)


def test_title_key_bo_dau_cau_va_khong_phan_biet_hoa_thuong():
    assert normalize.title_key("VN-Index  tăng 10 điểm!") == normalize.title_key(
        "vn index tăng 10 điểm"
    )


def test_content_hash_giong_nhau_khi_chi_khac_dinh_dang():
    a = "Khối ngoại bán ròng 500 tỷ đồng trong phiên hôm nay."
    b = "KHỐI NGOẠI bán ròng 500 tỷ đồng, trong phiên hôm nay"
    assert normalize.content_hash(a) == normalize.content_hash(b)
    assert normalize.content_hash(a) != normalize.content_hash("Nội dung khác hẳn.")


def test_canonical_url_bo_query_www_va_dua_ve_https():
    assert (
        normalize.canonical_url("http://www.Vietstock.vn/2026/11/bai-viet-1.htm/?utm=x#top")
        == "https://vietstock.vn/2026/11/bai-viet-1.htm"
    )
    assert normalize.article_id("http://vietstock.vn/a") == normalize.article_id(
        "https://www.vietstock.vn/a/"
    )


# ---------- Phiên giao dịch ----------

TRADING = [date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 23), date(2026, 11, 24)]


def make_calendar() -> session.Calendar:
    rows = []
    d = date(2026, 11, 16)
    while d <= date(2026, 11, 27):
        trading = d in TRADING
        soa = next((t for t in TRADING if t >= d), None)
        nxt = next((t for t in TRADING if t > d), None)
        rows.append((d, trading, soa, nxt))
        d += timedelta(days=1)
    return session.Calendar.from_rows(rows)


def test_tin_truoc_15h_ngay_giao_dich_thuoc_phien_cung_ngay():
    cal = make_calendar()
    at = datetime(2026, 11, 19, 14, 59, tzinfo=VN)
    assert session.assign_session(at, at.date(), True, cal) == date(2026, 11, 19)


def test_tin_tu_15h_thuoc_phien_ke_tiep():
    cal = make_calendar()
    at = datetime(2026, 11, 19, 15, 0, tzinfo=VN)
    assert session.assign_session(at, at.date(), True, cal) == date(2026, 11, 20)


def test_tin_thu_sau_sau_15h_thuoc_phien_thu_hai():
    cal = make_calendar()
    at = datetime(2026, 11, 20, 16, 30, tzinfo=VN)  # thứ sáu 20/11
    assert session.assign_session(at, at.date(), True, cal) == date(2026, 11, 23)


def test_tin_cuoi_tuan_thuoc_phien_thu_hai_ke_tiep():
    cal = make_calendar()
    at = datetime(2026, 11, 21, 9, 0, tzinfo=VN)  # thứ bảy
    assert session.assign_session(at, at.date(), True, cal) == date(2026, 11, 23)


def test_mui_gio_utc_duoc_doi_ve_gmt7():
    cal = make_calendar()
    at = datetime(2026, 11, 19, 8, 30, tzinfo=UTC)  # = 15:30 GMT+7
    assert session.assign_session(at, at.date(), True, cal) == date(2026, 11, 20)


def test_chi_biet_ngay_thi_khong_day_sang_phien_sau_neu_la_ngay_giao_dich():
    cal = make_calendar()
    assert session.assign_session(None, date(2026, 11, 19), False, cal) == date(2026, 11, 19)
    assert session.assign_session(None, date(2026, 11, 21), False, cal) == date(2026, 11, 23)
    assert session.assign_session(None, None, False, cal) is None


# ---------- Nhận diện mã và ngành ----------

SYMBOLS = {"VNM", "HPG", "VCB", "CEO", "FPT", "SHS"}
SECTORS = {"VNM": "3500", "HPG": "1700", "VCB": "8300", "CEO": "8600", "FPT": "9500", "SHS": "8700"}


def make_extractor(aliases=None) -> entities.Extractor:
    return entities.Extractor(SYMBOLS, SECTORS, aliases)


def codes(mentions, entity_type="STOCK"):
    return {m.entity_code for m in mentions if m.entity_type == entity_type}


def test_nhan_dien_ma_in_hoa_co_trong_danh_muc():
    m = make_extractor().extract(
        "VNM và HPG đi ngược xu hướng", "Cổ phiếu FPT cũng tăng. USD tăng giá."
    )
    assert codes(m) == {"VNM", "HPG", "FPT"}  # USD không phải mã


def test_ma_trung_tu_viet_tat_chi_tinh_khi_co_ngu_canh():
    ex = make_extractor()
    assert "CEO" not in codes(ex.extract("Tân CEO nhậm chức", "Ông A là CEO của tập đoàn."))
    assert "CEO" in codes(ex.extract("Tập đoàn C.E.O", "Cổ phiếu CEO tăng trần."))
    assert "CEO" in codes(ex.extract("Tin doanh nghiệp", "Tập đoàn C.E.O (CEO) công bố kết quả."))


def test_khong_nhan_dien_chuoi_dai_hon_3_ky_tu_hoac_chu_thuong():
    m = make_extractor().extract(
        "vnm tăng", "VNMX và xVNM không phải mã; hpg viết thường cũng không tính."
    )
    assert codes(m) == set()


def test_ten_cong_ty_anh_xa_ve_ma():
    ex = make_extractor({"Vinamilk": "VNM", "Hòa Phát": "HPG"})
    m = ex.extract("Vinamilk công bố lãi quý", "Hòa Phát mở rộng sản xuất thép.")
    assert codes(m) == {"VNM", "HPG"}
    assert {x.method for x in m if x.entity_type == "STOCK"} == {"alias"}


def test_nganh_suy_ra_tu_ma_va_tu_tu_khoa():
    m = make_extractor().extract(
        "Ngân hàng đẩy mạnh tín dụng",
        "VCB và HPG dẫn dắt. Ngành thép phục hồi, thép xây dựng tăng giá.",
    )
    sectors = codes(m, "SECTOR")
    assert {"8300", "1700"} <= sectors  # VCB -> ngân hàng, HPG -> thép, từ khóa ngân hàng và thép


def test_tu_khoa_nganh_trong_noi_dung_can_xuat_hien_tu_2_lan():
    ex = make_extractor()
    assert "5300" not in codes(
        ex.extract("Tin thị trường", "Một siêu thị mới khai trương."), "SECTOR"
    )
    assert "5300" in codes(
        ex.extract("Tin thị trường", "Siêu thị mở rộng, bán lẻ tăng trưởng."), "SECTOR"
    )


# ---------- Bài liên quan chứng khoán ----------


def test_bai_chung_khoan_duoc_giu_con_tin_the_gioi_bi_loai():
    related = relevance.score_article("VN-Index giảm", "Khối ngoại bán ròng mạnh.", None, 0)
    assert related.is_related and related.reason == "strong_keyword"
    other = relevance.score_article("Lũ lụt miền Trung", "Mưa lớn kéo dài nhiều ngày.", "Xã hội", 0)
    assert not other.is_related


def test_chuyen_muc_chung_khoan_hoac_co_ma_chac_chan_la_lien_quan():
    assert (
        relevance.score_article(
            "Tin", "Nội dung không có từ khóa.", "Thị trường chứng khoán", 0
        ).reason
        == "category"
    )
    assert relevance.score_article("Tin", "Nội dung.", None, 1).reason == "ticker"


def test_tu_khoa_yeu_can_du_so_lan():
    text = "Lãi suất tăng, tỷ giá biến động, tín dụng chậm lại, lạm phát cao."
    assert relevance.score_article("Kinh tế", text, None, 0).is_related  # 4 từ khóa yếu
    assert not relevance.score_article(
        "Kinh tế", "Lãi suất tăng, doanh nghiệp khó khăn.", None, 0
    ).is_related
