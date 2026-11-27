"""Cấu hình Superset: múi giờ (N1) và nhúng dashboard vào website có phân quyền (N7)."""

import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DB_URI"]

# Hiển thị theo múi giờ Việt Nam
BABEL_DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"

# --- Nhúng dashboard (website gọi backend để lấy guest token, rồi dùng embedded-sdk) ---
FEATURE_FLAGS = {"EMBEDDED_SUPERSET": True}

# Người dùng "khách" của token nhúng chỉ xem được dashboard ghi trong token, với quyền của vai trò này
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_SECRET = SECRET_KEY
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_EXP_SECONDS = 600

# Cho phép khung iframe từ website (môi trường phát triển); sản xuất nên bật Talisman và đặt frame-ancestors
TALISMAN_ENABLED = False
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "allow_headers": ["*"],
    "resources": ["*"],
    "origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
}
