# API contract (bản chốt N7; cập nhật N9: khuyến nghị và API mô hình dùng dữ liệu thật)

Nguồn chính xác nhất là **`docs/openapi.json`** (39 đường dẫn, sinh từ code bằng `python src/backend/export_openapi.py`). Tài liệu tương tác: http://localhost:8000/docs khi hệ thống đang chạy. Test `tests/smoke/test_api.py` so `openapi.json` với API thực tế nên **không ai đổi API mà quên cập nhật**. Từ lúc chốt, schema chỉ đổi khi báo cả nhóm (bản nháp N2 đã được thay bằng tệp này).

## 1. Quy ước chung

| Hạng mục | Quy ước |
|----------|---------|
| Giao thức | REST, JSON, UTF-8. Tiền tố `/api` cho website; `/ml` cho API mô hình (nội bộ) |
| Đặt tên | Trường `snake_case`; đường dẫn chữ thường |
| Ngày giờ | Ngày `YYYY-MM-DD`; thời điểm ISO 8601 có múi giờ |
| Đơn vị | Tiền **tỷ đồng**, hậu tố `_bn`; giá cổ phiếu **đồng**, hậu tố `_vnd` (kho lưu nghìn đồng, API nhân 1.000) |
| Xác thực | `Authorization: Bearer <JWT>`. Token HS256, mặc định hiệu lực 60 phút (`JWT_TTL_MINUTES`) |
| Vai trò | `guest` (không token) < `investor` < `admin`. Vai trò lấy từ cơ sở dữ liệu, **không tin** vai trò ghi trong token |
| Phân trang | `?page=1&page_size=20` (tối đa 100); trả `{items, page, page_size, total}` |
| Lỗi | `{"error": {"code": "...", "message": "...", "details": [...]}}` (`details` chỉ có ở lỗi kiểm tra dữ liệu) |
| Lưu ý đầu tư | Response dự báo/khuyến nghị có trường `disclaimer` |
| Dữ liệu mẫu | Endpoint chưa có dữ liệu thật trả đúng schema và `"stub": true` |

### Mã lỗi

| HTTP | `code` | Khi nào |
|------|--------|---------|
| 401 | `not_authenticated` | Cần đăng nhập, không gửi token |
| 401 | `invalid_token`, `token_expired` | Token sai, bị sửa, hoặc hết hạn (frontend đăng xuất và về trang đăng nhập) |
| 401 | `invalid_credentials` | Sai email hoặc mật khẩu (cùng một thông báo cho cả hai) |
| 401 | `invalid_service_key` | Webhook nội bộ thiếu hoặc sai `X-Service-Key` |
| 403 | `forbidden`, `account_disabled` | Đủ đăng nhập nhưng thiếu quyền; tài khoản bị khóa |
| 404 | `not_found`, `dashboard_not_embedded` | Không có mã/ngành/chỉ số/dashboard |
| 409 | `email_taken`, `already_watching`, `already_subscribed`, `etl_busy` | Trùng dữ liệu; đang có lần chạy ETL khác |
| 422 | `validation_error` | Dữ liệu gửi lên sai (kèm `details`) |
| 502 | `superset_unavailable`, `etl_runner_unavailable`, `etl_runner_error` | Dịch vụ phía sau không phản hồi |

## 2. Danh sách endpoint

Cột "Dữ liệu": **thật** = đọc từ `dw`/`app`; **stub** = mẫu đúng schema. Cột "Chủ" là người hoàn thiện (số thứ tự theo `Ke_hoach_thuc_hien_BTL_Nhom01.md`).

| Nhóm | Endpoint | Vai trò | Dữ liệu | Chủ |
|------|----------|---------|---------|-----|
| Auth | `POST /api/auth/register` (201), `POST /api/auth/login`, `GET /api/auth/me` | guest / investor | thật | TV1 |
| Nhúng Superset | `GET /api/superset/dashboards`, `GET /api/superset/embed/{key}` | theo từng dashboard | thật | TV1 (TV3 thêm dashboard) |
| Thị trường | `GET /api/market/overview?date=` | guest | thật | TV3 |
| Ngành | `GET /api/sectors/flow?from=&to=&granularity=day\|week\|month&investor_type=` | investor | thật | TV3 |
| | `GET /api/sectors/{icb_l2_code}` | investor | **stub** | TV3 |
| Mã | `GET /api/stocks?query=&exchange=&sector=` | investor | thật | TV2 |
| | `GET /api/stocks/{symbol}`, `/prices`, `/flow` | investor | thật | TV2 |
| | `GET /api/stocks/top-net?side=buy\|sell&investor_type=&period=&limit=` | investor | thật | TV3 |
| Tin tức | `GET /api/news?symbol=&sector=&from=&to=` | guest (tối đa 5 tin) / investor | thật (cảm xúc `null` với bài không nhắc mã/ngành nào) | TV5 |
| | `GET /api/news/highlights` | guest | thật | TV5 |
| Vĩ mô | `GET /api/macro/series?codes=USDVND,DXY&from=&to=` | investor | thật | TV5 |
| | `GET /api/macro/correlation?codes=&against=&window=` | investor | **stub** | TV5 |
| Dự báo | `GET /api/predictions?week=&horizon=` | investor | **stub** | TV4 |
| | `GET /api/predictions/accuracy?weeks=` | investor | **stub** | TV4 |
| | `GET /api/recommendations?week=` | investor | thật (N9) | TV4 |
| Theo dõi | `GET/POST /api/watchlist`, `DELETE /api/watchlist/{id}` | investor | thật | TV2 |
| Cảnh báo | `POST /api/alerts/subscriptions`, `DELETE /api/alerts/subscriptions/{id}` | investor | thật | TV2 |
| Chatbot | `POST /api/chat` | investor | **stub** | TV2 |
| Quản trị | `GET /api/admin/users`, `PATCH /api/admin/users/{id}` | admin | thật | TV2 |
| | `GET /api/admin/sources`, `PUT /api/admin/sources/{code}` | admin | thật | TV2 |
| | `GET /api/admin/models` | admin | thật | TV2 |
| | `POST /api/admin/etl/run` (202), `GET /api/admin/etl/runs?status=` | admin | thật | TV1 |
| | `GET /api/admin/dq-log?from=&to=&severity=&failed_only=` | admin | thật | TV1 |
| Webhook nội bộ | `POST /api/internal/alerts/dispatch`, `POST /api/internal/etl/events` | khóa dịch vụ | thật | TV1 (TV5 dùng) |
| API mô hình | `POST /ml/predict`, `/ml/cluster` | khóa dịch vụ | thật (đọc kết quả mô hình trong `dw`) | TV1 |
| | `POST /ml/sentiment` | khóa dịch vụ | thật nếu tiến trình backend có mô hình và thư viện học máy; **không** thì dữ liệu mẫu `stub: true` (image backend chưa có torch) | TV1 |
| Hệ thống | `GET /health` | công khai | thật | TV1 |

**Khuyến nghị (N9).** `GET /api/recommendations` trả 19 ngành xếp theo điểm giảm dần. Giữ nguyên các trường đã chốt (`action`, `signal`, `reason`) và **thêm** `confidence` (`high|medium|low`), `score`, `signals` (mã tín hiệu kích hoạt), `prob_inflow`, `rule_version`; các trường thêm đều có giá trị mặc định nên client cũ không hỏng. Quy tắc cố định và công khai: `docs/ml_ket_qua.md` mục 5. `signal` ưu tiên `mismatch` (lệch pha) rồi `reversal` rồi `none`. Dự báo `/api/predictions` thêm trường `rank` (1 = ngành được dự báo mua ròng mạnh nhất tuần đó).

**API mô hình.** `/ml/predict` nhận `target_week_start` (thứ Hai, chỉ chân trời 1 tuần), trả 404 nếu không có dự báo tuần đó. `/ml/cluster` nhận tối đa 500 mã, trả `unknown` cho mã không có trong kho. `/ml/sentiment` nhận tối đa 100 văn bản.

Khác bản nháp N2: giá dùng `_vnd` (đồng); thêm `/api/superset/*`, `/api/internal/etl/events`, `/api/admin/dq-log` có `failed_only`; `/api/stocks/top-net` có `limit`; `/api/sectors/flow` trả thêm `granularity`.

## 3. Luồng đăng nhập và phân quyền

1. `POST /api/auth/register` (email, mật khẩu ≥ 8 ký tự, họ tên) tạo tài khoản `investor`, mật khẩu băm bcrypt; trả `access_token` và `user`. `POST /api/auth/login` tương tự.
2. Frontend lưu token (localStorage) và gửi ở header `Authorization`. Token hết hạn: API trả `401 token_expired`, frontend xóa token và về trang đăng nhập.
3. Tài khoản quản trị đầu tiên tạo khi backend khởi động từ `APP_ADMIN_EMAIL`/`APP_ADMIN_PASSWORD` trong `.env`. Quản trị đổi vai trò người khác qua `PATCH /api/admin/users/{id}`; không thể tự hạ quyền hoặc tự khóa.
4. Khách xem: tổng quan thị trường, tối đa 5 tin, tin nổi bật, dashboard `overview`. Nhà đầu tư xem thêm toàn bộ dữ liệu ngành, mã, vĩ mô, dự báo, theo dõi, cảnh báo, chat, dashboard `sector-rotation`. Quản trị thêm các endpoint `/api/admin/*`.

## 4. Nhúng Superset

`GET /api/superset/embed/{key}` kiểm tra vai trò rồi trả `{dashboard_id, superset_domain, guest_token}`. Frontend dùng thư viện `@superset-ui/embedded-sdk` (component `SupersetEmbed`) để đặt iframe. Guest token hiệu lực 10 phút, **chỉ cho đúng một dashboard** (đã kiểm thử: token của dashboard A không đọc được dashboard B). Backend đăng nhập Superset bằng tài khoản dịch vụ; trình duyệt không bao giờ thấy mật khẩu Superset.

Thêm dashboard mới (TV3): dựng dashboard trong Superset hoặc thêm vào `DASHBOARDS` ở `src/superset/spec.py` rồi chạy `python src/superset/provision.py` (bật nhúng, đặt `slug`), sau đó thêm một dòng vào `DASHBOARDS` trong `src/backend/app/routers/core_superset.py` (khóa, `slug`, vai trò tối thiểu) và dùng `<SupersetEmbed dashboardKey="khoa" />`. Tên dataset, metric: `docs/superset_dataset_metric.md`.

## 5. Webhook n8n và bộ chạy ETL

Mọi gọi nội bộ gửi header `X-Service-Key` (`SERVICE_KEY` trong `.env`, **không** dùng JWT người dùng).

| Hướng | Địa chỉ | Payload | Ghi chú |
|-------|---------|---------|---------|
| n8n → backend | `POST {BACKEND_URL}/api/internal/alerts/dispatch` | `{"alert_type": "flow_reversal\|negative_news\|weekly_digest", "entity_type": "STOCK\|SECTOR", "entity_code": "8300"}` | Trả `{count, recipients: [{user_id, email, full_name}]}` để n8n gửi email |
| n8n → backend | `POST {BACKEND_URL}/api/internal/etl/events` | `{"job": "rss", "status": "failed\|success", "message": "..."}` | Ghi một dòng vào nhật ký chạy ETL (trigger `n8n`) |
| n8n/backend → bộ chạy ETL | `POST {ETL_RUNNER_URL}/jobs/{job}?trigger=n8n&requested_by=...` | không | `job` ∈ `rss`, `daily`, `news`, `dbt`, `quality`, `after_close`; trả 202 `{run_id}`; 409 nếu đang bận |
| bên ngoài → n8n | `POST http://localhost:5678/webhook/etl-run` | `{"job": "after_close"}` | Chạy lại thủ công; lỗi thì n8n ghi nhật ký và trả 502 |
| bên ngoài → n8n | `POST http://localhost:5678/webhook/alert-dispatch` | cùng payload với dispatch | Workflow mẫu cho TV5 (nút gửi email chưa cấu hình) |

Tiến độ mỗi lần chạy nằm ở bảng `app.etl_runs` (`GET /api/admin/etl/runs`): từng bước, trạng thái, thời gian, 3.000 ký tự cuối của nhật ký bước cuối.

## 6. Thêm endpoint mới

1. Tạo tệp trong thư mục của mình `src/backend/app/routers/tvN/`, khai báo `router = APIRouter(...)` với `response_model` Pydantic.
2. Phân quyền bằng `InvestorUser`, `AdminUser` hoặc `OptionalUser` (xem `app/core/deps.py`); webhook nội bộ dùng `dependencies=[ServiceCall]`.
3. Thêm một dòng `app.include_router(...)` ở `app/main.py`. Chú ý thứ tự: đường dẫn cụ thể (`/api/stocks/top-net`) phải đăng ký trước đường dẫn có tham số (`/api/stocks/{symbol}`).
4. Thêm test vào `tests/smoke/test_api.py` (bảng `CONTRACT` kiểm tra phân quyền) và chạy `python src/backend/export_openapi.py` để cập nhật contract.
5. Gọi từ frontend bằng `api()` (`src/frontend/src/api/client.js`) hoặc hook `useApi`.
