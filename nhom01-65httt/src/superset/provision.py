"""Cấu hình Superset tự động (chạy lại nhiều lần không nhân đôi): kết nối dw, dataset, metric, biểu đồ thử.

Chạy từ thư mục nhom01-65httt/ (Superset phải đang chạy):
    python src/superset/provision.py            # tạo hoặc cập nhật tất cả
    python src/superset/provision.py --no-charts  # bỏ qua biểu đồ thử

Cần trong .env: SUPERSET_PORT, SUPERSET_ADMIN_USER, SUPERSET_ADMIN_PASSWORD, BI_READONLY_PASSWORD.
Superset kết nối PostgreSQL qua tên dịch vụ `postgres` trong mạng Docker, bằng tài khoản chỉ đọc bi_readonly.
"""

import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import spec  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Superset:
    def __init__(self, base: str, user: str, password: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.headers["Referer"] = self.base
        r = self.s.post(
            f"{self.base}/api/v1/security/login",
            json={"username": user, "password": password, "provider": "db", "refresh": True},
            timeout=30,
        )
        r.raise_for_status()
        self.s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        r = self.s.get(f"{self.base}/api/v1/security/csrf_token/", timeout=30)
        r.raise_for_status()
        self.s.headers["X-CSRFToken"] = r.json()["result"]

    def call(self, method: str, path: str, **kw):
        r = self.s.request(
            method, f"{self.base}/api/v1/{path}", timeout=kw.pop("timeout", 120), **kw
        )
        if not r.ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:600]}")
        return r.json()

    def find(self, resource: str, col: str, value: str) -> dict | None:
        q = f"(filters:!((col:{col},opr:eq,value:'{value}')),page_size:100)"
        result = self.call("GET", resource, params={"q": q})["result"]
        return result[0] if result else None

    # ---- kết nối cơ sở dữ liệu ----
    def ensure_database(self, uri: str) -> int:
        existing = self.find("database", "database_name", spec.DATABASE_NAME)
        payload = {
            "database_name": spec.DATABASE_NAME,
            "sqlalchemy_uri": uri,
            "expose_in_sqllab": True,
            "allow_dml": False,
            "allow_ctas": False,
            "allow_cvas": False,
        }
        if existing:
            self.call("PUT", f"database/{existing['id']}", json=payload)
            return existing["id"]
        return self.call("POST", "database/", json=payload)["id"]

    # ---- dataset và metric ----
    def ensure_dataset(self, db_id: int, ds: spec.Dataset) -> int:
        existing = self.find("dataset", "table_name", ds.table)
        if existing and existing.get("schema") == spec.SCHEMA:
            ds_id = existing["id"]
        else:
            ds_id = self.call(
                "POST",
                "dataset/",
                json={"database": db_id, "schema": spec.SCHEMA, "table_name": ds.table},
            )["id"]
        self.call(
            "PUT", f"dataset/{ds_id}", params={"override_columns": "true"}, json={}
        )  # đồng bộ cột
        current = self.call("GET", f"dataset/{ds_id}")["result"]
        ids = {m["metric_name"]: m["id"] for m in current["metrics"]}
        wanted = {m.name for m in ds.metrics}
        metrics = []
        for m in ds.metrics:
            item = {
                "metric_name": m.name,
                "expression": m.expression,
                "verbose_name": m.verbose,
                "description": m.description,
                "d3format": m.d3format,
                "metric_type": "metric",
            }
            if m.name in ids:
                item["id"] = ids[m.name]
            metrics.append(item)
        for name, mid in ids.items():  # giữ metric có sẵn không thuộc đặc tả (vd "count")
            if name not in wanted:
                metrics.append(
                    {
                        "id": mid,
                        "metric_name": name,
                        "expression": next(
                            x["expression"] for x in current["metrics"] if x["id"] == mid
                        ),
                    }
                )
        payload = {"description": ds.description, "metrics": metrics}
        if ds.main_dttm_col:
            payload["main_dttm_col"] = ds.main_dttm_col
        self.call("PUT", f"dataset/{ds_id}", json=payload)
        return ds_id

    # ---- biểu đồ thử ----
    def ensure_chart(self, ds_id: int, ds: spec.Dataset) -> int | None:
        if not ds.test_chart:
            return None
        name, viz, extra = ds.test_chart
        extra = dict(extra)
        sql_filter = extra.pop("adhoc_filters_sql", None)
        params = {
            "viz_type": viz,
            "datasource": f"{ds_id}__table",
            "time_range": "No filter",
            "row_limit": extra.pop("row_limit", 10000),
            "adhoc_filters": [
                {"expressionType": "SQL", "clause": "WHERE", "sqlExpression": sql_filter}
            ]
            if sql_filter
            else [],
        }
        if viz == "table":
            params.update({"query_mode": "aggregate", "all_columns": [], "order_desc": True})
        else:
            params["x_axis"] = ds.main_dttm_col
        params.update(extra)
        payload = {
            "slice_name": name,
            "viz_type": viz,
            "datasource_id": ds_id,
            "datasource_type": "table",
            "params": json.dumps(params),
        }
        existing = self.find("chart", "slice_name", name)
        if existing:
            self.call("PUT", f"chart/{existing['id']}", json=payload)
            return existing["id"]
        return self.call("POST", "chart/", json=payload)["id"]

    # ---- dashboard và nhúng ----
    def ensure_dashboard(self, dash: spec.DashboardSpec) -> tuple[int, str]:
        """Tạo (hoặc cập nhật) dashboard, gắn biểu đồ, bật nhúng. Trả (id dashboard, uuid nhúng)."""
        existing = self.find("dashboard", "slug", dash.slug)
        payload = {"dashboard_title": dash.title, "slug": dash.slug, "published": True}
        if existing:
            dash_id = existing["id"]
            self.call("PUT", f"dashboard/{dash_id}", json=payload)
        else:
            dash_id = self.call("POST", "dashboard/", json=payload)["id"]
        for name in dash.chart_names:
            chart = self.find("chart", "slice_name", name)
            if not chart:
                raise RuntimeError(f"Chưa có biểu đồ {name}; chạy provision không kèm --no-charts")
            self.call("PUT", f"chart/{chart['id']}", json={"dashboards": [dash_id]})
        embedded = self.s.get(f"{self.base}/api/v1/dashboard/{dash_id}/embedded", timeout=60)
        if embedded.status_code == 200:
            return dash_id, embedded.json()["result"]["uuid"]
        result = self.call("POST", f"dashboard/{dash_id}/embedded", json={"allowed_domains": []})[
            "result"
        ]
        return dash_id, result["uuid"]

    # ---- truy vấn dữ liệu (dùng cho kiểm thử) ----
    def query(
        self,
        ds_id: int,
        metrics: list[str],
        columns: list[str] | None = None,
        where: str | None = None,
        orderby: list | None = None,
        row_limit: int = 1000,
    ) -> list[dict]:
        q: dict = {
            "columns": columns or [],
            "metrics": metrics,
            "row_limit": row_limit,
            "time_range": "No filter",
            "extras": {"where": where} if where else {},
        }
        if orderby:
            q["orderby"] = orderby
        body = {
            "datasource": {"id": ds_id, "type": "table"},
            "queries": [q],
            "result_format": "json",
            "result_type": "full",
        }
        return self.call("POST", "chart/data", json=body, timeout=300)["result"][0]["data"]


def chart_rows(sup: Superset, chart_id: int) -> list[dict]:
    """Chạy truy vấn tương đương biểu đồ đã lưu (dựng từ tham số, giống cách giao diện Explore làm)."""
    chart = sup.call("GET", f"chart/{chart_id}")["result"]
    params = json.loads(chart["params"])
    columns: list = list(params.get("groupby") or [])
    if params["viz_type"] != "table" and params.get("x_axis"):
        columns.insert(
            0,
            {
                "columnType": "BASE_AXIS",
                "sqlExpression": params["x_axis"],
                "label": params["x_axis"],
                "expressionType": "SQL",
                "timeGrain": params.get("time_grain_sqla"),
            },
        )
    where = " AND ".join(
        f"({f['sqlExpression']})"
        for f in params.get("adhoc_filters", [])
        if f.get("expressionType") == "SQL"
    )
    body = {
        "datasource": {"id": int(params["datasource"].split("__")[0]), "type": "table"},
        "queries": [
            {
                "columns": columns,
                "metrics": params["metrics"],
                "row_limit": params.get("row_limit", 10000),
                "time_range": "No filter",
                "extras": {"where": where} if where else {},
                "orderby": [[params["metrics"][0], False]] if params["viz_type"] == "table" else [],
            }
        ],
        "result_format": "json",
        "result_type": "full",
    }
    return sup.call("POST", "chart/data", json=body, timeout=300)["result"][0]["data"]


def connect() -> Superset:
    load_env()
    port = os.environ.get("SUPERSET_PORT", "8088")
    return Superset(
        os.environ.get("SUPERSET_URL", f"http://127.0.0.1:{port}"),
        os.environ["SUPERSET_ADMIN_USER"],
        os.environ["SUPERSET_ADMIN_PASSWORD"],
    )


def main() -> int:
    charts = "--no-charts" not in sys.argv
    sup = connect()
    uri = f"postgresql+psycopg2://bi_readonly:{os.environ['BI_READONLY_PASSWORD']}@postgres:5432/bi_dw"
    db_id = sup.ensure_database(uri)
    print(f"Kết nối {spec.DATABASE_NAME}: id {db_id}")
    for ds in spec.DATASETS:
        ds_id = sup.ensure_dataset(db_id, ds)
        chart_id = sup.ensure_chart(ds_id, ds) if charts else None
        print(
            f"  dataset {ds.table}: id {ds_id}, {len(ds.metrics)} metric, biểu đồ thử: {chart_id}"
        )
    if charts:
        for dash in spec.DASHBOARDS:
            dash_id, uuid = sup.ensure_dashboard(dash)
            print(f"  dashboard {dash.slug}: id {dash_id}, nhúng {uuid}")
    print("Xong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
