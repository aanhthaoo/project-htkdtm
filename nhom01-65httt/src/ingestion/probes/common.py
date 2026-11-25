"""Tiện ích dùng chung cho các script kiểm chứng nguồn dữ liệu (N2).

Nguyên tắc: User-Agent hợp lệ, giãn cách giữa các request, thử lại khi nguồn trả rỗng/lỗi tạm thời.
"""

import gzip
import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0 (HTKDTM-student-project; academic use only)"
DELAY_SECONDS = 1.5


def http_get(
    url: str, headers: dict[str, str] | None = None, timeout: int = 60
) -> tuple[int, bytes]:
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _decode_body(resp.read(), resp.headers.get("Content-Encoding"))
    except urllib.error.HTTPError as exc:
        return exc.code, _decode_body(exc.read(), exc.headers.get("Content-Encoding"))


def _decode_body(body: bytes, content_encoding: str | None) -> bytes:
    """Một số máy chủ (VnEconomy, Vietcap) luôn nén gzip dù không được yêu cầu."""
    if content_encoding and "gzip" in content_encoding.lower():
        try:
            return gzip.decompress(body)
        except gzip.BadGzipFile:  # một số máy chủ khai báo gzip nhưng gửi dữ liệu thường
            return body
    return body


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 60):
    status, body = http_get(url, headers, timeout)
    return status, json.loads(body.decode("utf-8")) if body else None


def polite_sleep(seconds: float = DELAY_SECONDS) -> None:
    time.sleep(seconds)


def build_url(base: str, params: dict) -> str:
    return base + "?" + urllib.parse.urlencode(params)
