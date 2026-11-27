"""Kiểm thử API backend trên cơ sở dữ liệu thật (cần PostgreSQL đang chạy và dw đã có dữ liệu).

Chạy:  pytest -m smoke tests/smoke/test_api.py
Mỗi test tạo người dùng riêng (email test-*@example.com) và dọn sau khi xong.
Phủ: đăng ký/đăng nhập đúng và sai, mật khẩu không lưu dạng thô, token hết hạn, phân quyền 3 vai trò,
contract (mỗi endpoint trả đúng schema, danh sách endpoint khớp tài liệu), webhook nội bộ.
"""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import security
from app.db import get_engine
from app.main import app

pytestmark = pytest.mark.smoke

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Mat-khau-thu-nghiem-1"


@pytest.fixture(scope="module")
def client():
    try:
        get_engine().connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("Không kết nối được PostgreSQL")
    with TestClient(app) as c:
        n = (
            get_engine()
            .connect()
            .execute(text("SELECT count(*) FROM dw.fact_money_flow"))
            .scalar_one()
        )
        if not n:
            pytest.skip("dw chưa có dữ liệu")
        yield c
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM app.users WHERE email LIKE 'test-%@example.com'"))
        conn.execute(
            text("DELETE FROM app.etl_runs WHERE requested_by = 'n8n' AND job LIKE 'test-%'")
        )


def new_email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


def register(client, email=None, password=PASSWORD, role="investor"):
    email = email or new_email()
    r = client.post(
        "/api/auth/register", json={"email": email, "password": password, "full_name": "Người Thử"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    if role != "investor":
        with get_engine().begin() as conn:
            conn.execute(
                text("UPDATE app.users SET role = :r WHERE id = :i"),
                {"r": role, "i": body["user"]["id"]},
            )
        body["access_token"] = security.create_token(body["user"]["id"], role)[0]
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    body["email"] = email
    return body


@pytest.fixture()
def investor(client):
    return register(client)


@pytest.fixture()
def admin(client):
    return register(client, role="admin")


# ---------------- Đăng ký, đăng nhập ----------------
def test_dang_ky_tao_nha_dau_tu_va_tra_token(client):
    u = register(client)
    assert u["user"]["role"] == "investor"
    assert u["token_type"] == "bearer" and u["expires_in"] == 3600
    assert "password" not in json.dumps(u).lower().replace("password_hash", "")


def test_mat_khau_khong_luu_dang_tho_trong_co_so_du_lieu(client):
    u = register(client)
    with get_engine().connect() as conn:
        stored = conn.execute(
            text("SELECT password_hash FROM app.users WHERE id = :i"), {"i": u["user"]["id"]}
        ).scalar_one()
    assert stored != PASSWORD and PASSWORD not in stored
    assert stored.startswith("$2")


def test_dang_ky_trung_email_khong_phan_biet_hoa_thuong(client):
    u = register(client)
    r = client.post("/api/auth/register", json={"email": u["email"].upper(), "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "khong-phai-email", "password": PASSWORD},
        {"email": "test-x@example.com", "password": "ngan"},
        {"email": "test-x@example.com"},
    ],
)
def test_dang_ky_du_lieu_sai_bi_tu_choi_voi_dinh_dang_loi_chuan(client, payload):
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error" and err["details"]


def test_dang_nhap_dung(client):
    u = register(client)
    r = client.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == u["email"]
    with get_engine().connect() as conn:
        assert conn.execute(
            text("SELECT last_login_at IS NOT NULL FROM app.users WHERE id = :i"),
            {"i": u["user"]["id"]},
        ).scalar_one()


def test_dang_nhap_sai_mat_khau_va_sai_email_cung_thong_bao(client):
    u = register(client)
    wrong_pw = client.post(
        "/api/auth/login", json={"email": u["email"], "password": "sai-mat-khau-1"}
    )
    wrong_email = client.post("/api/auth/login", json={"email": new_email(), "password": PASSWORD})
    assert wrong_pw.status_code == wrong_email.status_code == 401
    assert wrong_pw.json() == wrong_email.json()
    assert wrong_pw.json()["error"]["code"] == "invalid_credentials"


def test_tai_khoan_bi_khoa_khong_dang_nhap_duoc_va_token_cu_het_hieu_luc(client):
    u = register(client)
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE app.users SET is_active = false WHERE id = :i"), {"i": u["user"]["id"]}
        )
    assert (
        client.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD}).status_code
        == 403
    )
    assert client.get("/api/auth/me", headers=u["headers"]).status_code == 401


# ---------------- Token ----------------
def test_me_voi_token_hop_le(client, investor):
    r = client.get("/api/auth/me", headers=investor["headers"])
    assert r.status_code == 200 and r.json()["email"] == investor["email"]


def test_me_khong_co_token_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"


def test_token_rac_va_token_ky_sai_khoa_401(client):
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer rac"}).json()["error"]["code"]
        == "invalid_token"
    )
    import jwt

    forged = jwt.encode(
        {"sub": "1", "role": "admin", "exp": 4102444800},
        "khoa-gia-mao-khoa-gia-mao-123456",
        "HS256",
    )
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_token_het_han_401_token_expired(client, investor):
    expired, _ = security.create_token(investor["user"]["id"], "investor", ttl_minutes=-1)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_vai_tro_trong_token_khong_duoc_tin_ma_lay_tu_co_so_du_lieu(client, investor):
    """Token ghi role admin nhưng người dùng thật là investor: vẫn bị 403 ở endpoint quản trị."""
    token, _ = security.create_token(investor["user"]["id"], "admin")
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


# ---------------- Phân quyền: khách < nhà đầu tư < quản trị ----------------
CONTRACT = [
    # (method, đường dẫn, vai trò tối thiểu, body)
    ("GET", "/api/market/overview", "guest", None),
    ("GET", "/api/sectors/flow", "investor", None),
    ("GET", "/api/sectors/8300", "investor", None),
    ("GET", "/api/stocks?query=VN", "investor", None),
    ("GET", "/api/stocks/VNM", "investor", None),
    ("GET", "/api/stocks/VNM/prices", "investor", None),
    ("GET", "/api/stocks/VNM/flow", "investor", None),
    ("GET", "/api/stocks/top-net", "investor", None),
    ("GET", "/api/news", "guest", None),
    ("GET", "/api/news/highlights", "guest", None),
    ("GET", "/api/macro/series?codes=USDVND,DXY", "investor", None),
    ("GET", "/api/macro/correlation", "investor", None),
    ("GET", "/api/predictions", "investor", None),
    ("GET", "/api/predictions/accuracy", "investor", None),
    ("GET", "/api/recommendations", "investor", None),
    ("GET", "/api/watchlist", "investor", None),
    ("POST", "/api/chat", "investor", {"message": "Dòng tiền ngân hàng tuần này?"}),
    ("GET", "/api/admin/users", "admin", None),
    ("GET", "/api/admin/sources", "admin", None),
    ("GET", "/api/admin/etl/runs", "admin", None),
    ("GET", "/api/admin/dq-log", "admin", None),
    ("GET", "/api/admin/models", "admin", None),
]
RANK = {"guest": 0, "investor": 1, "admin": 2}


@pytest.mark.parametrize(("method", "path", "min_role", "body"), CONTRACT)
def test_phan_quyen_tung_endpoint(client, investor, admin, method, path, min_role, body):
    actors = {"guest": {}, "investor": investor["headers"], "admin": admin["headers"]}
    for role, headers in actors.items():
        r = client.request(method, path, headers=headers, json=body)
        if RANK[role] >= RANK[min_role]:
            assert r.status_code == 200, f"{role} {method} {path}: {r.status_code} {r.text[:300]}"
        elif role == "guest":
            assert r.status_code == 401, f"khách {method} {path}: {r.status_code}"
        else:
            assert r.status_code == 403, f"{role} {method} {path}: {r.status_code}"


def test_khach_chi_thay_toi_da_5_tin_va_nha_dau_tu_thay_day_du(client, investor):
    guest = client.get("/api/news?page_size=50&page=3").json()
    assert guest["page"] == 1 and len(guest["items"]) <= 5 and guest["total"] > 5
    full = client.get("/api/news?page_size=20", headers=investor["headers"]).json()
    assert len(full["items"]) == 20


def test_tin_khong_tra_toan_van(client):
    item = client.get("/api/news").json()["items"][0]
    assert set(item) == {
        "title",
        "source",
        "published_at",
        "session_date",
        "sentiment_label",
        "sentiment_score",
        "url",
    }


def test_phan_trang_toi_da_100(client, investor):
    assert client.get("/api/stocks?page_size=101", headers=investor["headers"]).status_code == 422
    assert client.get("/api/stocks?page=0", headers=investor["headers"]).status_code == 422


def test_nha_dau_tu_khong_vao_duoc_quan_tri_va_khong_tu_nang_quyen(client, investor, admin):
    assert client.get("/api/admin/users", headers=investor["headers"]).status_code == 403
    r = client.patch(
        f"/api/admin/users/{investor['user']['id']}",
        headers=investor["headers"],
        json={"role": "admin"},
    )
    assert r.status_code == 403
    r = client.patch(
        f"/api/admin/users/{admin['user']['id']}",
        headers=admin["headers"],
        json={"role": "investor"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "self_demotion"


def test_quan_tri_khoa_nguoi_dung(client, investor, admin):
    r = client.patch(
        f"/api/admin/users/{investor['user']['id']}",
        headers=admin["headers"],
        json={"is_active": False},
    )
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert client.get("/api/auth/me", headers=investor["headers"]).status_code == 401


# ---------------- Nội dung dữ liệu thật ----------------
def test_tong_quan_thi_truong_khop_kho(client):
    body = client.get("/api/market/overview").json()
    with get_engine().connect() as conn:
        d, close, value = conn.execute(
            text(
                "SELECT trade_date, vnindex_close, stock_value_bn FROM dw.mv_market_daily_kpi ORDER BY trade_date DESC LIMIT 1"
            )
        ).one()
        net = conn.execute(
            text(
                "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f JOIN dw.dim_investor_type it USING (investor_type_key) "
                "WHERE it.code = 'FOREIGN' AND f.trade_date = :d"
            ),
            {"d": d},
        ).scalar_one()
    assert body["date"] == str(d)
    assert body["vnindex"]["close"] == pytest.approx(close)
    assert body["total_value_bn"] == pytest.approx(value)
    assert body["foreign"]["net_bn"] == pytest.approx(net)
    assert "disclaimer" in body
    assert client.get("/api/market/overview?date=1990-01-01").status_code == 404


def test_dong_tien_nganh_khop_kho(client, investor):
    body = client.get(
        "/api/sectors/flow?granularity=week&investor_type=FOREIGN", headers=investor["headers"]
    ).json()
    assert len(body["periods"]) >= 10 and len(body["sectors"]) >= 15
    assert all(len(s["net_bn"]) == len(body["periods"]) for s in body["sectors"])
    sector = body["sectors"][0]
    idx = len(body["periods"]) - 2
    with get_engine().connect() as conn:
        expected = conn.execute(
            text(
                "SELECT sum(f.net_value_bn) FROM dw.fact_money_flow f JOIN dw.dim_time t USING (date_key) "
                "JOIN dw.dim_stock d USING (stock_key) JOIN dw.dim_sector s USING (sector_key) "
                "JOIN dw.dim_investor_type it USING (investor_type_key) "
                "WHERE d.security_type = 'STOCK' AND it.code = 'FOREIGN' AND s.icb_l2_code = :c AND t.week_start_date = :w"
            ),
            {"c": sector["icb_l2_code"], "w": body["periods"][idx]},
        ).scalar_one()
    assert sector["net_bn"][idx] == pytest.approx(expected, abs=0.01)


def test_tra_cuu_ma_va_gia(client, investor):
    h = investor["headers"]
    detail = client.get("/api/stocks/vnm", headers=h).json()
    assert detail["symbol"] == "VNM" and detail["icb_l2_name_vi"]
    assert client.get("/api/stocks/KHONGCO", headers=h).json()["error"]["code"] == "not_found"
    prices = client.get("/api/stocks/VNM/prices", headers=h).json()["items"]
    assert len(prices) > 30
    with get_engine().connect() as conn:
        close = conn.execute(
            text(
                "SELECT p.close_price FROM dw.fact_daily_price p JOIN dw.dim_stock d USING (stock_key) "
                "WHERE d.symbol = 'VNM' AND p.trade_date = :d"
            ),
            {"d": prices[-1]["date"]},
        ).scalar_one()
    assert prices[-1]["close_vnd"] == pytest.approx(close * 1000)


def test_top_mua_rong_sap_xep_dung_chieu(client, investor):
    h = investor["headers"]
    buy = client.get("/api/stocks/top-net?side=buy&period=5", headers=h).json()["items"]
    sell = client.get("/api/stocks/top-net?side=sell&period=5", headers=h).json()["items"]
    assert [i["net_bn"] for i in buy] == sorted((i["net_bn"] for i in buy), reverse=True)
    assert [i["net_bn"] for i in sell] == sorted(i["net_bn"] for i in sell)
    assert buy[0]["net_bn"] > 0 > sell[0]["net_bn"]


def test_macro_series(client, investor):
    body = client.get("/api/macro/series?codes=USDVND,DXY", headers=investor["headers"]).json()
    assert {s["code"] for s in body["series"]} == {"USDVND", "DXY"}
    assert all(len(s["points"]) > 100 for s in body["series"])
    r = client.get("/api/macro/series?codes=KHONGCO", headers=investor["headers"])
    assert r.status_code == 404


def test_khuyen_nghi_that_tu_quy_tac_n9_co_disclaimer_va_du_19_nganh(client, investor):
    h = investor["headers"]
    body = client.get("/api/recommendations", headers=h).json()
    assert body["stub"] is False and "disclaimer" in body and body["rule_version"]
    assert len(body["items"]) == 19
    scores = [i["score"] for i in body["items"]]
    assert scores == sorted(scores, reverse=True)  # xếp theo điểm giảm dần
    for i in body["items"]:
        assert i["action"] in {"increase", "decrease", "hold"} and i["signal"] in {
            "none",
            "reversal",
            "mismatch",
        }
        assert i["confidence"] in {"high", "medium", "low"} and i["reason"]
        assert (i["action"] == "increase") == (i["score"] >= 0.5)
        assert (i["action"] == "decrease") == (i["score"] <= -0.5)
        assert i["signal"] != "mismatch" or any(
            x.endswith(("_outflow", "_inflow")) and x.startswith(("positive", "negative"))
            for x in i["signals"]
        )
    past = client.get("/api/recommendations?week=2024-03-04", headers=h).json()
    assert past["week"] == "2024-03-04" and len(past["items"]) == 19
    assert client.get("/api/recommendations?week=2019-01-07", headers=h).status_code == 404
    assert client.get("/api/recommendations").status_code == 401


def test_tin_tuc_co_nhan_cam_xuc_tu_mo_hinh(client, investor):
    """Bài nhắc mã/ngành có cảm xúc; bài không nhắc mã/ngành nào (khoảng 12%) thì cảm xúc là null."""
    items = client.get("/api/news?page_size=100", headers=investor["headers"]).json()["items"]
    scored = [i for i in items if i["sentiment_label"] is not None]
    assert len(scored) >= 0.6 * len(items)
    assert all(i["sentiment_label"] in {"negative", "neutral", "positive"} for i in scored)
    assert all(-1 <= i["sentiment_score"] <= 1 for i in scored)
    assert all((i["sentiment_label"] is None) == (i["sentiment_score"] is None) for i in items)
    top = client.get("/api/news/highlights").json()["items"]
    assert top and all(i["sentiment_label"] for i in top)  # tin nổi bật luôn nhắc nhiều mã


def test_du_bao_that_tu_mo_hinh_va_co_gia_tri_thuc(client, investor):
    h = investor["headers"]
    body = client.get("/api/predictions", headers=h).json()
    assert body["stub"] is False and body["model"]["name"] == "xgb_sector_flow"
    assert len(body["items"]) == 19 and "disclaimer" in body
    assert all(0 <= i["prob_inflow"] <= 1 for i in body["items"])
    # tuần mới nhất có thể là dự báo trực tiếp (chưa có giá trị thực): khi đó mọi dòng cùng chưa có
    assert body["evaluated"] == all(i["actual_class"] for i in body["items"])
    assert sorted(i["rank"] for i in body["items"]) == list(range(1, 20))
    by_rank = sorted(body["items"], key=lambda i: i["rank"])
    assert [i["predicted_net_bn"] for i in by_rank] == sorted(
        (i["predicted_net_bn"] for i in body["items"]), reverse=True
    )  # hạng 1 = giá trị ròng dự báo cao nhất
    past = client.get("/api/predictions?week=2023-01-09", headers=h).json()
    assert past["target_week_start"] == "2023-01-09"
    assert past["evaluated"] is True and all(i["actual_class"] for i in past["items"])
    assert client.get("/api/predictions?week=2019-01-07", headers=h).status_code == 404
    assert client.get("/api/predictions?horizon=3", headers=h).status_code == 404


def test_do_chinh_xac_du_bao_khop_chi_so_mo_hinh(client, investor, admin):
    acc = client.get("/api/predictions/accuracy?weeks=200", headers=investor["headers"]).json()
    assert acc["stub"] is False and len(acc["points"]) >= 100
    models = client.get("/api/admin/models", headers=admin["headers"]).json()
    forecast = next(m for m in models["items"] if m["task"] == "forecast")
    assert acc["overall_accuracy"] == pytest.approx(
        forecast["metrics"]["model"]["accuracy"], abs=1e-9
    )
    assert {m["task"] for m in models["items"]} >= {"forecast", "cluster"} and models[
        "stub"
    ] is False


def test_nhan_cum_hien_trong_chi_tiet_ma(client, investor):
    detail = client.get("/api/stocks/VNM", headers=investor["headers"]).json()
    assert detail["cluster_label"]


# ---------------- Theo dõi, cảnh báo ----------------
def test_danh_sach_theo_doi_them_trung_xoa_va_khong_xoa_cua_nguoi_khac(client, investor):
    h = investor["headers"]
    r = client.post(
        "/api/watchlist", headers=h, json={"entity_type": "STOCK", "entity_code": "vnm"}
    )
    assert r.status_code == 201 and r.json()["entity_code"] == "VNM"
    item_id = r.json()["id"]
    assert (
        client.post(
            "/api/watchlist", headers=h, json={"entity_type": "STOCK", "entity_code": "VNM"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/watchlist", headers=h, json={"entity_type": "STOCK", "entity_code": "KHONGCO"}
        ).status_code
        == 404
    )
    assert [i["entity_code"] for i in client.get("/api/watchlist", headers=h).json()] == ["VNM"]
    other = register(client)
    assert client.delete(f"/api/watchlist/{item_id}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/watchlist/{item_id}", headers=h).status_code == 204
    assert client.get("/api/watchlist", headers=h).json() == []


# ---------------- Webhook nội bộ (khóa dịch vụ) ----------------
def service_headers():
    import os

    return {"X-Service-Key": os.environ["SERVICE_KEY"]}


def test_webhook_noi_bo_can_khoa_dich_vu(client, investor):
    body = {"alert_type": "flow_reversal", "entity_type": "SECTOR", "entity_code": "8300"}
    assert client.post("/api/internal/alerts/dispatch", json=body).status_code == 401
    assert (
        client.post(
            "/api/internal/alerts/dispatch", json=body, headers={"X-Service-Key": "sai"}
        ).status_code
        == 401
    )
    # token của người dùng (kể cả admin) không thay được khóa dịch vụ
    assert (
        client.post(
            "/api/internal/alerts/dispatch", json=body, headers=investor["headers"]
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/internal/alerts/dispatch", json=body, headers=service_headers()
        ).status_code
        == 200
    )


def test_n8n_nhan_danh_sach_nguoi_dang_ky_canh_bao(client, investor):
    sub = client.post(
        "/api/alerts/subscriptions",
        headers=investor["headers"],
        json={"entity_type": "SECTOR", "entity_code": "8300", "alert_type": "flow_reversal"},
    )
    assert sub.status_code == 201
    body = {"alert_type": "flow_reversal", "entity_type": "SECTOR", "entity_code": "8300"}
    r = client.post("/api/internal/alerts/dispatch", json=body, headers=service_headers()).json()
    assert investor["email"] in [x["email"] for x in r["recipients"]] and r["count"] == len(
        r["recipients"]
    )
    other_type = dict(body, alert_type="negative_news")
    r2 = client.post(
        "/api/internal/alerts/dispatch", json=other_type, headers=service_headers()
    ).json()
    assert investor["email"] not in [x["email"] for x in r2["recipients"]]
    assert (
        client.delete(
            f"/api/alerts/subscriptions/{sub.json()['id']}", headers=investor["headers"]
        ).status_code
        == 204
    )


def test_n8n_ghi_su_kien_etl_loi_vao_nhat_ky(client, admin):
    job = f"test-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/internal/etl/events",
        headers=service_headers(),
        json={"job": job, "status": "failed", "message": "Nguồn CafeF không phản hồi"},
    )
    assert r.status_code == 201
    runs = client.get("/api/admin/etl/runs?status=failed", headers=admin["headers"]).json()["items"]
    assert any(x["job"] == job and x["trigger_type"] == "n8n" for x in runs)


def test_api_mo_hinh_noi_bo_dung_schema_va_du_lieu_that(client):
    h = service_headers()
    assert client.post("/ml/sentiment", json={"texts": ["a", "b"]}).status_code == 401
    assert client.post("/ml/predict", json={"target_week_start": "2024-03-04"}).status_code == 401
    assert client.post("/ml/cluster", json={"symbols": ["VNM"]}).status_code == 401
    # dự báo: đúng 19 ngành, khớp /api/predictions của cùng tuần
    p = client.post("/ml/predict", json={"target_week_start": "2024-03-04"}, headers=h).json()
    assert p["stub"] is False and len(p["items"]) == 19 and "disclaimer" in p
    assert all(0 <= i["prob_inflow"] <= 1 for i in p["items"])
    assert (
        client.post("/ml/predict", json={"target_week_start": "2019-01-07"}, headers=h).status_code
        == 404
    )
    assert (
        client.post(
            "/ml/predict", json={"target_week_start": "2024-03-04", "horizon_weeks": 2}, headers=h
        ).status_code
        == 404
    )
    # cụm: nhãn thật từ dw, mã lạ là unknown, không phân biệt hoa thường
    c = client.post("/ml/cluster", json={"symbols": ["vnm", "ZZZZ"]}, headers=h).json()
    assert c["stub"] is False and [i["symbol"] for i in c["items"]] == ["VNM", "ZZZZ"]
    assert (
        c["items"][0]["cluster_label"] not in ("unknown", "")
        and c["items"][1]["cluster_label"] == "unknown"
    )
    assert client.post("/ml/cluster", json={"symbols": ["A"] * 501}, headers=h).status_code == 422
    # cảm xúc: điểm thật nếu mô hình và thư viện có trong tiến trình, nếu không là dữ liệu mẫu đúng schema
    s = client.post(
        "/ml/sentiment",
        json={
            "texts": [
                "Công ty báo lãi kỷ lục, khối ngoại mua ròng mạnh",
                "Cổ phiếu bị bán tháo, công ty báo lỗ nặng",
            ]
        },
        headers=h,
    ).json()
    assert len(s["results"]) == 2 and all(-1 <= r["score"] <= 1 for r in s["results"])
    if not s["stub"]:
        assert s["results"][0]["score"] > s["results"][1]["score"]
    assert client.post("/ml/sentiment", json={"texts": ["a"] * 101}, headers=h).status_code == 422


def test_nhat_ky_chat_luong_du_lieu_cho_quan_tri(client, admin):
    body = client.get(
        "/api/admin/dq-log?failed_only=false&severity=error", headers=admin["headers"]
    ).json()
    assert body["total"] > 0 and all(i["severity"] == "error" for i in body["items"])


# ---------------- Contract ----------------
def test_moi_endpoint_cua_contract_co_trong_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    for method, path, _, _ in CONTRACT:
        template = path.split("?")[0]
        # đường dẫn có tham số trong OpenAPI: /api/stocks/{symbol}
        candidates = [template] + [
            p
            for p in paths
            if p.count("/") == template.count("/")
            and all(
                a == b or a.startswith("{")
                for a, b in zip(p.split("/"), template.split("/"), strict=True)
            )
        ]
        assert any(
            method.lower() in paths.get(c, {}) for c in candidates
        ), f"{method} {path} chưa có trong OpenAPI"
    for path in (
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/me",
        "/api/watchlist",
        "/api/alerts/subscriptions",
        "/api/admin/etl/run",
        "/api/internal/alerts/dispatch",
        "/ml/sentiment",
        "/ml/predict",
        "/ml/cluster",
        "/api/superset/embed/{key}",
    ):
        assert path in paths, path


def test_openapi_da_xuat_khop_ban_hien_tai():
    """docs/openapi.json là contract chốt: đổi API thì phải chạy `python src/backend/export_openapi.py` và báo nhóm."""
    exported = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert exported == json.loads(
        json.dumps(app.openapi())
    ), "Chạy: python src/backend/export_openapi.py"


def test_dinh_dang_loi_thong_nhat(client):
    for r in (
        client.get("/api/auth/me"),
        client.get("/api/khong-co"),
        client.post("/api/auth/login", json={}),
    ):
        assert set(r.json()) == {"error"} and {"code", "message"} <= set(r.json()["error"])


# ---------------- Nhúng Superset ----------------
def _superset_up():
    import os

    import httpx

    try:
        return httpx.get(f"{os.environ['SUPERSET_URL']}/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture()
def superset(client):
    if not _superset_up():
        pytest.skip("Superset không chạy")
    r = client.get("/api/superset/embed/overview")
    if r.status_code == 404:
        pytest.skip("Chưa bật nhúng dashboard: chạy python src/superset/provision.py")
    return True


def test_nhung_dashboard_theo_vai_tro(client, superset, investor):
    assert [d["key"] for d in client.get("/api/superset/dashboards").json()] == ["overview"]
    both = client.get("/api/superset/dashboards", headers=investor["headers"]).json()
    assert [d["key"] for d in both] == ["overview", "sector-rotation"]
    guest = client.get("/api/superset/embed/overview")
    assert guest.status_code == 200 and len(guest.json()["guest_token"]) > 50
    assert client.get("/api/superset/embed/sector-rotation").status_code == 401
    assert (
        client.get("/api/superset/embed/sector-rotation", headers=investor["headers"]).status_code
        == 200
    )
    assert (
        client.get("/api/superset/embed/khong-co", headers=investor["headers"]).status_code == 404
    )


def test_guest_token_chi_xem_duoc_dung_dashboard_trong_token(client, superset, investor):
    import os

    import httpx

    base = os.environ["SUPERSET_URL"]
    overview = client.get("/api/superset/embed/overview").json()
    assert (
        client.get("/api/superset/embed/sector-rotation", headers=investor["headers"]).status_code
        == 200
    )
    headers = {"X-GuestToken": overview["guest_token"]}
    ok = httpx.get(f"{base}/api/v1/dashboard/tong-quan-demo/charts", headers=headers, timeout=30)
    assert ok.status_code == 200 and len(ok.json()["result"]) == 2
    denied = httpx.get(
        f"{base}/api/v1/dashboard/luan-chuyen-nganh-demo/charts", headers=headers, timeout=30
    )
    assert denied.status_code in (401, 403, 404), denied.text[:200]


# ---------------- Chạy lại ETL (cần etl-runner) ----------------
def _runner_up():
    import os

    import httpx

    try:
        return httpx.get(f"{os.environ['ETL_RUNNER_URL']}/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def test_quan_tri_chay_lai_etl_va_theo_doi(client, admin, investor):
    if not _runner_up():
        pytest.skip("etl-runner không chạy")
    assert client.post("/api/admin/etl/run", json={"job": "quality"}).status_code == 401
    assert (
        client.post(
            "/api/admin/etl/run", json={"job": "quality"}, headers=investor["headers"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/etl/run", json={"job": "khong-co"}, headers=admin["headers"]
        ).status_code
        == 422
    )
    r = client.post("/api/admin/etl/run", json={"job": "quality"}, headers=admin["headers"])
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    # đang chạy thì yêu cầu thứ hai bị từ chối
    busy = client.post("/api/admin/etl/run", json={"job": "quality"}, headers=admin["headers"])
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "etl_busy"
    import time

    deadline = time.time() + 600
    run = None
    while time.time() < deadline:
        runs = client.get("/api/admin/etl/runs", headers=admin["headers"]).json()["items"]
        run = next(x for x in runs if x["id"] == run_id)
        if run["status"] != "running":
            break
        time.sleep(5)
    assert run["status"] == "success", run
    assert [s["name"] for s in run["steps"]] == ["dbt_test", "quality"]
    assert all(s["status"] == "success" for s in run["steps"])
    assert run["requested_by"] == admin["email"] and run["trigger_type"] == "admin"


def test_thoi_gian_phan_hoi_khuyen_nghi_va_api_mo_hinh_hop_ly(client, investor):
    import time

    h = service_headers()
    calls = [
        lambda: client.get("/api/recommendations", headers=investor["headers"]),
        lambda: client.post("/ml/predict", json={"target_week_start": "2024-03-04"}, headers=h),
        lambda: client.post("/ml/cluster", json={"symbols": ["VNM", "FPT", "HPG"]}, headers=h),
    ]
    for call in calls:
        call()  # khởi động nguội (kết nối, biên dịch truy vấn)
        start = time.perf_counter()
        assert call().status_code == 200
        assert time.perf_counter() - start < 2.0
