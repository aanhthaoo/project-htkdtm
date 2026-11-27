-- Các bảng thô (schema raw) của lớp thu thập dữ liệu. Chạy lại được (IF NOT EXISTS).
-- Quy ước: giữ nguyên giá trị nguồn trả về (đơn vị gốc), thêm fetched_at; trường không ánh xạ vào `extra`.

-- Nhật ký chạy: mỗi (nguồn, tác vụ, cửa sổ) một dòng, dùng để tiếp tục từ chỗ dừng
CREATE TABLE IF NOT EXISTS raw.ingestion_run (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    task         TEXT NOT NULL,
    window_key   TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    rows_loaded  BIGINT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    error        TEXT,
    UNIQUE (source, task, window_key)
);

-- ===== VNDirect (nguồn chính): chỉ lấy type = STOCK. Giá nghìn đồng; giá trị tiền bằng đồng =====
CREATE TABLE IF NOT EXISTS raw.vnd_stock_prices (
    code          TEXT NOT NULL,
    trade_date    DATE NOT NULL,
    floor         TEXT,
    type          TEXT,
    quote_time    TEXT,
    basic_price   DOUBLE PRECISION,
    ceiling_price DOUBLE PRECISION,
    floor_price   DOUBLE PRECISION,
    open          DOUBLE PRECISION,
    high          DOUBLE PRECISION,
    low           DOUBLE PRECISION,
    close         DOUBLE PRECISION,
    average       DOUBLE PRECISION,
    ad_open       DOUBLE PRECISION,
    ad_high       DOUBLE PRECISION,
    ad_low        DOUBLE PRECISION,
    ad_close      DOUBLE PRECISION,
    ad_average    DOUBLE PRECISION,
    nm_volume     DOUBLE PRECISION,
    nm_value      DOUBLE PRECISION,
    pt_volume     DOUBLE PRECISION,
    pt_value      DOUBLE PRECISION,
    change        DOUBLE PRECISION,
    ad_change     DOUBLE PRECISION,
    pct_change    DOUBLE PRECISION,
    extra         JSONB,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (code, trade_date)
);

CREATE TABLE IF NOT EXISTS raw.vnd_foreigns (
    code          TEXT NOT NULL,
    trade_date    DATE NOT NULL,
    floor         TEXT,
    type          TEXT,
    buy_val       DOUBLE PRECISION,
    sell_val      DOUBLE PRECISION,
    net_val       DOUBLE PRECISION,
    buy_vol       DOUBLE PRECISION,
    sell_vol      DOUBLE PRECISION,
    net_vol       DOUBLE PRECISION,
    total_room    DOUBLE PRECISION,
    current_room  DOUBLE PRECISION,
    extra         JSONB,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (code, trade_date)
);

CREATE TABLE IF NOT EXISTS raw.vnd_proprietary (
    code             TEXT NOT NULL,
    trade_date       DATE NOT NULL,
    floor            TEXT,
    type             TEXT,
    buying_vol       DOUBLE PRECISION,
    buying_vol_pct   DOUBLE PRECISION,
    selling_vol      DOUBLE PRECISION,
    selling_vol_pct  DOUBLE PRECISION,
    buying_val       DOUBLE PRECISION,
    buying_val_pct   DOUBLE PRECISION,
    selling_val      DOUBLE PRECISION,
    selling_val_pct  DOUBLE PRECISION,
    net_val          DOUBLE PRECISION,
    net_vol          DOUBLE PRECISION,
    extra            JSONB,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (code, trade_date)
);

-- ===== Vietcap =====
CREATE TABLE IF NOT EXISTS raw.vietcap_symbols (
    symbol            TEXT PRIMARY KEY,
    type              TEXT,
    board             TEXT,
    organ_name        TEXT,
    organ_short_name  TEXT,
    product_grp_id    TEXT,
    icb_code2         TEXT,
    payload           JSONB,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.vietcap_groups (
    group_name  TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (group_name, symbol)
);

CREATE TABLE IF NOT EXISTS raw.vietcap_company (
    symbol           TEXT PRIMARY KEY,
    icb_code_lv2     TEXT,
    icb_code_lv4     TEXT,
    sector           TEXT,
    market_cap       DOUBLE PRECISION,
    issue_share      DOUBLE PRECISION,
    listing_date     DATE,
    max_foreign_pct  DOUBLE PRECISION,
    foreigner_pct    DOUBLE PRECISION,
    free_float_pct   DOUBLE PRECISION,
    payload          JSONB,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== CafeF (VN-Index và đối chiếu): giá nghìn đồng, giá trị khớp lệnh và thỏa thuận tỷ đồng =====
CREATE TABLE IF NOT EXISTS raw.cafef_price (
    symbol              TEXT NOT NULL,
    trade_date          DATE NOT NULL,
    open_k              DOUBLE PRECISION,
    high_k              DOUBLE PRECISION,
    low_k               DOUBLE PRECISION,
    close_k             DOUBLE PRECISION,
    adj_close_k         DOUBLE PRECISION,
    change_text         TEXT,
    matched_volume      DOUBLE PRECISION,
    matched_value_bn    DOUBLE PRECISION,
    putthrough_volume   DOUBLE PRECISION,
    putthrough_value_bn DOUBLE PRECISION,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trade_date)
);

-- ===== yfinance =====
CREATE TABLE IF NOT EXISTS raw.yf_prices (
    ticker      TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    adj_close   DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, trade_date)
);

-- ===== Tin tức =====
-- Backfill từ EconVNNews (chỉ có ngày đăng)
CREATE TABLE IF NOT EXISTS raw.news_backfill (
    url             TEXT PRIMARY KEY,
    source          TEXT,
    source_file     TEXT,
    title           TEXT,
    content         TEXT,
    published_date  DATE,
    author          TEXT,
    category        TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_news_backfill_date ON raw.news_backfill (published_date);

-- Tin crawl và RSS (có giờ đăng). status: pending (mới có liên kết), done, failed
CREATE TABLE IF NOT EXISTS raw.news_crawl (
    url            TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    list_ref       TEXT,
    published_at   TIMESTAMPTZ,
    title          TEXT,
    summary        TEXT,
    content        TEXT,
    category       TEXT,
    http_status    INTEGER,
    status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'failed')),
    content_chars  INTEGER,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_news_crawl_published ON raw.news_crawl (published_at DESC);
CREATE INDEX IF NOT EXISTS ix_news_crawl_status ON raw.news_crawl (status, source);
