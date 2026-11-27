# n8n: workflow lõi

n8n chạy ở http://localhost:5678 (lần đầu mở sẽ yêu cầu tạo tài khoản chủ sở hữu). Workflow nằm ở `src/n8n/workflows/*.json`, **sinh từ `src/n8n/build_workflows.py`**; sửa script rồi chạy lại để các tệp luôn nhất quán (có test kiểm tra).

```bash
python src/n8n/build_workflows.py                                   # sinh lại JSON (từ thư mục nhom01-65httt/)
docker compose up -d n8n                                            # thư mục workflows được gắn vào container ở /workflows
MSYS_NO_PATHCONV=1 docker exec htkdtm_nhom01-n8n-1 n8n import:workflow --separate --input=/workflows
MSYS_NO_PATHCONV=1 docker exec htkdtm_nhom01-n8n-1 n8n update:workflow --id=etl-hourly --active=true   # lặp lại cho từng workflow cần bật
docker restart htkdtm_nhom01-n8n-1                                  # bắt buộc để kích hoạt có hiệu lực
```
(`MSYS_NO_PATHCONV=1` chỉ cần khi chạy lệnh trong Git Bash trên Windows.) Cũng có thể import bằng giao diện: Workflows → Import from file.

Workflow đọc biến môi trường của n8n (đặt trong `docker-compose.yml`, không ghi cứng): `ETL_RUNNER_URL`, `BACKEND_URL`, `SERVICE_KEY`.

| Workflow (id) | Kích hoạt | Việc làm | Mặc định |
|---------------|-----------|----------|----------|
| `etl-hourly` | Mỗi giờ + nút chạy thủ công | Gọi bộ chạy ETL job `rss`; nếu nguồn lỗi, ghi sự kiện lỗi vào `app.etl_runs` | bật |
| `etl-after-close` | 15h30 thứ Hai–thứ Sáu + nút chạy thủ công | Job `after_close`: cập nhật giá, khối ngoại, tự doanh, VN-Index, quốc tế, tin → `dbt run` → `dbt test` → kiểm tra chất lượng. Chờ và đọc trạng thái mỗi 60 giây; lỗi thì ghi nhật ký | bật |
| `etl-rerun-webhook` | `POST /webhook/etl-run` body `{"job": "..."}` | Chạy lại thủ công một job; lỗi thì ghi nhật ký và trả 502 | bật |
| `alert-dispatch-sample` | `POST /webhook/alert-dispatch` | **Mẫu cho TV5:** lấy người đăng ký cảnh báo từ backend, tách từng người; nút "Gửi email" đang là `NoOp`, TV5 thay bằng nút Send Email (SMTP) | tắt |

Tin tức: job `news` (làm sạch toàn bộ tin, 30–40 phút) **không** nằm trong `after_close`; chạy riêng (ví dụ ban đêm) bằng webhook hoặc thêm workflow lịch riêng.

## Kiểm thử đã làm
- Chạy job `after_close` qua webhook: giá và khối ngoại mới (23/11 → 25/11) vào `raw` rồi `dw`; 4 bước (`daily` 40 giây, `dbt_run` 84 giây, `dbt_test` 17 giây, `quality` 8 giây) đều thành công.
- Kịch bản lỗi: gọi job không tồn tại, n8n ghi một dòng `failed` (trigger `n8n`) vào `app.etl_runs` và trả 502.
- Cấu trúc workflow được kiểm tra tự động (`tests/unit/test_n8n_workflows_runner.py`): nút hợp lệ, mọi gọi HTTP mang khóa dịch vụ, địa chỉ lấy từ biến môi trường, không có mật khẩu ghi cứng.

## Thêm workflow mới (TV5)
Thêm hàm sinh vào `build_workflows.py` (mẫu: `alert_sample`), đăng ký trong `main()`, thêm id vào bảng trên và test `test_co_du_4_workflow_loi`. Hoặc dựng trong giao diện n8n, xuất JSON vào thư mục `workflows/`.
