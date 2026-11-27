FROM apache/superset:5.0.0

USER root

# psycopg2: Superset lưu siêu dữ liệu trong PostgreSQL. flask-cors: bật CORS khi nhúng dashboard vào website
RUN . /app/.venv/bin/activate && uv pip install --no-cache psycopg2-binary==2.9.10 flask-cors==4.0.2

COPY superset_config.py /app/superset_config.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV SUPERSET_CONFIG_PATH=/app/superset_config.py

USER superset
ENTRYPOINT ["/app/docker-entrypoint.sh"]
