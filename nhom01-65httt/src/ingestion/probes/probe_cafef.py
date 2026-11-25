"""Kiểm chứng API dữ liệu của CafeF: giá, khối ngoại, tự doanh (N2).

Mục tiêu: biết endpoint, định dạng tham số, kích thước trang tối đa, độ dài lịch sử mỗi lần gọi,
độ phủ lịch sử theo năm, độ ổn định (có trả rỗng thất thường hay không).

Chạy:  python src/ingestion/probes/probe_cafef.py [--out ket_qua.json]
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import build_url, get_json, polite_sleep  # noqa: E402

BASE = "https://cafef.vn/du-lieu/ajax/pagenew/datahistory/"
HEADERS = {"Referer": "https://cafef.vn/"}
ENDPOINTS = {"price": "pricehistory", "foreign": "gdkhoingoai", "prop": "gdtudoanh"}
# Mỗi sàn một mã đại diện
SYMBOLS = {"HOSE": "VNM", "HNX": "SHS", "UPCOM": "BSR"}
YEARS = range(2020, 2027)
PAGE_SIZE = 30  # thử nghiệm cho thấy trang lớn hơn 30 có thể trả rỗng
MAX_TRIES = 4


def fetch(endpoint: str, symbol: str, start: str, end: str, page: int, size: int = PAGE_SIZE):
    url = build_url(
        BASE + ENDPOINTS[endpoint] + ".ashx",
        {"Symbol": symbol, "StartDate": start, "EndDate": end, "PageIndex": page, "PageSize": size},
    )
    status, data = get_json(url, HEADERS)
    polite_sleep()
    return status, data


def extract_rows(data: dict) -> list[dict]:
    inner = data["Data"]["Data"]
    if isinstance(inner, dict):  # tự doanh bọc thêm một cấp
        return inner.get("ListDataTudoanh") or []
    return inner or []


def row_date(row: dict) -> str:
    raw = row.get("Ngay") or row.get("Date")
    day, month, year = raw.split("/")
    return f"{year}-{month}-{day}"


def fetch_with_retry(endpoint: str, symbol: str, start: str, end: str, page: int):
    """Nguồn thỉnh thoảng trả total=0 ở lần gọi đầu; thử lại tối đa MAX_TRIES lần."""
    attempts = 0
    for _ in range(MAX_TRIES):
        attempts += 1
        status, data = fetch(endpoint, symbol, start, end, page)
        if status == 200 and data and data.get("Success") and extract_rows(data):
            return data, attempts
    return data, attempts


def probe_year(endpoint: str, symbol: str, year: int) -> dict:
    start, end = f"01/01/{year}", f"12/31/{year}"
    first, tries = fetch_with_retry(endpoint, symbol, start, end, 1)
    rows = extract_rows(first) if first else []
    if not rows:
        return {"year": year, "total": 0, "tries": tries}
    total = first["Data"]["TotalCount"]
    last_page = math.ceil(total / PAGE_SIZE)
    latest = max(row_date(r) for r in rows)
    earliest = min(row_date(r) for r in rows)
    if last_page > 1:
        last, _ = fetch_with_retry(endpoint, symbol, start, end, last_page)
        last_rows = extract_rows(last) if last else []
        if last_rows:
            earliest = min(row_date(r) for r in last_rows)
    return {
        "year": year,
        "total": total,
        "earliest": earliest,
        "latest": latest,
        "pages": last_page,
        "tries": tries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="cafef_probe_result.json")
    parser.add_argument(
        "--endpoints",
        nargs="+",
        default=list(ENDPOINTS),
        choices=list(ENDPOINTS),
        help="Chỉ thăm dò các endpoint này (endpoint giá có thể chậm/không ổn định)",
    )
    args = parser.parse_args()

    results: dict = {}
    for endpoint in args.endpoints:
        for exchange, symbol in SYMBOLS.items():
            key = f"{endpoint}:{exchange}:{symbol}"
            results[key] = []
            for year in YEARS:
                res = probe_year(endpoint, symbol, year)
                results[key].append(res)
                print(key, res, flush=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
