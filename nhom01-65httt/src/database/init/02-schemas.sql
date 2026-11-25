-- Các schema của hệ thống (chạy trong database POSTGRES_DB, bởi tài khoản bi_admin)
--   raw : dữ liệu thô nguyên trạng từ nguồn, kèm nguồn và thời điểm thu thập
--   stg : dữ liệu đã làm sạch, chuẩn hóa (đầu vào của dbt)
--   dw  : kho dữ liệu Star Schema (dbt xây dựng) và nhật ký chất lượng
--   app : dữ liệu vận hành của website (người dùng, theo dõi, cảnh báo...)

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS app;

COMMENT ON SCHEMA raw IS 'Du lieu tho nguyen trang tu nguon';
COMMENT ON SCHEMA stg IS 'Du lieu da lam sach, chuan hoa';
COMMENT ON SCHEMA dw  IS 'Kho du lieu Star Schema (dbt)';
COMMENT ON SCHEMA app IS 'Du lieu van hanh cua website';

-- Nhật ký chất lượng dữ liệu: mọi bước kiểm tra (ETL, đối chiếu chéo, dbt test) ghi vào đây
CREATE TABLE IF NOT EXISTS dw.dq_log (
    id              BIGSERIAL PRIMARY KEY,
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_id          TEXT,
    layer           TEXT NOT NULL CHECK (layer IN ('raw', 'stg', 'dw', 'ml')),
    source          TEXT,
    check_name      TEXT NOT NULL,
    target_table    TEXT,
    business_date   DATE,
    severity        TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    passed          BOOLEAN NOT NULL,
    metric_value    NUMERIC,
    threshold_value NUMERIC,
    details         JSONB
);

CREATE INDEX IF NOT EXISTS ix_dq_log_logged_at ON dw.dq_log (logged_at DESC);
CREATE INDEX IF NOT EXISTS ix_dq_log_check_date ON dw.dq_log (check_name, business_date);

-- Phân quyền
-- bi_readonly: đọc dw
GRANT USAGE ON SCHEMA dw TO bi_readonly, bi_app;
GRANT SELECT ON ALL TABLES IN SCHEMA dw TO bi_readonly, bi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA dw GRANT SELECT ON TABLES TO bi_readonly, bi_app;

-- bi_app: ghi schema app
GRANT USAGE, CREATE ON SCHEMA app TO bi_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO bi_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO bi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO bi_app;
