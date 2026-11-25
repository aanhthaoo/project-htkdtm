"""Cấu hình Superset (N1). Cấu hình nhúng iframe và phân quyền sẽ bổ sung ở N7."""

import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DB_URI"]

# Hiển thị theo múi giờ Việt Nam
BABEL_DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
