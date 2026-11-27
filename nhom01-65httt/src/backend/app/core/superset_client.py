"""Gọi API Superset từ backend: lấy mã nhúng dashboard và cấp guest token cho trình duyệt.

Backend đăng nhập Superset bằng tài khoản dịch vụ (admin) và chỉ trả cho trình duyệt một guest token ngắn hạn,
giới hạn ở đúng một dashboard; trình duyệt không bao giờ thấy mật khẩu Superset.
"""

import time

import httpx

from app.config import get_settings
from app.core.errors import ApiError

_token_cache: dict = {"token": None, "expires": 0.0}


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().superset_url, timeout=20)


def _admin_token(client: httpx.Client) -> str:
    if _token_cache["token"] and _token_cache["expires"] > time.time():
        return _token_cache["token"]
    s = get_settings()
    r = client.post(
        "/api/v1/security/login",
        json={
            "username": s.superset_admin_user,
            "password": s.superset_admin_password,
            "provider": "db",
            "refresh": False,
        },
    )
    r.raise_for_status()
    _token_cache.update(token=r.json()["access_token"], expires=time.time() + 600)
    return _token_cache["token"]


def embedded_uuid(slug: str) -> str:
    """Mã nhúng (uuid) của dashboard theo slug; 404 nếu chưa bật nhúng."""
    try:
        with _client() as client:
            token = _admin_token(client)
            r = client.get(
                f"/api/v1/dashboard/{slug}/embedded", headers={"Authorization": f"Bearer {token}"}
            )
            if r.status_code == 404:
                raise ApiError(404, "dashboard_not_embedded", f"Dashboard {slug} chưa bật nhúng")
            r.raise_for_status()
            return r.json()["result"]["uuid"]
    except httpx.HTTPError as exc:
        raise ApiError(502, "superset_unavailable", "Không kết nối được Superset") from exc


def guest_token(dashboard_uuid: str, username: str) -> str:
    try:
        with _client() as client:
            token = _admin_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            csrf = client.get("/api/v1/security/csrf_token/", headers=headers)
            csrf.raise_for_status()
            headers["X-CSRFToken"] = csrf.json()["result"]
            headers["Referer"] = get_settings().superset_url
            r = client.post(
                "/api/v1/security/guest_token/",
                headers=headers,
                json={
                    "user": {"username": username, "first_name": "Khách", "last_name": "Web"},
                    "resources": [{"type": "dashboard", "id": dashboard_uuid}],
                    "rls": [],
                },
            )
            r.raise_for_status()
            return r.json()["token"]
    except httpx.HTTPError as exc:
        raise ApiError(502, "superset_unavailable", "Không cấp được token nhúng dashboard") from exc
