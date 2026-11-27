#!/usr/bin/env bash
# Kiểm tra "chạy lại từ đầu" trong một dự án Docker compose TÁCH BIỆT (volume mới, cổng khác) để không động tới dữ liệu đang dùng.
# Tiền điều kiện: đã có gói `data/seed/full_raw_stg_dw.dump` (python -m handover.seed export full) và `data/verify/env` (bản sao .env đổi cổng).
# Chạy từ thư mục nhom01-65httt:   bash tools/verify_rebuild.sh   (Git Bash trên Windows; ghi thời gian từng bước vào data/verify/steps.tsv)
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
PY="${PYTHON:-python}"
PROJECT=htkdtm_verify
ENVF="$ROOT/data/verify/env"
get() { grep "^$1=" "$ENVF" | cut -d= -f2-; }
export POSTGRES_PORT="$(get POSTGRES_PORT)" SUPERSET_PORT="$(get SUPERSET_PORT)"
export DATABASE_URL="postgresql+psycopg://bi_app:$(get BI_APP_PASSWORD)@127.0.0.1:${POSTGRES_PORT}/bi_dw"
export SUPERSET_URL="http://127.0.0.1:${SUPERSET_PORT}" ETL_RUNNER_URL="http://127.0.0.1:$(get ETL_RUNNER_PORT)"
LOG="$ROOT/data/verify/steps.tsv"
: > "$LOG"

step() {  # step <tên> <lệnh...>: chạy, đo thời gian, ghi mã thoát
  local name="$1"; shift
  local t0=$(date +%s)
  echo "=== $name ($(date +%H:%M:%S))"
  "$@" > "$ROOT/data/verify/log_${name}.txt" 2>&1
  local rc=$?
  printf "%s\t%s\t%s\n" "$name" "$(( $(date +%s) - t0 ))" "$rc" >> "$LOG"
  echo "    mã thoát $rc, $(( $(date +%s) - t0 )) giây"
}
psql_verify() { docker exec "${PROJECT}-postgres-1" psql -U bi_admin -d bi_dw -v ON_ERROR_STOP=1 -c "$1"; }

cd src
step 01_init_db        "$PY" -m ingestion.cli init-db
step 02_dbt_seed       "$PY" dbt_dw/run.py seed
# xóa kết quả mô hình đã phục hồi để chứng minh chúng được tạo lại từ dữ liệu
step 03_xoa_ket_qua_ml psql_verify "TRUNCATE dw.fact_recommendation, dw.fact_prediction, dw.fact_news_sentiment, dw.stock_cluster, dw.dim_model"
step 04_etl_tin        "$PY" -m etl.news.pipeline
step 05_dbt_full_refresh "$PY" dbt_dw/run.py run --full-refresh
step 06_ml_cam_xuc     "$PY" -m ml.sentiment
step 07_ml_phan_cum    "$PY" -m ml.clustering
step 08_dbt_dim_stock  "$PY" dbt_dw/run.py run --select "dim_stock+"
step 09_ml_du_bao      "$PY" -m ml.forecast
step 10_ml_khuyen_nghi "$PY" -m ml.recommend
step 11_dbt_test       "$PY" dbt_dw/run.py test
step 12_quality        "$PY" -m etl.quality_checks
cd ..
step 13_superset       "$PY" src/superset/provision.py
step 14_n8n_import     bash -c "$PY src/n8n/build_workflows.py && docker exec ${PROJECT}-n8n-1 n8n import:workflow --separate --input=/workflows"
echo "Xong các bước nạp và dựng. Còn: handover.check, pytest (xem docs/kiem_thu_tu_dau.md)."
cat "$LOG"
