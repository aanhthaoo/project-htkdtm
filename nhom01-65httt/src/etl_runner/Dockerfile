# Bộ chạy ETL: chạy các lệnh thu thập (src/ingestion), làm sạch tin (src/etl), dbt (src/dbt_dw) theo yêu cầu của n8n hoặc trang quản trị.
# Ngữ cảnh build là thư mục src/ (xem docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PYTHONPATH=/app/src

WORKDIR /app/src

COPY ingestion/requirements.txt /tmp/req-ingestion.txt
COPY dbt_dw/requirements.txt /tmp/req-dbt.txt
COPY etl_runner/requirements.txt /tmp/req-runner.txt
RUN pip install --no-cache-dir -r /tmp/req-ingestion.txt -r /tmp/req-dbt.txt -r /tmp/req-runner.txt

COPY ingestion /app/src/ingestion
COPY etl /app/src/etl
COPY dbt_dw /app/src/dbt_dw
COPY etl_runner /app/src/etl_runner

EXPOSE 8100
CMD ["uvicorn", "etl_runner.app:app", "--host", "0.0.0.0", "--port", "8100"]
