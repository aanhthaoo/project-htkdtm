# Kiểm thử chạy lại từ đầu (N10)

Ngày chạy: 27/11/2026, trên một máy Windows 11, Docker Desktop. Mục tiêu: chứng minh người khác dựng được hệ thống và chuỗi dữ liệu → dbt → mô hình → API từ trạng thái sạch, đúng như README mô tả.

## 1. Cách làm và vì sao không dùng `docker compose down -v` trên hệ thống chính

`down -v` xóa vĩnh viễn volume PostgreSQL của hệ thống đang dùng (4,8 GB, hàng giờ thu thập, gồm tin CafeF crawl). Thay vào đó dựng **một dự án compose thứ hai, tách biệt** (`-p htkdtm_verify`: volume mới và cổng khác: PostgreSQL 25432, backend 28000, frontend 25173, Superset 28088, n8n 25678, etl-runner 28100) từ cùng mã nguồn, rồi chạy toàn bộ chuỗi trong đó. Hệ thống chính không bị động tới. Kết quả tương đương `down -v` → `up` cho mọi thành phần dùng mã trong kho.

Không chạy lại từ đầu (và lý do):
- **Thu thập toàn bộ lịch sử từ API ngoài** (`ingestion.cli vndirect`, `cafef-news-*`, `hf-*`, hàng giờ, có giới hạn tốc độ): dữ liệu `raw` được phục hồi từ gói seed. Đường thu thập vẫn được kiểm tra bằng unit test với dữ liệu lưu sẵn (`tests/unit/test_ingestion.py`, `test_source_fixtures.py`) và bằng một lần chạy thật `ingestion.cli daily` (bước 15).
- **Embedding toàn kho** (~85 phút CPU): dùng bộ nhớ đệm `data/ml_cache/`; phần tính embedding có test riêng (`test_embedding_co_bo_nho_dem_chi_tinh_bai_moi`).

## 2. Các bước, lệnh và thời gian

Tập lệnh tái lập: `tools/verify_rebuild.sh` (ghi thời gian vào `data/verify/steps.tsv`). Gói seed: `python -m handover.seed`.

| # | Bước | Lệnh | Thời gian | Kết quả |
|---|------|------|-----------|---------|
| 0a | Xuất gói đầy đủ từ hệ thống chính | `python -m handover.seed export full` (tương đương `pg_dump -Fc -n raw -n stg -n dw`) | 2 phút 13 giây (tệp 1,44 GB) | tệp `full_raw_stg_dw.dump` |
| 0b | Dựng dự án mới từ trạng thái rỗng | `docker compose -p htkdtm_verify --env-file data/verify/env up -d --build` | 27 giây | 6 dịch vụ healthy, cơ sở dữ liệu rỗng |
| 0c | Phục hồi `raw`, `stg`, `dw` | `python -m handover.seed restore data/seed/full_raw_stg_dw.dump --project htkdtm_verify` | 3 phút 50 giây | 4,4 GB; số dòng khớp từng bảng (khác biệt chỉ ở thứ đã đổi sau lúc xuất: bảng nhập tay mới, 4 chỉ số vĩ mô mới, 6 dòng nhật ký) |
| 1 | Tạo bảng raw mới | `python -m ingestion.cli init-db` | 1 giây | OK |
| 2 | Nạp seed dbt | `python dbt_dw/run.py seed` | 10 giây | OK |
| 3 | Xóa kết quả mô hình đã phục hồi | `TRUNCATE dim_model, stock_cluster, fact_prediction, fact_news_sentiment, fact_recommendation` | 0 giây | để chứng minh mô hình tạo lại được từ dữ liệu |
| 4 | **ETL tin tức** từ `raw` | `python -m etl.news.pipeline` | **19 phút 15 giây** | 315.957 bài, 130.417 bài dùng được |
| 5 | **dbt dựng lại toàn bộ** | `python dbt_dw/run.py run --full-refresh` | 93 giây | 41/41 mô hình |
| 6 | **Cảm xúc** | `python -m ml.sentiment` | 165 giây | 557.556 dòng; kiểm tra 400 bài: accuracy 68,3% (xem ghi chú dưới) |
| 7 | **Phân cụm** | `python -m ml.clustering` | 55 giây | K=4, 387 + 951 mã có cụm |
| 8 | Đưa nhãn cụm vào `dim_stock` | `python dbt_dw/run.py run --select "dim_stock+"` | 49 giây | OK |
| 9 | **Dự báo** | `python -m ml.forecast` | 83 giây | 3.819 dự báo; accuracy 63,37% (giống hệt hệ thống chính) |
| 10 | **Khuyến nghị và backtest** | `python -m ml.recommend` | 34 giây | 3.819 khuyến nghị |
| 11 | **dbt test** | `python dbt_dw/run.py test` | 21 giây | **145/145 qua** |
| 12 | Kiểm tra chất lượng | `python -m etl.quality_checks` | 9 giây | mọi kiểm tra đạt ngưỡng |
| 13 | Superset | `python src/superset/provision.py` | 12 giây | kết nối, 10 dataset, metric, 2 dashboard nhúng |
| 14 | n8n | `python src/n8n/build_workflows.py` + `n8n import:workflow` | 7 giây | 4 workflow |
| 15 | Thu thập ngày mới từ nguồn ngoài (đường ingestion) | `python -m ingestion.cli daily` (chạy sau các bước trên, trong cơ sở dữ liệu sạch) | 1 phút 19 giây | xong, không lỗi: 7–8 dòng mới mỗi chuỗi yfinance, 17 bài RSS mới, 14 bài CafeF chờ toàn văn |

Tổng các bước 1–14: **28 phút 14 giây**; cộng dựng, phục hồi và xuất gói: khoảng **38 phút** (không tính thu thập và embedding). Cả 14 bước thoát mã 0.

**Ghi chú về cảm xúc.** Bản dựng lại có 3.000 bài có nhãn (hệ thống chính 2.952) vì 48 bài tin ngày 24-25/11 nay đã có phiên giao dịch (lịch giao dịch trong kho mới tới 23/11 lúc chạy pipeline tin ở hệ thống chính). Tập kiểm tra vì vậy là 400 bài thay vì 352 (accuracy 68,3% thay vì 69,6%; mô hình chỉ TF-IDF 64,8% thay vì 65,9%). Hai con số đều đúng cho tập kiểm tra tương ứng; số trong `docs/ml_ket_qua.md` giữ theo 352 bài để so với lần trước. Bài học vận hành: sau khi thu thập ngày mới phải chạy lại pipeline tin (`etl.news.pipeline`) rồi `dbt run`, nếu không bài mới không có phiên.

## 3. Kiểm thử hồi quy trên hệ thống dựng lại

| Kiểm thử | Lệnh | Kết quả |
|----------|------|---------|
| dbt test | `python dbt_dw/run.py test` | **145/145 qua** (21 giây) |
| pytest, unit và smoke | `pytest tests -m "smoke or not smoke"` (biến môi trường trỏ tới cổng của dự án kiểm tra) | **281 qua** (3 phút 21 giây), gồm phân quyền, contract OpenAPI, Superset (metric khớp SQL gốc), mô hình trong kho, API mô hình, nạp CSV, ETL qua n8n |
| Test giao diện | `cd src/frontend && npm test` | **8/8 qua** (phân quyền route, API client) |
| Lint | `ruff check .` | sạch |

Hệ thống chính (đã chạy trước đó): 264 pytest, 138 dbt test, đều qua; sau đó thêm test nạp CSV, kiểm tra nhãn người, khuyến nghị và ETL (nay tổng 281 pytest, 145 dbt test).

## 4. Kiểm tra 10 hạng mục bàn giao (`python -m handover.check`)

Chạy trên hệ thống dựng lại từ đầu (4 phút 42 giây): **10/10 đạt**.

| # | Hạng mục | Kết quả |
|---|----------|---------|
| 1 | `docker compose up` chạy cả hệ thống | 5 dịch vụ HTTP và PostgreSQL sống |
| 2 | `dw` có dữ liệu thật, độ phủ đúng | giá 01/09/2020–25/11/2026; 1.839 mã; giá 2.487.026 dòng; dòng tiền 2.207.198; bài 315.957; quan hệ bài-mã/ngành 656.899 |
| 3 | Dataset và metric Superset khớp SQL gốc | 14 test qua |
| 4 | Backend: auth, phân quyền, nhúng Superset | 37 test qua |
| 5 | API contract chốt | 3 test qua (OpenAPI khớp API thực) |
| 6 | Mô hình và API mô hình | 22 test kho + 6 test API qua |
| 7 | Tập mẫu cảm xúc cho TV5 | 390 bài chưa gán nhãn, có hướng dẫn |
| 8 | Bộ mẫu chạy được | 15/15 tệp mẫu; 26 test qua |
| 9 | Chạy lại ETL qua API, có nhật ký | job `quality` thành công, `dq_log` thêm 52 dòng |
| 10 | Hướng dẫn nhánh, PR, quy ước | README, hook commit, `CLAUDE.md` có |

### Gói seed dev (chỉ schema `dw`)

Xuất từ hệ thống dựng lại: **187 MB, 36 giây** (`python -m handover.seed export dev`), nhỏ hơn gói đầy đủ (1,44 GB) khoảng 8 lần. Để chứng minh nó đủ dùng một mình, gói được phục hồi vào chính hệ thống dựng lại (thay toàn bộ schema `dw`) rồi chạy lại các hạng mục 2 đến 6; kết quả ở mục 6.

## 5. Chưa kiểm tra được bằng tự động: checklist giao diện thủ công

Giao diện chưa có người dùng thật thao tác qua trình duyệt (test tự động chỉ phủ phân quyền route và API). Mỗi người kiểm tra trang của mình theo danh sách sau khi hệ thống chạy ở http://localhost:5173:

- [ ] Khách: mở trang chủ, xem tổng quan thị trường và tối đa 5 tin; mở trang cần đăng nhập thì bị chuyển tới trang đăng nhập.
- [ ] Đăng ký tài khoản mới (mật khẩu < 8 ký tự bị từ chối), đăng nhập, đăng xuất; token hết hạn thì tự đăng xuất.
- [ ] Nhà đầu tư: dashboard Luân chuyển ngành (Superset nhúng) hiển thị, đổi bộ lọc; dashboard Tổng quan hiển thị cho khách.
- [ ] Trang Mã cổ phiếu: tìm mã, xem nhãn cụm, thêm và xóa mã khỏi danh sách theo dõi.
- [ ] Trang Dự báo: dự báo 19 ngành, thứ hạng, độ chính xác theo tuần so với mô hình cơ sở, khuyến nghị kèm tín hiệu và lưu ý đầu tư.
- [ ] Trang Tin tức: tin kèm điểm cảm xúc, lọc theo mã và ngành.
- [ ] Quản trị: danh sách người dùng, đổi vai trò (không tự hạ quyền được), chạy lại ETL và xem nhật ký `etl_runs`, xem `dq_log`.
- [ ] Giao diện điện thoại (chiều rộng ~390 px): không bị tràn ngang.

## 6. Kết quả thử gói seed dev

Phục hồi `dw_dev.dump` vào hệ thống dựng lại (`python -m handover.seed restore data/seed/dw_dev.dump --project htkdtm_verify`, thay toàn bộ schema `dw`): **60 giây**. Sau đó các hạng mục 2 đến 6 vẫn đạt (5/5): số dòng và độ phủ đúng, Superset khớp SQL gốc, 37 test phân quyền, contract, mô hình và API mô hình. Vậy một thành viên chỉ cần gói dev (187 MB) và `docker compose up` là có hệ thống đủ dữ liệu để làm việc, không cần thu thập hay dựng lại. `pg_restore` báo "errors ignored: 1" (câu `CREATE SCHEMA` vì schema đã được tạo sẵn để giữ quyền mặc định): bình thường.

## 7. Sự cố gặp khi kiểm tra và cách xử lý

| Sự cố | Nguyên nhân | Xử lý |
|-------|-------------|-------|
| Lần chạy đầu của `tools/verify_rebuild.sh` kết thúc sau vài giây, 12 bước bị bỏ qua | Tệp nhật ký dùng đường dẫn tương đối nên các bước chạy trong `src/` không ghi được, lệnh bị bỏ qua | Dùng đường dẫn tuyệt đối; chạy lại từ đầu (chưa có gì được chạy ở lần đầu) |
| Bản dựng lại có 3.000 bài có nhãn thay vì 2.952 | Lịch giao dịch ở hệ thống chính mới tới 23/11 lúc chạy pipeline tin, nên 48 bài ngày 24-25/11 chưa có phiên | Không phải lỗi mã; sau thu thập ngày mới luôn chạy lại `etl.news.pipeline` rồi `dbt run` |
| Ngưỡng số dòng của `handover.check` đặt theo ước đoán nên báo thiếu ở lần chạy thử đầu | Đặt cao hơn thực tế (dòng tiền 2,2 triệu, không phải 3 triệu) | Đặt lại bằng khoảng 95% số dòng thật lúc bàn giao |
| Lần chạy pytest đầu trên hệ thống mới chỉ có 160 test | `pytest` mặc định bỏ nhóm `smoke` | Chạy với `-m "smoke or not smoke"` (README mục 3.3 nêu `pytest -m smoke`) |
| `down -v` sẽ xóa dữ liệu thật | Đã tránh bằng dự án compose tách biệt | Mục 1; gói seed là bản sao lưu |

## 8. Dọn dẹp

Dự án kiểm tra dùng khoảng 5 GB đĩa và **đã được xóa** sau khi ghi kết quả (`docker compose -p htkdtm_verify --env-file data/verify/env down -v`; hệ thống chính vẫn chạy bình thường, dbt test 145/145 qua sau đó). Muốn lặp lại: dựng lại như mục 2 (các lệnh trong `tools/verify_rebuild.sh`).
