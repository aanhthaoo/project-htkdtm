"""Kiểm tra việc thu thập đã hoàn tất chưa: so số liệu thực tế với kỳ vọng của từng nguồn.

Kết quả mỗi dòng: XONG / ĐANG CHẠY / LỖI. Mã thoát 0 chỉ khi mọi nguồn XONG.
"""

from dataclasses import dataclass
from datetime import date

from ingestion import db

DONE, RUNNING, FAILED = "XONG", "ĐANG CHẠY", "LỖI"


@dataclass
class Item:
    name: str
    state: str
    detail: str


def _scalar(conn, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def _run_counts(conn, source: str, task: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, count(*) FROM raw.ingestion_run WHERE source=%s AND task=%s GROUP BY 1",
        (source, task),
    ).fetchall()
    return dict(rows)


def check_vndirect(conn) -> list[Item]:
    from ingestion.sources import vndirect

    expected = len(db.month_windows(vndirect.FIRST_DATE, date.today()))
    items = []
    for kind in ("prices", "foreign", "prop"):
        counts = _run_counts(conn, "vndirect", kind)
        done, failed = counts.get("done", 0), counts.get("failed", 0)
        if failed:
            state = FAILED
        elif done >= expected and not counts.get("running"):
            state = DONE
        else:
            state = RUNNING
        items.append(Item(f"VNDirect {kind}", state, f"{done}/{expected} tháng, {failed} lỗi"))
    return items


def check_vietcap(conn) -> list[Item]:
    n_symbols = _scalar(conn, "SELECT count(*) FROM raw.vietcap_symbols")
    listed = _scalar(
        conn,
        "SELECT count(*) FROM raw.vietcap_symbols WHERE type='STOCK' AND board IN ('HSX','HNX','UPCOM')",
    )
    n_company = _scalar(conn, "SELECT count(*) FROM raw.vietcap_company")
    groups = _scalar(conn, "SELECT count(DISTINCT group_name) FROM raw.vietcap_groups")
    return [
        Item("Vietcap danh sách mã", DONE if n_symbols > 3000 else RUNNING, f"{n_symbols} mã"),
        Item("Vietcap nhóm chỉ số", DONE if groups >= 5 else RUNNING, f"{groups}/5 nhóm"),
        Item(
            "Vietcap iQ công ty",
            DONE if listed and n_company >= listed * 0.98 else RUNNING,
            f"{n_company}/{listed} mã đang niêm yết",
        ),
    ]


def check_misc(conn) -> list[Item]:
    items = []
    n_idx = _scalar(conn, "SELECT count(*) FROM raw.cafef_price WHERE symbol='VNINDEX'")
    items.append(Item("CafeF VN-Index", DONE if n_idx >= 1500 else RUNNING, f"{n_idx} phiên"))
    n_yf = _scalar(conn, "SELECT count(DISTINCT ticker) FROM raw.yf_prices")
    items.append(Item("yfinance", DONE if n_yf >= 7 else RUNNING, f"{n_yf}/7 chuỗi"))
    hf_done = _run_counts(conn, "hf_econvnnews", "load").get("done", 0)
    n_bf = _scalar(conn, "SELECT count(*) FROM raw.news_backfill")
    items.append(
        Item("EconVNNews", DONE if hf_done >= 4 else RUNNING, f"{hf_done}/4 tệp, {n_bf:,} bài")
    )
    return items


def check_news(conn) -> list[Item]:
    rows = dict(
        conn.execute(
            "SELECT status, count(*) FROM raw.news_crawl WHERE source='cafef' GROUP BY 1"
        ).fetchall()
    )
    oldest = _scalar(
        conn, "SELECT min(published_at)::date FROM raw.news_crawl WHERE source='cafef'"
    )
    pending, done, failed = rows.get("pending", 0), rows.get("done", 0), rows.get("failed", 0)
    reached = oldest is not None and oldest <= date(2024, 9, 30)
    if pending == 0 and done and reached:
        state = DONE
    else:
        state = RUNNING
    detail = f"xong {done:,}, chờ {pending:,}, lỗi {failed:,}; bài cũ nhất {oldest}"
    if not reached:
        detail += " (danh sách chưa tới 09/2024)"
    items = [Item("CafeF tin", state, detail)]
    rss = _scalar(
        conn, "SELECT count(*) FROM raw.news_crawl WHERE source <> 'cafef' AND status='done'"
    )
    items.append(Item("RSS", DONE if rss else RUNNING, f"{rss:,} bài"))
    return items


def run_checks(conn) -> list[Item]:
    return [
        *check_vndirect(conn),
        *check_vietcap(conn),
        *check_misc(conn),
        *check_news(conn),
    ]


def print_checks(items: list[Item]) -> int:
    width = max(len(i.name) for i in items)
    for i in items:
        print(f"{i.name:{width}}  {i.state:10}  {i.detail}")
    states = {i.state for i in items}
    print()
    if states == {DONE}:
        print("KẾT LUẬN: tất cả nguồn đã XONG.")
        return 0
    if FAILED in states:
        print(
            "KẾT LUẬN: có nguồn LỖI. Xem raw.ingestion_run (status = 'failed') và chạy lại lệnh tương ứng."
        )
        return 2
    print("KẾT LUẬN: còn nguồn ĐANG CHẠY (hoặc chưa chạy).")
    return 1
