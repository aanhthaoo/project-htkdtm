from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_health_ok_khi_db_ket_noi_duoc(monkeypatch):
    monkeypatch.setattr(main.db, "check_database", lambda: None)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_503_khi_db_loi(monkeypatch):
    def loi():
        raise ConnectionError("khong ket noi duoc")

    monkeypatch.setattr(main.db, "check_database", loi)

    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "down"
    # Không lộ thông điệp lỗi chi tiết (có thể chứa thông tin kết nối)
    assert "khong ket noi duoc" not in str(body)
