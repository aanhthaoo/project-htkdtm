"""Dòng lệnh thu thập dữ liệu.

Chạy từ thư mục `src/`:   python -m ingestion.cli <lệnh> [tùy chọn]
Mọi lệnh chạy lại được (không nhân đôi dữ liệu) và tiếp tục được từ chỗ dừng.
"""

import argparse
import logging
import sys
from datetime import UTC, date, datetime

from ingestion import db
from ingestion.client import Client


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingestion")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Tạo các bảng raw (IF NOT EXISTS)")
    p = sub.add_parser(
        "load-csv", help="Nạp CSV nhập tay (vĩ mô tháng, cá nhân tuần, ETF tháng) vào raw"
    )
    p.add_argument("kind", choices=["macro", "individual", "etf"])
    p.add_argument("file")
    p.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra, không ghi")
    p.add_argument(
        "--allow-sample",
        action="store_true",
        help="Cho phép dòng ghi chú 'Mẫu minh họa' (chỉ để thử)",
    )
    sub.add_parser("status", help="Tóm tắt số dòng từng bảng raw và nhật ký chạy")
    sub.add_parser("check", help="Kiểm tra thu thập đã xong chưa (mã thoát 0 = xong hết)")

    p = sub.add_parser("vndirect", help="Giá, khối ngoại, tự doanh toàn thị trường theo tháng")
    p.add_argument("--from", dest="start", type=parse_day, default=date(2020, 9, 1))
    p.add_argument("--to", dest="end", type=parse_day, default=None)
    p.add_argument("--kinds", nargs="+", default=["prices", "foreign", "prop"])
    p.add_argument("--force", action="store_true", help="Lấy lại cả các tháng đã xong")

    sub.add_parser("vietcap-symbols", help="Danh sách mã và nhóm chỉ số")
    p = sub.add_parser("vietcap-companies", help="ICB cấp 2/4, vốn hóa... mỗi mã một lần gọi")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-age-days", type=int, default=30)

    sub.add_parser("cafef-index", help="VN-Index từ CafeF")
    sub.add_parser("yfinance", help="7 chuỗi quốc tế")
    sub.add_parser("rss", help="Tin mới từ RSS và toàn văn")
    p = sub.add_parser(
        "daily", help="Cập nhật hằng ngày: gộp các bước nhẹ, lấy lại cửa sổ gần nhất"
    )
    p.add_argument("--days", type=int, default=10, help="Số ngày gần nhất lấy lại")
    p.add_argument("--skip", nargs="*", default=[], choices=["prices", "index", "yfinance", "news"])

    p = sub.add_parser("cafef-news-list", help="Lưu liên kết bài CafeF theo trang")
    p.add_argument("--stop-before", type=parse_day, default=date(2024, 9, 25))
    p.add_argument("--start-page", type=int, default=1)
    p = sub.add_parser("cafef-news-fetch", help="Lấy toàn văn các bài CafeF chờ")
    p.add_argument("--limit", type=int, default=None)

    p = sub.add_parser("hf-download", help="Tải các tệp EconVNNews")
    p.add_argument("--files", nargs="+", default=None)
    p = sub.add_parser("hf-load", help="Nạp tệp EconVNNews đã tải vào raw.news_backfill")
    p.add_argument("--files", nargs="+", default=None)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    conn = db.connect()
    db.apply_ddl(conn)

    if args.cmd == "load-csv":
        from pathlib import Path

        from ingestion import manual_csv

        result = manual_csv.load(args.kind, Path(args.file), args.allow_sample, args.dry_run)
        for err in result.errors:
            print("LỖI:", err)
        if result.errors:
            print(f"Không ghi gì: {len(result.errors)} lỗi, {len(result.rows)} dòng hợp lệ")
            return 1
        print(
            ("Hợp lệ (dry-run, chưa ghi): " if args.dry_run else "Đã nạp ")
            + f"{len(result.rows)} dòng vào {manual_csv.SPECS[args.kind].table}"
        )
        return 0
    if args.cmd == "init-db":
        print("Đã tạo/kiểm tra các bảng raw.")
    elif args.cmd == "status":
        return status(conn)
    elif args.cmd == "check":
        from ingestion import check

        return check.print_checks(check.run_checks(conn))
    elif args.cmd == "vndirect":
        from ingestion.sources import vndirect

        n = vndirect.backfill(
            conn, Client(delay=2.0), args.start, args.end, tuple(args.kinds), args.force
        )
        print("vndirect: nạp", n, "dòng")
    elif args.cmd == "vietcap-symbols":
        from ingestion.sources import vietcap

        client = Client(delay=1.5)
        vietcap.load_symbols(conn, client)
        vietcap.load_groups(conn, client)
    elif args.cmd == "vietcap-companies":
        from ingestion.sources import vietcap

        n = vietcap.load_companies(conn, Client(delay=1.5), args.max_age_days, args.limit)
        print("vietcap iQ: nạp", n, "mã")
    elif args.cmd == "cafef-index":
        from ingestion.sources import cafef_index

        print("cafef index:", cafef_index.load_index(conn, Client(delay=3.0, timeout=90)), "dòng")
    elif args.cmd == "yfinance":
        from ingestion.sources import yfinance_prices

        print("yfinance:", yfinance_prices.load(conn), "dòng")
    elif args.cmd == "rss":
        from ingestion.sources import rss

        print("rss:", rss.load_all(conn, Client(delay=2.0)), "bài mới")
    elif args.cmd == "cafef-news-list":
        from ingestion.sources import cafef_news

        stop = datetime(
            args.stop_before.year, args.stop_before.month, args.stop_before.day, tzinfo=UTC
        )
        n = cafef_news.collect_listing(conn, Client(delay=1.5), stop, args.start_page)
        print("cafef list:", n, "liên kết")
    elif args.cmd == "cafef-news-fetch":
        from ingestion.sources import cafef_news

        print("cafef fetch:", cafef_news.fetch_pending(conn, Client(delay=1.5), args.limit), "bài")
    elif args.cmd == "daily":
        return daily(conn, args.days, set(args.skip))
    elif args.cmd == "hf-download":
        from ingestion.sources import hf_backfill

        for name in args.files or hf_backfill.FILES:
            hf_backfill.download(name)
    elif args.cmd == "hf-load":
        from ingestion.sources import hf_backfill

        for name in args.files or hf_backfill.FILES:
            hf_backfill.load_file(conn, hf_backfill.DATA_DIR / name)
    return 0


def daily(conn, days: int, skip: set[str]) -> int:
    """Chuỗi cập nhật hằng ngày. Mỗi bước độc lập: bước lỗi được ghi lại, các bước sau vẫn chạy."""
    from datetime import timedelta

    from ingestion import quality
    from ingestion.sources import cafef_index, cafef_news, rss, vndirect, yfinance_prices

    since = date.today() - timedelta(days=days)
    failures: list[str] = []

    def step(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - gom lỗi để báo cuối cùng
            conn.rollback()
            failures.append(f"{name}: {exc}")
            logging.getLogger("ingestion.daily").error("%s lỗi: %s", name, exc)

    if "prices" not in skip:
        step(
            "vndirect", lambda: vndirect.backfill(conn, Client(delay=2.0), since, None, force=True)
        )
        step("quality", lambda: print_report(quality.report_latest_days(conn, days)))
    if "index" not in skip:
        step(
            "cafef-index",
            lambda: cafef_index.load_index(conn, Client(delay=3.0, timeout=90), start=since),
        )
    if "yfinance" not in skip:
        step("yfinance", lambda: yfinance_prices.load(conn, start=since))
    if "news" not in skip:
        step("rss", lambda: rss.load_all(conn, Client(delay=2.0)))
        stop = datetime.combine(since, datetime.min.time(), tzinfo=cafef_news.news.VN_TZ)
        step("cafef-list", lambda: cafef_news.collect_listing(conn, Client(delay=1.5), stop))
        step("cafef-fetch", lambda: cafef_news.fetch_pending(conn, Client(delay=1.5), limit=500))
    if failures:
        print("CÁC BƯỚC LỖI:")
        for message in failures:
            print("  " + message)
        return 1
    print("daily: xong, không lỗi")
    return 0


def print_report(rows: list[dict]) -> None:
    print()
    print("Độ sẵn sàng dữ liệu các ngày gần nhất (VNDirect):")
    print(f"{'ngày':12} {'có giá':>8} {'có GD':>7} {'KN hoạt động':>13} {'dòng TD':>8}  khối ngoại")
    for r in rows:
        flag = "đủ" if r["foreign_ok"] else "CHƯA ĐỦ"
        print(
            f"{r['date']!s:12} {r['prices']:>8} {r['traded']:>7} {r['foreign_active']:>13} "
            f"{r['prop']:>8}  {flag}"
        )


TABLES = [
    "raw.vnd_stock_prices", "raw.vnd_foreigns", "raw.vnd_proprietary", "raw.vietcap_symbols",
    "raw.vietcap_groups", "raw.vietcap_company", "raw.cafef_price", "raw.yf_prices",
    "raw.news_backfill", "raw.news_crawl",
]  # fmt: skip


def status(conn) -> int:
    print(f"{'bảng':28} {'số dòng':>12}")
    for table in TABLES:
        n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table:28} {n:>12,}")
    print("\nNhật ký chạy (trạng thái):")
    for row in conn.execute(
        "SELECT source, task, status, count(*), coalesce(sum(rows_loaded), 0) "
        "FROM raw.ingestion_run GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
    ):
        print(f"  {row[0]:14} {row[1]:10} {row[2]:8} cửa sổ={row[3]:<4} dòng={row[4]:,}")
    print("\nTin crawl theo trạng thái:")
    for row in conn.execute(
        "SELECT source, status, count(*) FROM raw.news_crawl GROUP BY 1, 2 ORDER BY 1, 2"
    ):
        print(f"  {row[0]:12} {row[1]:8} {row[2]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
