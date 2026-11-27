#!/bin/sh
# Khởi tạo siêu dữ liệu Superset rồi chạy máy chủ. Các lệnh đều chạy lại được nhiều lần.
set -e

superset db upgrade

superset fab create-admin \
  --username "${SUPERSET_ADMIN_USER:-admin}" \
  --firstname Admin \
  --lastname User \
  --email admin@example.com \
  --password "${SUPERSET_ADMIN_PASSWORD}" || echo "Tai khoan admin da ton tai, bo qua."

superset init

exec /usr/bin/run-server.sh
