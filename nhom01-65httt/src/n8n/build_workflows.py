"""Sinh các workflow n8n lõi (JSON) vào src/n8n/workflows/. Chạy từ thư mục nhom01-65httt/:

    python src/n8n/build_workflows.py

Workflow gọi bộ chạy ETL (etl-runner) và backend qua biến môi trường của n8n (xem docker-compose.yml):
ETL_RUNNER_URL, BACKEND_URL, SERVICE_KEY. Import: docker compose exec n8n n8n import:workflow --separate --input=/workflows
"""

import json
from pathlib import Path

OUT = Path(__file__).parent / "workflows"
KEY_HEADER = {"parameters": [{"name": "X-Service-Key", "value": "={{ $env.SERVICE_KEY }}"}]}


def http(
    name, x, y, method, url, *, query=None, body=None, never_error=True, continue_on_error=True
):
    params = {
        "method": method,
        "url": url,
        "sendHeaders": True,
        "headerParameters": KEY_HEADER,
        "options": {
            "response": {"response": {"fullResponse": True, "neverError": never_error}},
            "timeout": 30000,
        },
    }
    if query:
        params["sendQuery"] = True
        params["queryParameters"] = {
            "parameters": [{"name": k, "value": v} for k, v in query.items()]
        }
    if body:
        params["sendBody"] = True
        params["specifyBody"] = "json"
        params["jsonBody"] = body
    node = {
        "parameters": params,
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x, y],
    }
    if continue_on_error:
        node["onError"] = "continueRegularOutput"
    return node


def if_node(name, x, y, expression):
    return {
        "parameters": {"conditions": {"boolean": [{"value1": expression, "value2": True}]}},
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 1,
        "position": [x, y],
    }


def simple(name, x, y, type_, params=None, version=1):
    return {
        "parameters": params or {},
        "name": name,
        "type": type_,
        "typeVersion": version,
        "position": [x, y],
    }


def link(*pairs):
    """link(("A", "B"), ("B", "C", 1)) -> connections; phần tử thứ 3 là chỉ số cổng ra (0 = đúng, 1 = sai)."""
    out: dict = {}
    for p in pairs:
        src, dst = p[0], p[1]
        port = p[2] if len(p) > 2 else 0
        slots = out.setdefault(src, {"main": []})["main"]
        while len(slots) <= port:
            slots.append([])
        slots[port].append({"node": dst, "type": "main", "index": 0})
    return out


def workflow(wid, name, nodes, connections):
    return {
        "id": wid,
        "name": name,
        "active": False,
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "timezone": "Asia/Ho_Chi_Minh"},
        "pinData": {},
    }


RUNNER = "={{ $env.ETL_RUNNER_URL }}"
BACKEND = "={{ $env.BACKEND_URL }}"
OK_START = "={{ [202, 409].includes($json.statusCode) }}"  # 202 đã nhận, 409 đang bận (bình thường với lịch theo giờ)


def failure_event(job_expr: str, message_expr: str) -> str:
    return (
        "={{ JSON.stringify({ job: "
        + job_expr
        + ", status: 'failed', message: "
        + message_expr
        + " }) }}"
    )


MSG_START_FAIL = (
    "String($json.error ? $json.error.message : JSON.stringify($json.body)).slice(0, 500)"
)


def hourly():
    nodes = [
        simple(
            "Mỗi giờ",
            0,
            0,
            "n8n-nodes-base.scheduleTrigger",
            {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}},
            1.2,
        ),
        simple("Chạy thủ công", 0, 200, "n8n-nodes-base.manualTrigger"),
        http(
            "Thu thập RSS",
            260,
            100,
            "POST",
            RUNNER + "/jobs/rss",
            query={"trigger": "n8n", "requested_by": "n8n-hourly"},
        ),
        if_node("Đã nhận hoặc đang bận?", 520, 100, OK_START),
        simple("Xong", 780, 20, "n8n-nodes-base.noOp"),
        http(
            "Ghi lỗi vào nhật ký",
            780,
            200,
            "POST",
            BACKEND + "/api/internal/etl/events",
            body=failure_event("'rss'", MSG_START_FAIL),
        ),
    ]
    links = link(
        ("Mỗi giờ", "Thu thập RSS"),
        ("Chạy thủ công", "Thu thập RSS"),
        ("Thu thập RSS", "Đã nhận hoặc đang bận?"),
        ("Đã nhận hoặc đang bận?", "Xong", 0),
        ("Đã nhận hoặc đang bận?", "Ghi lỗi vào nhật ký", 1),
    )
    return workflow("etl-hourly", "ETL - Thu thập tin RSS theo giờ", nodes, links)


def after_close():
    nodes = [
        simple(
            "15h30 các ngày làm việc",
            0,
            0,
            "n8n-nodes-base.scheduleTrigger",
            {"rule": {"interval": [{"field": "cronExpression", "expression": "30 15 * * 1-5"}]}},
            1.2,
        ),
        simple("Chạy thủ công", 0, 200, "n8n-nodes-base.manualTrigger"),
        http(
            "Chạy chuỗi sau phiên",
            260,
            100,
            "POST",
            RUNNER + "/jobs/after_close",
            query={"trigger": "n8n", "requested_by": "n8n-after-close"},
        ),
        if_node("Đã nhận?", 520, 100, "={{ $json.statusCode === 202 }}"),
        simple(
            "Lưu mã lần chạy",
            780,
            20,
            "n8n-nodes-base.set",
            {
                "assignments": {
                    "assignments": [
                        {
                            "id": "a1",
                            "name": "run_id",
                            "value": "={{ $json.body.run_id }}",
                            "type": "number",
                        }
                    ]
                },
                "options": {},
            },
            3.4,
        ),
        simple(
            "Chờ 60 giây", 1040, 20, "n8n-nodes-base.wait", {"amount": 60, "unit": "seconds"}, 1.1
        ),
        http(
            "Xem trạng thái",
            1300,
            20,
            "GET",
            "={{ $env.ETL_RUNNER_URL + '/jobs/' + $json.run_id }}",
        ),
        simple(
            "Đọc trạng thái",
            1560,
            20,
            "n8n-nodes-base.set",
            {
                "assignments": {
                    "assignments": [
                        {
                            "id": "b1",
                            "name": "run_id",
                            "value": "={{ $json.body.id }}",
                            "type": "number",
                        },
                        {
                            "id": "b2",
                            "name": "status",
                            "value": "={{ $json.body.status }}",
                            "type": "string",
                        },
                        {
                            "id": "b3",
                            "name": "log_tail",
                            "value": "={{ $json.body.log_tail }}",
                            "type": "string",
                        },
                    ]
                },
                "options": {},
            },
            3.4,
        ),
        if_node("Còn chạy?", 1820, 20, "={{ $json.status === 'running' }}"),
        if_node("Thành công?", 2080, 100, "={{ $json.status === 'success' }}"),
        simple("Xong", 2340, 20, "n8n-nodes-base.noOp"),
        http(
            "Ghi lỗi vào nhật ký (chuỗi lỗi)",
            2340,
            200,
            "POST",
            BACKEND + "/api/internal/etl/events",
            body=failure_event(
                "'after_close'",
                "String($json.log_tail || 'Chuỗi sau phiên thất bại').slice(0, 500)",
            ),
        ),
        http(
            "Ghi lỗi vào nhật ký (không khởi động được)",
            780,
            220,
            "POST",
            BACKEND + "/api/internal/etl/events",
            body=failure_event("'after_close'", MSG_START_FAIL),
        ),
    ]
    links = link(
        ("15h30 các ngày làm việc", "Chạy chuỗi sau phiên"),
        ("Chạy thủ công", "Chạy chuỗi sau phiên"),
        ("Chạy chuỗi sau phiên", "Đã nhận?"),
        ("Đã nhận?", "Lưu mã lần chạy", 0),
        ("Đã nhận?", "Ghi lỗi vào nhật ký (không khởi động được)", 1),
        ("Lưu mã lần chạy", "Chờ 60 giây"),
        ("Chờ 60 giây", "Xem trạng thái"),
        ("Xem trạng thái", "Đọc trạng thái"),
        ("Đọc trạng thái", "Còn chạy?"),
        ("Còn chạy?", "Chờ 60 giây", 0),
        ("Còn chạy?", "Thành công?", 1),
        ("Thành công?", "Xong", 0),
        ("Thành công?", "Ghi lỗi vào nhật ký (chuỗi lỗi)", 1),
    )
    return workflow(
        "etl-after-close",
        "ETL - Chuỗi sau phiên 15h30 (giá, quốc tế, dbt, chất lượng)",
        nodes,
        links,
    )


def rerun_webhook():
    job = "$json.body.job"
    nodes = [
        simple(
            "Webhook chạy lại ETL",
            0,
            100,
            "n8n-nodes-base.webhook",
            {
                "httpMethod": "POST",
                "path": "etl-run",
                "responseMode": "responseNode",
                "options": {},
            },
            2,
        ),
        http(
            "Gọi bộ chạy ETL",
            260,
            100,
            "POST",
            "={{ $env.ETL_RUNNER_URL + '/jobs/' + encodeURIComponent(" + job + ") }}",
            query={"trigger": "n8n", "requested_by": "n8n-webhook"},
        ),
        if_node("Đã nhận?", 520, 100, "={{ $json.statusCode === 202 }}"),
        simple(
            "Trả kết quả",
            780,
            20,
            "n8n-nodes-base.respondToWebhook",
            {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify($json.body) }}",
                "options": {"responseCode": 202},
            },
            1.1,
        ),
        http(
            "Ghi lỗi vào nhật ký",
            780,
            200,
            "POST",
            BACKEND + "/api/internal/etl/events",
            body=failure_event(
                "String($('Webhook chạy lại ETL').item.json.body.job)",
                MSG_START_FAIL,
            ),
        ),
        simple(
            "Trả lỗi",
            1040,
            200,
            "n8n-nodes-base.respondToWebhook",
            {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ error: { code: 'etl_start_failed', message: 'Không khởi động được ETL, đã ghi nhật ký' } }) }}",
                "options": {"responseCode": 502},
            },
            1.1,
        ),
    ]
    links = link(
        ("Webhook chạy lại ETL", "Gọi bộ chạy ETL"),
        ("Gọi bộ chạy ETL", "Đã nhận?"),
        ("Đã nhận?", "Trả kết quả", 0),
        ("Đã nhận?", "Ghi lỗi vào nhật ký", 1),
        ("Ghi lỗi vào nhật ký", "Trả lỗi"),
    )
    wf = workflow("etl-rerun-webhook", "ETL - Chạy lại thủ công qua webhook", nodes, links)
    nodes[0]["webhookId"] = "etl-run-webhook"
    return wf


def alert_sample():
    nodes = [
        simple(
            "Webhook cảnh báo",
            0,
            100,
            "n8n-nodes-base.webhook",
            {
                "httpMethod": "POST",
                "path": "alert-dispatch",
                "responseMode": "responseNode",
                "options": {},
            },
            2,
        ),
        http(
            "Lấy người đăng ký",
            260,
            100,
            "POST",
            BACKEND + "/api/internal/alerts/dispatch",
            body="={{ JSON.stringify({ alert_type: $json.body.alert_type, entity_type: $json.body.entity_type, entity_code: $json.body.entity_code }) }}",
            continue_on_error=False,
            never_error=False,
        ),
        simple(
            "Tách từng người nhận",
            520,
            100,
            "n8n-nodes-base.splitOut",
            {"fieldToSplitOut": "body.recipients", "options": {}},
            1,
        ),
        simple(
            "Gửi email (TV5 thay bằng nút Send Email/SMTP)",
            780,
            100,
            "n8n-nodes-base.noOp",
        ),
        simple(
            "Trả kết quả",
            1040,
            100,
            "n8n-nodes-base.respondToWebhook",
            {
                "respondWith": "json",
                "responseBody": "={{ JSON.stringify({ dispatched: $input.all().length }) }}",
                "options": {"responseCode": 200},
            },
            1.1,
        ),
    ]
    links = link(
        ("Webhook cảnh báo", "Lấy người đăng ký"),
        ("Lấy người đăng ký", "Tách từng người nhận"),
        ("Tách từng người nhận", "Gửi email (TV5 thay bằng nút Send Email/SMTP)"),
        ("Gửi email (TV5 thay bằng nút Send Email/SMTP)", "Trả kết quả"),
    )
    wf = workflow(
        "alert-dispatch-sample", "Mẫu - Gửi cảnh báo email (TV5 hoàn thiện)", nodes, links
    )
    nodes[0]["webhookId"] = "alert-dispatch-webhook"
    return wf


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for wf in (hourly(), after_close(), rerun_webhook(), alert_sample()):
        path = OUT / f"{wf['id']}.json"
        path.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Đã ghi {path.name}: {len(wf['nodes'])} nút")


if __name__ == "__main__":
    main()
