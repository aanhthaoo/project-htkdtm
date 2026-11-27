"""Kiểm thử kho dữ liệu trên PostgreSQL đang chạy: 5 thao tác OLAP phải cho số liệu nhất quán với nhau.

Chạy:  pytest -m smoke tests/smoke/test_warehouse.py     (cần đã chạy dbt: python src/dbt_dw/run.py build)
"""

from pathlib import Path

import psycopg
import pytest

from ingestion import db

pytestmark = pytest.mark.smoke

OLAP = Path(__file__).resolve().parents[2] / "src" / "dbt_dw" / "analyses" / "olap"
TOL = 1e-6


@pytest.fixture(scope="module")
def conn():
    try:
        connection = db.connect()
    except psycopg.OperationalError:
        pytest.skip("Không kết nối được PostgreSQL")
    n = connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='dw' AND table_name='fact_money_flow'"
    ).fetchone()[0]
    if not n or connection.execute("SELECT count(*) FROM dw.fact_money_flow").fetchone()[0] == 0:
        pytest.skip("Chưa có dữ liệu trong dw.fact_money_flow (chạy dbt trước)")
    yield connection
    connection.close()


def run(conn, name: str):
    return conn.execute((OLAP / name).read_text(encoding="utf-8")).fetchall()


def direct_foreign_total(conn) -> float:
    return conn.execute(
        "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f "
        "JOIN dw.dim_investor_type it USING (investor_type_key) WHERE it.code = 'FOREIGN'"
    ).fetchone()[0]


def test_rollup_tong_toan_ky_bang_tong_truc_tiep(conn):
    rows = run(conn, "01_rollup_thoi_gian.sql")
    grand = [r for r in rows if r[0] is None and r[1] is None and r[2] is None]
    assert len(grand) == 1
    assert grand[0][3] == pytest.approx(direct_foreign_total(conn), abs=1e-3)


def test_rollup_tong_nam_bang_tong_cac_thang_va_tong_thang_bang_tong_cac_tuan(conn):
    rows = run(conn, "01_rollup_thoi_gian.sql")
    by_year = {r[0]: r[3] for r in rows if r[0] is not None and r[1] is None}
    months, weeks = {}, {}
    for year, month, week, value in rows:
        if year is not None and month is not None and week is None:
            months.setdefault(year, 0.0)
            months[year] += value
        if year is not None and month is not None and week is not None:
            weeks.setdefault((year, month), 0.0)
            weeks[(year, month)] += value
    for year, total in by_year.items():
        assert months[year] == pytest.approx(total, abs=1e-3)
    month_totals = {(r[0], r[1]): r[3] for r in rows if r[0] and r[1] and r[2] is None}
    for key, total in month_totals.items():
        assert weeks[key] == pytest.approx(total, abs=1e-3)


def test_drilldown_tong_ma_bang_tong_nganh(conn):
    rows = run(conn, "02_drilldown_nganh_ma.sql")
    grand = [r for r in rows if r[0] is None][0][3]
    stocks = sum(r[3] for r in rows if r[2] is not None)
    assert stocks == pytest.approx(grand, abs=1e-3)
    by_l2 = {}
    for l1, l2, symbol, value in rows:
        if symbol is None and l2 is not None:
            by_l2[(l1, l2)] = value
    for (l1, l2), subtotal in by_l2.items():
        members = sum(r[3] for r in rows if r[0] == l1 and r[1] == l2 and r[2] is not None)
        assert members == pytest.approx(subtotal, abs=1e-3)


def test_slice_chi_gom_khoi_ngoai(conn):
    rows = run(conn, "03_slice_khoi_ngoai.sql")
    assert rows, "slice không trả dòng nào"
    weeks = sorted({r[0] for r in rows})
    expected = conn.execute(
        "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f "
        "JOIN dw.dim_time t USING (date_key) JOIN dw.dim_investor_type it USING (investor_type_key) "
        "WHERE it.code = 'FOREIGN' AND t.week_start_date = ANY(%s)",
        (weeks,),
    ).fetchone()[0]
    assert sum(r[2] for r in rows) == pytest.approx(expected, abs=1e-3)


def test_dice_ngan_hang_quy_3_2025_khop_truy_van_truc_tiep(conn):
    rows = run(conn, "04_dice_khoi_ngoai_ngan_hang_quy.sql")
    direct = conn.execute(
        """
        SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f
        JOIN dw.dim_time t USING (date_key)
        JOIN dw.dim_stock d USING (stock_key)
        JOIN dw.dim_sector s USING (sector_key)
        JOIN dw.dim_investor_type it USING (investor_type_key)
        WHERE it.code = 'FOREIGN' AND s.icb_l2_code = '8300' AND t.date BETWEEN '2025-07-01' AND '2025-09-30'
        """
    ).fetchone()[0]
    assert sum(r[3] for r in rows) == pytest.approx(direct, abs=1e-3)
    for _symbol, buy, sell, net in rows:
        assert net == pytest.approx(buy - sell, abs=1e-6)


def test_pivot_tong_cot_bang_tong_hang(conn):
    rows = run(conn, "05_pivot_nganh_tuan.sql")
    assert rows
    for row in rows:
        weeks = [v for v in row[1:7] if v is not None]
        assert sum(weeks) == pytest.approx(row[7], abs=1e-3)


def test_cube_cac_muc_tong_hop_nhat_quan(conn):
    rows = run(conn, "06_cube_nganh_nhom_nha_dau_tu.sql")
    grand = [r for r in rows if r[2] == 1 and r[3] == 1][0][4]
    by_sector = sum(r[4] for r in rows if r[2] == 0 and r[3] == 1)
    by_investor = sum(r[4] for r in rows if r[2] == 1 and r[3] == 0)
    cells = sum(r[4] for r in rows if r[2] == 0 and r[3] == 0)
    for value in (by_sector, by_investor, cells):
        assert value == pytest.approx(grand, abs=1e-3)


def test_grouping_sets_gom_dung_cac_muc(conn):
    rows = run(conn, "07_grouping_sets.sql")
    assert any(r[0] is None and r[1] is None for r in rows)  # toàn kỳ
    assert any(r[0] is None and r[1] is not None for r in rows)  # theo nhóm nhà đầu tư
    assert any(r[0] is not None and r[1] is None for r in rows)  # theo tuần
    assert any(r[0] is not None and r[1] is not None for r in rows)  # tuần x nhóm


def test_materialized_view_khop_fact(conn):
    mv = conn.execute(
        "SELECT sum(net_value_bn) FROM dw.mv_sector_weekly_flow WHERE investor_type = 'FOREIGN'"
    ).fetchone()[0]
    assert mv == pytest.approx(direct_foreign_total(conn), abs=1e-3)
    kpi = conn.execute("SELECT sum(foreign_net_bn) FROM dw.mv_market_daily_kpi").fetchone()[0]
    assert kpi == pytest.approx(direct_foreign_total(conn), abs=1e-3)


# ---------------- Nạp CSV nhập tay (TV4) ----------------
def test_nap_csv_nhap_tay_vao_raw_ghi_de_khong_nhan_doi_va_ghi_dq_log(tmp_path):
    """Dùng khóa ở quá khứ xa (tháng 01/2019, trước dữ liệu của dự án) và xóa sau khi thử để không làm bẩn kho."""
    from ingestion import manual_csv

    csv_path = tmp_path / "cpi.csv"
    header = "period_end,indicator_code,value,unit,source,published_date,note\n"
    csv_path.write_text(
        header + "2019-01-31,CPI_YOY,2.5,%,Kiểm thử,2019-02-06,thử\n", encoding="utf-8"
    )
    conn = db.connect()
    try:
        before = conn.execute(
            "SELECT count(*) FROM dw.dq_log WHERE source = 'manual_csv'"
        ).fetchone()[0]
        result = manual_csv.load("macro", csv_path)
        assert not result.errors
        csv_path.write_text(
            header + "2019-01-31,CPI_YOY,2.7,%,Kiểm thử,2019-02-06,thử\n", encoding="utf-8"
        )
        manual_csv.load("macro", csv_path)  # nạp lại cùng khóa: ghi đè, không thêm dòng
        rows = conn.execute(
            "SELECT value FROM raw.manual_macro_monthly WHERE period_end = '2019-01-31' AND indicator_code = 'CPI_YOY'"
        ).fetchall()
        assert rows == [(2.7,)]
        # tệp sai: không ghi gì nhưng vẫn có dòng nhật ký báo lỗi
        bad = tmp_path / "bad.csv"
        bad.write_text(header + "2019-01-15,CPI_YOY,2.5,%,Kiểm thử,2019-02-06,\n", encoding="utf-8")
        assert manual_csv.load("macro", bad).errors
        assert (
            conn.execute(
                "SELECT count(*) FROM raw.manual_macro_monthly WHERE period_end = '2019-01-15'"
            ).fetchone()[0]
            == 0
        )
        after = conn.execute(
            "SELECT count(*) FROM dw.dq_log WHERE source = 'manual_csv'"
        ).fetchone()[0]
        assert after == before + 3
        failed = conn.execute(
            "SELECT passed FROM dw.dq_log WHERE source = 'manual_csv' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        assert failed is False
    finally:
        conn.execute("DELETE FROM raw.manual_macro_monthly WHERE period_end = '2019-01-31'")
        conn.execute(
            "DELETE FROM dw.dq_log WHERE source = 'manual_csv' AND details->>'file' IN ('cpi.csv', 'bad.csv')"
        )
        conn.commit()
        conn.close()
