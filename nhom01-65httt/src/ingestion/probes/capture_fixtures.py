"""Lưu phản hồi mẫu của từng nguồn vào tests/fixtures/ để unit test sau này không cần gọi mạng (N2).

Chạy:  python src/ingestion/probes/capture_fixtures.py
Cần:   pip install feedparser
Phản hồi được rút gọn (vài dòng) để tệp nhỏ, giữ nguyên cấu trúc.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import build_url, get_json, http_get, polite_sleep  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures"
CAFEF = "https://cafef.vn/du-lieu/ajax/pagenew/datahistory/"
HEADERS = {"Referer": "https://cafef.vn/"}


def save_json(rel: str, obj) -> None:
    path = FIXTURES / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved", rel)


def get_cafef_nonempty(url: str, tries: int = 5):
    """API CafeF thỉnh thoảng trả TotalCount = 0 dù có dữ liệu; thử lại có chờ."""
    data = None
    for attempt in range(tries):
        _, data = get_json(url, HEADERS)
        polite_sleep(2 + attempt * 2)
        if data and data.get("Data", {}).get("TotalCount"):
            return data
    raise RuntimeError(f"CafeF vẫn trả rỗng sau {tries} lần thử: {url}")


def cafef_samples() -> None:
    # Cùng khoảng ngày 02-10/01/2024 (định dạng tháng/ngày/năm) để đối chiếu 3 endpoint
    params = {"StartDate": "01/02/2024", "EndDate": "01/10/2024", "PageIndex": 1, "PageSize": 5}
    for name, endpoint in {
        "price": "pricehistory",
        "foreign": "gdkhoingoai",
        "prop": "gdtudoanh",
    }.items():
        data = get_cafef_nonempty(
            build_url(CAFEF + endpoint + ".ashx", {"Symbol": "VNM", **params})
        )
        save_json(f"cafef/{name}_VNM_2024-01.json", data)
        polite_sleep()
    # Chỉ số VN-Index
    data = get_cafef_nonempty(
        build_url(CAFEF + "pricehistory.ashx", {"Symbol": "VNINDEX", **params})
    )
    save_json("cafef/price_VNINDEX_2024-01.json", data)
    polite_sleep()


def vietcap_samples() -> None:
    _, symbols = get_json("https://trading.vietcap.com.vn/api/price/symbols/getAll")
    stocks = [s for s in symbols if s["type"] == "STOCK" and s["board"] in ("HSX", "HNX", "UPCOM")]
    save_json("vietcap/symbols_getAll_sample.json", stocks[:15])
    polite_sleep()
    _, vn30 = get_json("https://trading.vietcap.com.vn/api/price/symbols/getByGroup?group=VN30")
    save_json("vietcap/vn30_group.json", vn30)
    polite_sleep()


def vndirect_samples() -> None:
    """VNDirect finfo: cùng khoảng 02-10/01/2024 để đối chiếu với CafeF."""
    base = "https://api-finfo.vndirect.com.vn/v4/"
    for name, endpoint, key in (
        ("price", "stock_prices", "date"),
        ("foreign", "foreigns", "tradingDate"),
        ("prop", "proprietary_trading", "date"),
    ):
        url = (
            f"{base}{endpoint}?q=code:VNM~{key}:gte:2024-01-02~{key}:lte:2024-01-10"
            f"&size=5000&sort={key}:asc"
        )
        _, data = get_json(url)
        save_json(f"vndirect/{name}_VNM_2024-01.json", data)
        polite_sleep(2)
    _, company = get_json("https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/VNM")
    info = company["data"]
    keep = (
        "ticker",
        "icbCodeLv2",
        "icbCodeLv4",
        "sector",
        "marketCap",
        "issueShare",
        "listingDate",
        "maximumForeignPercentage",
        "freeFloatPercentage",
    )
    save_json("vietcap/company_VNM_sample.json", {k: info.get(k) for k in keep})
    polite_sleep(2)


def rss_samples() -> None:
    import feedparser

    feeds = {
        "vneconomy": "https://vneconomy.vn/chung-khoan.rss",
        "vietstock": "https://vietstock.vn/830/chung-khoan/co-phieu.rss",
        "vnexpress": "https://vnexpress.net/rss/kinh-doanh.rss",
        "tnck": "https://www.tinnhanhchungkhoan.vn/rss/home.rss",
    }
    for name, url in feeds.items():
        _, body = http_get(url)
        feed = feedparser.parse(body)
        items = [
            {
                "title": e.get("title"),
                "link": e.get("link"),
                "published": e.get("published"),
                "summary": (e.get("summary") or "")[:300],
                "tags": [t.get("term") for t in e.get("tags", [])],
            }
            for e in feed.entries[:3]
        ]
        save_json(f"rss/{name}_sample.json", items)
        polite_sleep()


if __name__ == "__main__":
    cafef_samples()
    vietcap_samples()
    vndirect_samples()
    rss_samples()
