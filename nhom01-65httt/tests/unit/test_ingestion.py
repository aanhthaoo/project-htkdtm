"""Unit test cho lớp thu thập: phần chuyển đổi dữ liệu, không cần mạng và không cần DB."""

import json
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import feedparser
import pandas as pd

from ingestion import db
from ingestion.client import decode_body
from ingestion.sources import cafef_index, cafef_news, news, rss, vietcap, vndirect, yfinance_prices

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def load(rel: str):
    return json.loads((FIXTURES / rel).read_text(encoding="utf-8"))


# ---------- VNDirect ----------


def test_vndirect_parse_khoi_ngoai_dung_cot_va_don_vi():
    spec = vndirect.SPECS["foreign"]
    rows, skipped = vndirect.parse_rows(spec, load("vndirect/foreign_VNM_2024-01.json")["data"])
    assert skipped == 0 and rows
    cols = vndirect.columns(spec)
    assert all(len(r) == len(cols) for r in rows)
    last = dict(zip(cols, rows[-1], strict=True))
    assert last["code"] == "VNM" and last["trade_date"] == "2024-01-10"
    assert last["buy_val"] == 16195379000.0  # giữ nguyên đơn vị gốc (đồng)
    assert (
        last["net_val"] == last["buy_val"] - last["sell_val"]
        or abs(last["net_val"] - (last["buy_val"] - last["sell_val"])) < 1e3
    )
    assert last["extra"] is None  # không có trường lạ


def test_vndirect_chi_giu_type_stock_va_gom_truong_la_vao_extra():
    spec = vndirect.SPECS["prop"]
    api = [
        {"code": "AAA", "type": "STOCK", "floor": "HOSE", "date": "2024-01-02", "buyingVal": 1.0,
         "newField": 5},
        {"code": "BBB", "type": "CW", "floor": "HOSE", "date": "2024-01-02", "buyingVal": 2.0},
        {"code": "02", "type": None, "floor": "HOSE", "date": "2024-01-02"},
    ]  # fmt: skip
    rows, skipped = vndirect.parse_rows(spec, api)
    assert skipped == 2 and len(rows) == 1
    record = dict(zip(vndirect.columns(spec), rows[0], strict=True))
    assert record["code"] == "AAA" and record["buying_val"] == 1.0
    assert json.loads(record["extra"]) == {"newField": 5}


def test_vndirect_gia_co_du_cot():
    spec = vndirect.SPECS["prices"]
    rows, _ = vndirect.parse_rows(spec, load("vndirect/price_VNM_2024-01.json")["data"])
    record = dict(zip(vndirect.columns(spec), rows[-1], strict=True))
    assert record["close"] == 67.5 and record["pt_value"] == 0.0
    assert record["nm_value"] > 1e8


# ---------- Vietcap ----------


def test_vietcap_company_row():
    info = load("vietcap/company_VNM_sample.json")
    row = vietcap.company_row("VNM", info)
    record = dict(zip(vietcap.COMPANY_COLUMNS, row, strict=True))
    assert record["icb_code_lv2"] == "3500" and record["icb_code_lv4"] == "3577"
    assert record["listing_date"] == date(2006, 1, 19)
    assert record["market_cap"] > 1e12


def test_vietcap_symbol_row():
    item = load("vietcap/symbols_getAll_sample.json")[0]
    row = vietcap.symbol_row(item)
    assert row[0] == item["symbol"] and row[2] == item["board"]


# ---------- CafeF ----------


def test_cafef_parse_row_doi_ngay_dd_mm_yyyy():
    raw = load("cafef/price_VNM_2024-01.json")["Data"]["Data"][0]
    row = cafef_index.parse_row("VNM", raw)
    assert row[0] == "VNM" and row[1] == date(2024, 1, 10)
    assert row[5] == 67.5  # đóng cửa, nghìn đồng


def test_cafef_thoi_diem_tu_ma_bai():
    url = "https://cafef.vn/vafi-kien-nghi-188261119142908476.chn"
    assert news.cafef_published_from_url(url) == datetime(
        2026, 11, 19, 14, 29, 8, tzinfo=timezone(timedelta(hours=7))
    )
    assert news.cafef_published_from_url("https://cafef.vn/ban-do-du-an.chn") is None


def test_cafef_extract_links_bo_trung_va_bo_lien_ket_khong_phai_bai():
    html = """
    <a href="/bai-a-188261119142908476.chn">A</a>
    <a href="/bai-a-188261119142908476.chn">A lần hai</a>
    <a href="/ban-do-du-an.chn">không phải bài</a>
    <a href="/bai-b-188261118101010123.chn?x=1">B</a>
    """
    links = cafef_news.extract_links(html)
    assert links == [
        "https://cafef.vn/bai-a-188261119142908476.chn",
        "https://cafef.vn/bai-b-188261118101010123.chn",
    ]


# ---------- Bóc bài báo ----------

ARTICLE = """
<html><head>
<meta property="og:title" content="Tiêu đề thử nghiệm">
<meta property="og:description" content="Tóm tắt ngắn">
<meta property="article:published_time" content="2026-11-19T14:31:00">
<meta property="article:section" content="Chứng khoán">
<script>var x = 1;</script></head>
<body><div class="menu"><p>Menu ngắn</p></div>
<div class="detail-content">
<p>Đoạn nội dung đầu tiên đủ dài để được giữ lại trong kết quả bóc tách bài báo.</p>
<p>Ngắn</p>
<p>Đoạn nội dung thứ hai cũng đủ dài để được giữ lại, có ký tự \x00 lạ cần loại bỏ.</p>
</div></body></html>
"""


def test_parse_article_chi_lay_noi_dung_trong_vung_chon():
    parsed = news.parse_article(ARTICLE, "div.detail-content")
    assert parsed["title"] == "Tiêu đề thử nghiệm"
    assert parsed["category"] == "Chứng khoán"
    assert "Menu ngắn" not in parsed["content"] and "Ngắn" not in parsed["content"].splitlines()
    assert len(parsed["content"].splitlines()) == 2
    assert "\x00" not in parsed["content"]


def test_gio_dang_khong_co_mui_gio_hieu_la_gmt_7():
    dt = news.parse_local_time("2026-11-19T14:31:00")
    assert dt.utcoffset() == timedelta(hours=7)
    assert news.parse_local_time("2026-11-19T14:31:00+0700").utcoffset() == timedelta(hours=7)
    assert news.parse_local_time("không phải ngày") is None


def test_article_row_failed_khi_khong_co_noi_dung():
    row = news.article_row("u", "cafef", {"title": "t", "content": ""}, None)
    assert row[news.NEWS_COLUMNS.index("status")] == "failed"
    ok = news.article_row("u", "cafef", {"title": "t", "content": "nội dung"}, None)
    assert ok[news.NEWS_COLUMNS.index("status")] == "done"


# ---------- RSS ----------


def test_rss_chuan_hoa_mui_gio_ve_utc():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>A</title><link>http://a</link><pubDate>Tue, 24 Nov 2026 01:36:06 GMT</pubDate></item>
    <item><title>B</title><link>http://b</link><pubDate>Tue, 24 Nov 2026 08:36:06 +0700</pubDate></item>
    </channel></rss>"""
    entries = feedparser.parse(xml).entries
    a, b = (rss.entry_published(e) for e in entries)
    assert a == b == datetime(2026, 11, 24, 1, 36, 6, tzinfo=UTC)


# ---------- yfinance ----------


def test_yfinance_frame_to_rows_bo_dong_nan():
    index = pd.to_datetime(["2024-01-02", "2024-01-03"]).tz_localize("America/New_York")
    frame = pd.DataFrame(
        {"Open": [1.0, 2.0], "High": [1.5, 2.5], "Low": [0.5, 1.5], "Close": [1.2, float("nan")],
         "Adj Close": [1.2, float("nan")], "Volume": [10, 20]},
        index=index,
    )  # fmt: skip
    rows = yfinance_prices.frame_to_rows("^GSPC", frame)
    assert len(rows) == 1 and rows[0][:2] == ("^GSPC", date(2024, 1, 2))


# ---------- Tiện ích chung ----------


def test_dedupe_rows_giu_dong_cuoi():
    rows = [("a", 1, "x"), ("a", 1, "y"), ("b", 1, "z")]
    assert db.dedupe_rows(rows, (0, 1)) == [("a", 1, "y"), ("b", 1, "z")]


def test_month_windows_bao_gom_thang_dau_va_thang_cuoi():
    w = db.month_windows(date(2020, 9, 15), date(2021, 1, 10))
    assert w[0] == (date(2020, 9, 15), date(2020, 9, 30))
    assert w[-1] == (date(2021, 1, 1), date(2021, 1, 10))
    assert len(w) == 5
    assert (date(2020, 12, 1), date(2020, 12, 31)) in w


def test_decode_body_xu_ly_gzip_gia_mao():
    import gzip

    assert decode_body(gzip.compress(b"abc"), "gzip") == b"abc"
    assert (
        decode_body(b"du lieu thuong", "gzip") == b"du lieu thuong"
    )  # khai báo gzip nhưng không nén
    assert decode_body(b"abc", None) == b"abc"


def test_jdump_bo_rong_va_ky_tu_nul():
    assert db.jdump({}) is None and db.jdump(None) is None
    assert "\\u0000" not in db.jdump({"a": "x\x00y"})
    assert db.clean_text("a\x00b") == "ab"
