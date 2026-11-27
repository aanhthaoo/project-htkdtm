-- Bảng vận hành của website (schema app). Chạy lại nhiều lần không lỗi.
CREATE TABLE IF NOT EXISTS app.users (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'investor' CHECK (role IN ('investor', 'admin')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON app.users (lower(email));

-- Danh sách theo dõi (ngành hoặc mã)
CREATE TABLE IF NOT EXISTS app.watchlist (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('STOCK', 'SECTOR')),
    entity_code TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, entity_type, entity_code)
);

-- Đăng ký cảnh báo email
CREATE TABLE IF NOT EXISTS app.alert_subscriptions (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('STOCK', 'SECTOR')),
    entity_code TEXT NOT NULL,
    alert_type  TEXT NOT NULL CHECK (alert_type IN ('flow_reversal', 'negative_news', 'weekly_digest')),
    channel     TEXT NOT NULL DEFAULT 'email',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, entity_type, entity_code, alert_type)
);

-- Các lần chạy ETL (n8n, người quản trị, lịch). Bộ chạy ETL ghi vào đây.
CREATE TABLE IF NOT EXISTS app.etl_runs (
    id           BIGSERIAL PRIMARY KEY,
    job          TEXT NOT NULL,
    trigger_type TEXT NOT NULL DEFAULT 'manual' CHECK (trigger_type IN ('manual', 'schedule', 'n8n', 'admin')),
    status       TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    requested_by TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    steps        JSONB NOT NULL DEFAULT '[]'::jsonb,
    log_tail     TEXT
);
CREATE INDEX IF NOT EXISTS ix_etl_runs_started ON app.etl_runs (started_at DESC);

-- Nguồn thu thập (quản trị bật/tắt)
CREATE TABLE IF NOT EXISTS app.data_sources (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    is_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    note        TEXT NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO app.data_sources (code, name, kind, note) VALUES
    ('vndirect', 'VNDirect (giá, khối ngoại, tự doanh)', 'api', 'Nguồn chính'),
    ('cafef_index', 'CafeF (VN-Index)', 'api', 'Nguồn VN-Index'),
    ('vietcap', 'Vietcap iQ (ngành ICB, vốn hóa)', 'api', ''),
    ('yfinance', 'yfinance (chỉ số quốc tế)', 'api', ''),
    ('rss', 'RSS (VnEconomy, Vietstock, VnExpress, Tin nhanh CK)', 'rss', ''),
    ('cafef_news', 'CafeF tin (chuyên mục Chứng khoán)', 'crawl', ''),
    ('econvnnews', 'EconVNNews (lịch sử tin 09/2020 - 09/2024)', 'dataset', 'Chỉ nạp một lần')
ON CONFLICT (code) DO NOTHING;
