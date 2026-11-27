# Bàn giao giai đoạn 1 (TV1 → TV2, TV3, TV4, TV5)

Người bàn giao: TV1 (Trương Thảo Anh). Phạm vi: hạ tầng, dữ liệu, kho, khung hệ thống, ba mô hình, khuyến nghị, tài liệu (kế hoạch `docs/Ke_hoach_GD1_TV1.md`, N1–N10). Kết quả kiểm tra bàn giao chạy thật: **10/10 hạng mục đạt** trên hệ thống dựng lại từ đầu (mục 3 và `docs/kiem_thu_tu_dau.md` mục 4). Chạy lại từ đầu: `docs/kiem_thu_tu_dau.md` (28 phút cho ETL tin, dbt, ba mô hình, kiểm thử; không tính thu thập và embedding).

## 1. Bắt đầu nhanh (30 phút)

```bash
git clone <kho Fork của nhóm trưởng> && cd project-htkdtm/nhom01-65httt
git checkout --track origin/nhom01-65httt          # rồi tạo nhánh riêng: git checkout -b <tên>-nhom01-65httt
sh tools/setup-git-hooks.sh                        # hook kiểm tra commit (README mục 4)
cp .env.example .env                               # đổi mật khẩu nếu cần, KHÔNG commit .env
docker compose up -d --build && docker compose ps  # chờ tất cả healthy (Superset 1-2 phút)
```

Lấy dữ liệu: xin **gói seed dev** `dw_dev.dump` từ TV1 (ổ đĩa nhóm), đặt vào `data/seed/`, rồi từ `src/`:
```bash
pip install -r backend/requirements-dev.txt -r ingestion/requirements.txt -r dbt_dw/requirements.txt
python -m handover.seed restore ../data/seed/dw_dev.dump   # 187 MB, phục hồi khoảng 1 phút; kho có đủ dữ liệu thật và kết quả mô hình
python -m handover.check --only 1 2 4 5                    # tự kiểm tra máy của bạn (4 và 5 cần pytest đã cài)
cd .. && python src/superset/provision.py                  # dataset, metric, dashboard mẫu, bật nhúng (từ thư mục nhom01-65httt/)
```
Tài khoản đăng nhập website: quản trị `APP_ADMIN_*` và nhà đầu tư mẫu `APP_DEMO_*` trong `.env` (backend tự tạo khi khởi động); Superset `SUPERSET_ADMIN_*`; n8n tạo chủ sở hữu ở lần đầu mở (xem `src/n8n/README.md`). Địa chỉ: backend http://localhost:8000/docs, web http://localhost:5173, Superset http://localhost:8088, n8n http://localhost:5678.

## 2. Mỗi người bắt đầu từ đâu

| Người | Việc ở giai đoạn 2 | Điểm bắt đầu (đã có sẵn) | Còn là dữ liệu mẫu (`stub`) cần làm thật |
|-------|--------------------|--------------------------|------------------------------------------|
| **TV2** | Trang Mã cổ phiếu, theo dõi, cảnh báo, chat, quản trị | `src/backend/app/routers/tv2/` (mã, watchlist, cảnh báo, quản trị đã chạy thật), `src/frontend/src/pages/tv2/StocksPage.jsx` | `POST /api/chat` (chatbot giải thích dự báo) |
| **TV3** | Dashboard Superset, trang Thị trường và Ngành | `src/superset/spec.py` (10 dataset, metric, 2 dashboard mẫu), `routers/tv3/market_sectors.py`, `pages/tv3/SectorsPage.jsx`, `docs/superset_dataset_metric.md` | `GET /api/sectors/{icb_l2_code}` (chi tiết ngành) |
| **TV4** | Nhập CSV, trang Dự báo và khuyến nghị, tài khoản, báo cáo | `ingestion/templates/` + `python -m ingestion.cli load-csv` (đã chạy thật), `routers/tv4/predictions.py` (dự báo, độ chính xác, khuyến nghị đã thật), `pages/tv4/ForecastPage.jsx` | không còn stub; cần nhập CPI, ETF, cá nhân theo tuần rồi huấn luyện lại (GĐ3) |
| **TV5** | Tin tức, vĩ mô, cảm xúc chuẩn, cảnh báo n8n | `routers/tv5/news_macro.py`, `pages/tv5/NewsPage.jsx`, `src/n8n/workflows/alert-dispatch-sample.json`, `docs/huong_dan_gan_nhan_cam_xuc.md` + `data/samples/sentiment_validation_sample.csv` | `GET /api/macro/correlation`; nút gửi email của workflow cảnh báo (đang `NoOp`) |

**Hướng dẫn chi tiết từng người (việc, tiêu chí nghiệm thu, kiểm thử, điểm nối) nằm ở `docs/Ke_hoach_thuc_hien_BTL_Nhom01.md` mục 3; ràng buộc bắt buộc ở mục 7 dưới đây.** Quy ước nhánh, Pull Request, ranh giới thư mục: README mục 5. Thêm endpoint, dashboard, workflow: `docs/api_contract.md` mục 6, `src/n8n/README.md`. API và schema đã **chốt**: đổi phải báo cả nhóm (`docs/openapi.json` có test so với API thật).

## 3. Gói bàn giao: 10 hạng mục

Kiểm tra bằng lệnh `python -m handover.check` (từ `src/`); mỗi hạng mục chạy kiểm tra thật (truy vấn kho, gọi HTTP, chạy pytest theo nhóm). Lần chạy bàn giao: 10/10 đạt trên hệ thống chính và trên hệ thống dựng lại từ đầu (chi tiết ở `docs/kiem_thu_tu_dau.md` mục 4); trên hệ thống dựng lại còn có 281 pytest, 145 dbt test, 8 test giao diện đều qua.

| # | Hạng mục | Kiểm tra | Tài liệu |
|---|----------|----------|----------|
| 1 | `docker compose up` chạy cả hệ thống | 5 dịch vụ HTTP và PostgreSQL sống | README mục 3.2 |
| 2 | `dw` có dữ liệu thật và độ phủ đúng | số dòng tối thiểu từng bảng, giá từ 09/2020 | `docs/thiet_ke_kho.md`, README mục 3.4–3.5 |
| 3 | Dataset và metric Superset | mỗi metric khớp SQL gốc trên bảng fact | `docs/superset_dataset_metric.md` |
| 4 | Backend, auth, phân quyền, nhúng Superset, frontend | test phân quyền theo vai trò; 8 test frontend | `docs/api_contract.md` mục 3–4 |
| 5 | API contract chốt | `docs/openapi.json` khớp API thực | `docs/api_contract.md` |
| 6 | Mô hình: `fact_prediction`, `fact_news_sentiment`, nhãn cụm, khuyến nghị; API mô hình | dbt test và test hợp đồng | `docs/ml_ket_qua.md` |
| 7 | Tập mẫu cảm xúc 390 bài cho TV5 | đã xuất, cột `label_human` trống, có hướng dẫn và công cụ kiểm tra | `docs/huong_dan_gan_nhan_cam_xuc.md` |
| 8 | Bộ mẫu: trang React, router API, workflow n8n, CSV | mẫu có mặt; bộ nạp CSV và workflow có test | `src/ingestion/templates/README.md`, `src/n8n/README.md` |
| 9 | Chạy lại ETL qua API, có nhật ký | `POST /api/admin/etl/run` job `quality` ghi `app.etl_runs` và `dw.dq_log` | `docs/api_contract.md` mục 5 |
| 10 | Hướng dẫn nhánh, PR, quy ước | README mục 4–5, hook commit, `CLAUDE.md` | README |

## 4. Kết quả đáng biết (trung thực, để không ai bất ngờ)

- **Dự báo chiều dòng tiền ngành** (63,4%) chưa vượt có ý nghĩa mô hình cơ sở "tuần sau giống tuần này" (62,6%); chỉ dự báo **giá trị** ròng tốt hơn rõ. **Khuyến nghị** khớp chiều dòng tiền tuần sau (tăng, chắc chắn cao 70% so với giảm, chắc chắn cao 24%) nhưng không tạo lợi suất ngành vượt mua đều sau phí. Nên trình bày là công cụ theo dõi dòng tiền, không phải tín hiệu sinh lời.
- **Cảm xúc**: 69,6% trên nhãn do Claude gán; liên hệ với lợi suất thật yếu và chủ yếu cùng phiên. Nhãn người của TV5 mới là chuẩn cuối.
- **Phân cụm**: hành vi mua/bán ròng của một mã không bền theo thời gian; cụm dùng để mô tả thanh khoản, mức hoạt động khối ngoại và biến động.
- **Insight nháp** (5 phát hiện có số liệu): `docs/insight_nhap.md`, nhóm cần chọn và chốt ở giai đoạn 3.

## 5. Giới hạn đã biết

| Vấn đề | Ảnh hưởng | Hướng xử lý |
|--------|-----------|-------------|
| Nguồn là API/trang công khai không chính thức (VNDirect, CafeF, Vietcap, RSS) | Có thể đổi hoặc chặn; tự doanh theo mã chỉ từ 17/05/2022 | Lưu `raw` ngay khi lấy; kiểm tra `python -m ingestion.cli check`; ghi rõ trong báo cáo (`docs/bao_cao_nguon.md`) |
| Chưa có dự báo trực tiếp cho tuần kế tiếp | Trang Dự báo hiện chỉ có dự báo quá khứ | Sau 15h thứ Sáu: `ingestion.cli daily` → dbt → `ml.forecast` → `ml.recommend` |
| Mô hình học máy chạy bằng lệnh, chưa trong `etl-runner` và n8n; `POST /ml/sentiment` trong Docker trả `stub` | Cần chạy tay sau khi có dữ liệu mới | Thêm job `ml` vào etl-runner (cần torch trong image) ở GĐ2–3 |
| Job tin tức đầy đủ (30–40 phút) chưa được n8n lên lịch | Tin cũ chưa tự làm sạch hằng ngày | Thêm workflow lịch ban đêm (`src/n8n/README.md`) |
| Embedding toàn kho mất ~85 phút CPU lần đầu | Máy mới chạy `ml.sentiment` lần đầu rất lâu nếu không có `data/ml_cache/` | Dùng gói seed kèm bộ nhớ đệm |
| Cấu hình nhúng Superset là cấu hình phát triển; chưa giới hạn số lần đăng nhập sai | Chưa an toàn để công khai ra Internet | Siết trước khi triển khai |
| Giao diện web chưa có người kiểm thử thủ công qua trình duyệt | Lỗi hiển thị có thể còn | TV2–TV5 kiểm thử khi làm trang của mình; checklist ở `docs/kiem_thu_tu_dau.md` mục 5 |
| Chưa có CPI, ETF, nhà đầu tư cá nhân theo tuần | Mô hình thiếu ba nhóm đặc trưng | TV4 nhập CSV (bộ nạp đã sẵn); huấn luyện lại ở GĐ3 |
| Cổ phiếu mới niêm yết hoặc dưới 200 phiên (499 mã) không có cụm học được | Nhãn `chua_du_du_lieu` | Tự có cụm khi đủ dữ liệu, chạy lại `ml.clustering` |

## 6. Họp giao việc (30–45 phút) và kịch bản demo

Chuẩn bị: hệ thống chạy sẵn với gói seed dev, đã `provision.py`; hai tài khoản (quản trị, nhà đầu tư) đăng nhập sẵn ở hai cửa sổ; `docs/insight_nhap.md` mở sẵn.

| Phút | Nội dung |
|------|----------|
| 0–5 | Mục tiêu giai đoạn 2 và cách chia việc (bảng mục 2); mỗi người nhận một việc đầu tiên cụ thể |
| 5–20 | **Demo:** (1) đăng nhập khách → thấy giới hạn tin, dashboard tổng quan; (2) nhà đầu tư → luân chuyển ngành (Superset nhúng), mã cổ phiếu có nhãn cụm, tin kèm cảm xúc; (3) trang Dự báo: dự báo, độ chính xác theo tuần so với mô hình cơ sở, khuyến nghị kèm tín hiệu đảo chiều và lệch pha; (4) quản trị → chạy lại ETL, xem `dq_log` và `etl_runs`; (5) n8n: workflow `etl-after-close` và cách bật |
| 20–30 | Cách làm việc: nhánh/PR/hook commit (README mục 4–5), cách thêm endpoint, trang, dashboard; chạy `python -m handover.check` trên máy mình |
| 30–40 | Kết quả trung thực của mô hình (mục 4) và giới hạn (mục 5): nhóm thống nhất cách trình bày; chọn insight cho báo cáo |
| 40–45 | Câu hỏi; chốt hạn đầu tiên cho từng người |

## 7. Ràng buộc khi làm tiếp (bắt buộc với TV2–TV5)

Các ràng buộc này tồn tại vì một lý do cụ thể đã gặp hoặc đã được kiểm thử; mã R1–R12 trùng với bảng tóm tắt ở `Ke_hoach_thuc_hien_BTL_Nhom01.md` mục 3.0. Hướng dẫn chi tiết từng người, kèm việc, tiêu chí nghiệm thu và kiểm thử, nằm ở cùng tài liệu (mục 3, TV2 đến TV5).

### 7.1. Quy trình và mã nguồn

| Mã | Ràng buộc | Lý do | Cách kiểm tra |
|----|-----------|-------|---------------|
| R1 | Chỉ sửa trong thư mục của mình; file chung (`routes.jsx`, `main.py`, `Layout.jsx`, `components/`, `package.json`, `docker-compose.yml`) chỉ qua PR có TV1 và người liên quan xem | Bốn người làm song song, xung đột merge là rủi ro lớn nhất của GĐ2 | Xem phần "Files changed" của PR: mọi đường dẫn nằm trong thư mục của người mở PR, trừ dòng thêm vào file chung |
| R2 | API đã chốt không đổi tên trường, kiểu, mã lỗi; chỉ thêm trường tùy chọn hoặc endpoint mới, sau khi báo cả nhóm và cập nhật `docs/api_contract.md`, `docs/openapi.json` | Người khác đã code theo schema; contract được test so với API thật | `pytest tests/smoke/test_api.py -k openapi` (so `docs/openapi.json` với API thực); chạy `python src/backend/export_openapi.py` sau khi đổi API |
| R3 | Backend chỉ đọc `dw`, chỉ ghi `app`; SQL dùng tham số; không đọc `raw`/`stg` | Tài khoản `bi_app` chỉ có quyền đọc `dw` và ghi `app`; ghép chuỗi SQL gây lỗ hổng | Review PR; test; không có chuỗi f-string ghép biến vào câu SQL |
| R4 | Không `docker compose down -v`; không `dbt run --select dim_stock` thiếu dấu `+`; không xóa/ghi đè bảng kết quả mô hình (`dim_model`, `fact_prediction`, `fact_news_sentiment`, `fact_recommendation`, `stock_cluster`); thử nghiệm phá hủy làm trong dự án compose riêng (`-p`) | `down -v` xóa 4,8 GB dữ liệu thu thập nhiều ngày; `dim_stock` bị dbt dựng lại sẽ làm PostgreSQL xóa các view phụ thuộc; các bảng mô hình cấu hình không bao giờ nạp lại | `dbt run` đã cấu hình `full_refresh: false` cho bảng mô hình; hướng dẫn dựng dự án riêng: `docs/kiem_thu_tu_dau.md` mục 1; có gói seed để phục hồi |
| R5 | Không commit `.env`, mật khẩu, khóa API (LLM, SMTP), `data/`, gói seed, `src/dbt_dw/target/` | Lộ bí mật; dữ liệu lớn làm hỏng kho | `.gitignore`; hook commit; xem `git status` trước khi `git add <thư mục nhóm>/` |
| R12 | Thêm thư viện (npm, pip) phải báo trước, một thư viện biểu đồ duy nhất do TV3 thêm; không thêm thư viện nặng (torch, scikit-learn) vào image backend | `package-lock.json`, image Docker là chỗ xung đột; image backend hiện nhẹ, mô hình học máy nằm ngoài | Xem diff `package.json`, `requirements*.txt` trong PR |
| Commit | `loại(nhom01-65httt): mô tả`, `loại` là `feat`, `fix`, `docs`, `chore`; **không** có `Co-Authored-By` của AI; chỉ `git add <thư mục nhóm>/`; không commit thẳng vào `main`; không `--no-verify` | Quy chuẩn của giảng viên và của nhóm (`README.md` mục 4, `CLAUDE.md`) | Hook `commit-msg` (bật bằng `sh tools/setup-git-hooks.sh`; `git config core.hooksPath` phải ra `nhom01-65httt/tools/hooks`) |

### 7.2. Dữ liệu và mô hình

| Mã | Ràng buộc | Lý do | Cách kiểm tra |
|----|-----------|-------|---------------|
| R6 | Không dùng dữ liệu tương lai: số liệu vĩ mô nhập tay phải có `published_date` thật (không sớm hơn thực tế); chỉ số tháng không đưa vào dataset theo ngày; mọi tính toán chỉ dùng thông tin có tại thời điểm đó | Mô hình dự báo và backtest được kiểm tra không nhìn trước; số công bố muộn sẽ làm hỏng điều đó | Bộ nạp CSV chặn `published_date` sớm hơn cuối kỳ; dbt test `manual_macro_published_after_period`; test nhìn trước trong `tests/unit/test_ml.py`, `test_recommend.py` |
| R10 | Không sửa mô hình (`src/ml`), không gọi thư viện học máy từ backend; cần đặc trưng hay kết quả mới thì nhờ TV1 qua Issue | Mọi mô hình có kỷ luật chọn cấu hình (tập chọn và tập báo cáo tách riêng) và test chống rò rỉ; sửa tay phá kỷ luật đó | Review PR; `pytest tests/unit/test_ml*.py` |
| Nhập tay | Số liệu CSV phải là số thật có nguồn; **không** dùng số ước lượng, số nội suy, số do AI sinh; không nạp dòng "Mẫu minh họa"; mọi lần nạp qua `ingestion.cli load-csv` để có `dq_log` | Báo cáo phải truy được nguồn; bộ nạp từ chối dòng mẫu và dòng sai | `dw.dq_log` (`source = 'manual_csv'`); `docs/nhap_lieu_thu_cong.md` |
| Nhãn người | TV5 gán nhãn mù, không dùng AI gán thay; tập 390 bài không dùng huấn luyện cho đến khi đo xong lần đầu | Mục đích là có tập kiểm tra độc lập của con người | `python -m ml.sentiment_check` |
| Bảng mô hình | Giữ nguyên schema `fact_prediction`, `fact_recommendation`, `fact_news_sentiment`, `stock_cluster`; TV1 chạy lại mô hình ở GĐ3 chỉ thay giá trị | Trang và dashboard của bạn không phải sửa khi mô hình đổi | dbt test `ml_*`; `tests/smoke/test_ml_warehouse.py` |
| Nhãn cụm | Giao diện không giả định tập nhãn cụm cố định: nhãn lạ hiện nguyên văn | TV1 huấn luyện lại ở GĐ3 có thể đổi số cụm và tên cụm | Test với nhãn giả |

### 7.3. Trình bày kết quả và phân quyền

| Mã | Ràng buộc | Lý do | Cách kiểm tra |
|----|-----------|-------|---------------|
| R7 | Trang hay email có dự báo, khuyến nghị, cảm xúc: luôn kèm `Disclaimer`, **mô hình cơ sở bên cạnh** và nói đúng kết quả (dự báo chiều dòng tiền chưa vượt có ý nghĩa thống kê cơ sở; khuyến nghị không tạo lợi suất vượt sau phí; cảm xúc chỉ có ý nghĩa cùng phiên); không "nên mua/nên bán", không "độ chính xác cao" | Kết quả thật là vậy; đề tài bị hỏi khi bảo vệ; đây không phải lời khuyên đầu tư | TV1 duyệt chữ trên trang dự báo, khuyến nghị, chatbot trước khi nộp; `ml_ket_qua.md` mục 2, 4, 5 |
| R8 | Phân quyền khách < nhà đầu tư < quản trị, **kiểm tra ở backend**; khách chỉ xem tổng quan, tối đa 5 tin, dashboard `overview`; vai trò lấy từ cơ sở dữ liệu, không tin vai trò ghi trong token | Ẩn nút ở giao diện không bảo vệ được dữ liệu | Bảng `CONTRACT` trong `tests/smoke/test_api.py`: mỗi endpoint mới thêm một dòng và ba trường hợp (không đăng nhập, sai vai trò, đúng vai trò) |
| R9 | Đơn vị: tiền tỷ đồng (`_bn`), giá đồng (`_vnd`, kho lưu nghìn đồng, API nhân 1.000); ngày `YYYY-MM-DD`; múi giờ Việt Nam; tuần bắt đầu thứ Hai | Mọi người dùng chung dữ liệu và biểu đồ; nhầm đơn vị làm sai KPI | `docs/api_contract.md` mục 1; test so với SQL gốc |
| R11 | Không đưa toàn văn bài báo ra API, giao diện, email; chỉ tiêu đề, nguồn, ngày, cảm xúc, tóm tắt ngắn, liên kết bài gốc | Bản quyền của nguồn tin | `GET /api/news` không có trường toàn văn; review PR |
| Chatbot | LLM chỉ chọn truy vấn trong danh sách có sẵn và điền tham số; không sinh SQL; chạy được khi không có khóa LLM; câu hỏi ngoài phạm vi bị từ chối; nội dung bài báo là dữ liệu không tin cậy | Chống truy vấn tùy ý, chống chèn chỉ dẫn (prompt injection), chi phí và độ ổn định khi demo | Test từng truy vấn so với SQL gốc; test từ chối; test bộ định tuyến dự phòng |
| Superset | Dashboard dựng bằng giao diện phải xuất vào `src/superset/dashboards/`; luôn nhúng qua `/api/superset/embed/{key}` (guest token 10 phút, một dashboard); mỗi metric mới khớp SQL gốc | Dashboard chỉ nằm trong volume Superset sẽ mất khi `down -v`; không để lộ tài khoản Superset | `tests/smoke/test_superset.py`; dựng lại từ đầu trong dự án compose riêng |

### 7.4. Chất lượng trước khi gộp PR

Mỗi PR: `ruff check .` sạch; `pytest` qua (unit; smoke khi đổi backend, kho hoặc Superset: `pytest -m "smoke or not smoke"`); `cd src/frontend && npm test` khi đổi giao diện; `python dbt_dw/run.py test` khi đổi `dbt_dw`; `docs/openapi.json` khớp khi đổi API; tài liệu liên quan cập nhật; ảnh chụp màn hình trang đã đổi; mô tả ngắn *làm gì, kiểm tra thế nào, ảnh hưởng ai*. Cuối mỗi tuần TV1 chạy `python -m handover.check` trên nhánh chung và báo ai làm hỏng. Thời gian phản hồi API mới: dưới 2 giây cho truy vấn thông thường (`tests/smoke/test_api.py` có test mẫu); phân trang tối đa 100 dòng mỗi trang.

## 8. Việc TV1 vẫn làm trong GĐ2 và cách nhờ giúp

TV1: phản hồi Issue và review PR trong 1 ngày làm việc; cập nhật dữ liệu hằng ngày sau 15h (`ingestion.cli daily` → `etl.news.pipeline` → `dbt run`) và dự báo, khuyến nghị tuần mới chiều thứ Sáu; thêm view `dw` hoặc quyền đọc khi có lý do chính đáng; cùng TV3 chứng minh lưu và dựng lại dashboard từ đầu ngày 2 Tuần 4. Muốn nhờ: mở Issue trên kho Fork với bốn mục *việc đang làm, điều đã thử, lệnh và kết quả, kỳ vọng*. Đừng sửa phần của TV1 (R1, R4, R10) để "đi nhanh": báo, TV1 sửa trong ngày.
