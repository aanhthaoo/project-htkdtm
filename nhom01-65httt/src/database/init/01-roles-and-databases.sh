#!/bin/sh
# Chạy một lần khi khởi tạo cụm PostgreSQL (volume rỗng).
# Tạo các tài khoản phụ và hai database phụ cho Superset và n8n.
# Chỉ dùng cú pháp POSIX sh (image alpine không có bash).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v readonly_pw="$BI_READONLY_PASSWORD" \
  -v app_pw="$BI_APP_PASSWORD" <<'EOSQL'
-- bi_readonly: chỉ đọc schema dw (dành cho Superset)
CREATE ROLE bi_readonly LOGIN PASSWORD :'readonly_pw';
-- bi_app: backend, đọc dw và ghi schema app
CREATE ROLE bi_app LOGIN PASSWORD :'app_pw';

-- Database siêu dữ liệu của các dịch vụ khác
CREATE DATABASE superset;
CREATE DATABASE n8n;
EOSQL
