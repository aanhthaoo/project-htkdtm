"""Tạo tài khoản chủ sở hữu n8n lần đầu (n8n không đọc tài khoản từ biến môi trường).

Chạy từ thư mục nhom01-65httt/ khi n8n đang chạy:  python src/n8n/setup_owner.py
Đọc N8N_OWNER_EMAIL, N8N_OWNER_PASSWORD, N8N_PORT từ .env. Chạy lại an toàn: nếu đã có chủ sở hữu thì chỉ báo lại.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in (".env.example", ".env"):
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip()
    return values


def call(url: str, payload: dict | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def main() -> int:
    env = load_env()
    base = f"http://127.0.0.1:{env.get('N8N_PORT', '5678')}"
    email, password = env["N8N_OWNER_EMAIL"], env["N8N_OWNER_PASSWORD"]
    _, settings = call(f"{base}/rest/settings")
    if not settings["data"]["userManagement"]["showSetupOnFirstLoad"]:
        print("n8n đã có chủ sở hữu, không tạo lại.")
    else:
        status, body = call(
            f"{base}/rest/owner/setup",
            {"email": email, "firstName": "Quản trị", "lastName": "Hệ thống", "password": password},
        )
        if status != 200:
            print(f"Tạo chủ sở hữu thất bại: HTTP {status} {body}")
            return 1
        print(f"Đã tạo chủ sở hữu n8n: {email}")
    status, _ = call(f"{base}/rest/login", {"email": email, "password": password})
    print("Đăng nhập thử:", "thành công" if status == 200 else f"thất bại (HTTP {status})")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
