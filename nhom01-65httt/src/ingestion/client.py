"""HTTP client có giãn cách, thử lại và giải nén gzip (một số máy chủ luôn nén)."""

import gzip
import json
import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (HTKDTM-student-project; academic use only)"


def decode_body(body: bytes, content_encoding: str | None) -> bytes:
    """Giải nén gzip nếu có; một số máy chủ khai báo gzip nhưng gửi dữ liệu thường."""
    if content_encoding and "gzip" in content_encoding.lower():
        try:
            return gzip.decompress(body)
        except gzip.BadGzipFile:
            return body
    return body


class HttpError(RuntimeError):
    pass


class Client:
    """Giãn cách tối thiểu `delay` giây giữa hai request; thử lại có chờ tăng dần."""

    def __init__(
        self,
        delay: float = 1.5,
        retries: int = 4,
        timeout: int = 60,
        headers: dict[str, str] | None = None,
    ):
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self.headers = {"User-Agent": USER_AGENT, **(headers or {})}
        self._last = 0.0

    def _throttle(self) -> None:
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
        """Trả (status, body). Lỗi mạng/5xx/429 được thử lại; 4xx khác trả về luôn."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            req = urllib.request.Request(url, headers={**self.headers, **(headers or {})})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.status, decode_body(
                        resp.read(), resp.headers.get("Content-Encoding")
                    )
            except urllib.error.HTTPError as exc:
                body = decode_body(exc.read(), exc.headers.get("Content-Encoding"))
                if exc.code < 500 and exc.code != 429:
                    return exc.code, body
                last_error = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
            backoff = min(60, 2 ** (attempt + 1))
            log.warning("GET lỗi (%s), thử lại sau %ss: %s", last_error, backoff, url[:120])
            time.sleep(backoff)
        raise HttpError(f"Không tải được sau {self.retries} lần: {url[:200]} ({last_error})")

    def get_json(self, url: str, headers: dict[str, str] | None = None):
        status, body = self.get(url, headers)
        if status != 200:
            raise HttpError(f"HTTP {status}: {url[:200]}")
        return json.loads(body.decode("utf-8"))
