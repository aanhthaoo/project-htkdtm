"""Kiểm chứng API VNDirect (finfo) và API công ty của Vietcap iQ (N2).

VNDirect trả toàn bộ lịch sử của một mã trong MỘT lần gọi (đã thử tới 1.554 dòng), khác với API
CafeF chỉ trả 30 dòng mỗi trang. Script đo độ phủ lịch sử trên các mã mẫu thuộc 3 sàn,
cả mã đã hủy niêm yết, và in thông tin ngành/vốn hóa từ Vietcap iQ.

Chạy:  python src/ingestion/probes/probe_vndirect.py [--out ket_qua.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import get_json, polite_sleep  # noqa: E402

FINFO = "https://api-finfo.vndirect.com.vn/v4/"
IQ_COMPANY = "https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/"
START = "2020-09-01"

# (endpoint, tên trường ngày)
ENDPOINTS = {
    "price": ("stock_prices", "date"),
    "foreign": ("foreigns", "tradingDate"),
    "prop": ("proprietary_trading", "date"),
}
SAMPLE = {
    "HOSE": ["VNM", "VCB", "HPG"],
    "HNX": ["SHS", "PVS"],
    "UPCOM": ["BSR", "ACV"],
    "DELISTED": ["QLT", "NGC"],
}


def fetch_history(
    endpoint: str, date_key: str, code: str, start: str = START, end: str = "2026-12-31"
):
    query = f"code:{code}~{date_key}:gte:{start}~{date_key}:lte:{end}"
    url = f"{FINFO}{endpoint}?q={query}&size=5000&sort={date_key}:asc"
    status, data = get_json(url)
    polite_sleep(2)
    return status, (data or {}).get("data", [])


def probe_symbol(code: str) -> dict:
    result = {}
    for name, (endpoint, date_key) in ENDPOINTS.items():
        status, rows = fetch_history(endpoint, date_key, code)
        result[name] = {
            "status": status,
            "rows": len(rows),
            "first": rows[0][date_key] if rows else None,
            "last": rows[-1][date_key] if rows else None,
        }
    return result


def probe_company(code: str) -> dict:
    status, data = get_json(IQ_COMPANY + code)
    polite_sleep(2)
    info = (data or {}).get("data") or {}
    keys = (
        "ticker",
        "icbCodeLv2",
        "icbCodeLv4",
        "sector",
        "marketCap",
        "issueShare",
        "listingDate",
    )
    return {"status": status, **{k: info.get(k) for k in keys}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="vndirect_probe_result.json")
    args = parser.parse_args()
    results: dict = {}
    for group, codes in SAMPLE.items():
        for code in codes:
            res = {"history": probe_symbol(code)}
            if group != "DELISTED":
                res["company"] = probe_company(code)
            results[f"{group}:{code}"] = res
            print(group, code, json.dumps(res, ensure_ascii=False), flush=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
