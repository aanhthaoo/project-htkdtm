FROM apache/superset:5.0.0

USER root

# Superset lưu siêu dữ liệu trong PostgreSQL nên cần driver psycopg2
RUN . /app/.venv/bin/activate && uv pip install --no-cache psycopg2-binary==2.9.10

COPY superset_config.py /app/superset_config.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV SUPERSET_CONFIG_PATH=/app/superset_config.py

USER superset
ENTRYPOINT ["/app/docker-entrypoint.sh"]
