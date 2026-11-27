# Đồ Án Hệ Thống Kinh Doanh Thông Minh - Nhóm 01 (Lớp 65HTTT)

## 1. Giới thiệu đề tài
- **Tên đề tài:** Hệ thống phân tích dòng tiền và luân chuyển ngành trên thị trường chứng khoán Việt Nam (BI + AI)
- **Môn học:** Hệ Thống Kinh Doanh Thông Minh (HTKDTM)
- **Lớp học phần:** 65HTTT
- **Trạng thái:** giai đoạn 1 (nền tảng và mô hình, TV1) đã xong và đóng gói bàn giao; TV2–TV5 làm tiếp theo `docs/Ke_hoach_thuc_hien_BTL_Nhom01.md`. Báo cáo bàn giao: `docs/ban_giao_GD1.md`.

## 2. Cấu trúc thư mục
- `danhsachnhom.md`: Danh sách thành viên và phân công nhiệm vụ.
- `docs/`: Tài liệu: kế hoạch, thiết kế kho (`thiet_ke_kho.md`), API contract (`api_contract.md`, `openapi.json`), Superset (`superset_dataset_metric.md`), mô hình (`ml_ket_qua.md`), insight nháp (`insight_nhap.md`), bàn giao (`ban_giao_GD1.md`, `kiem_thu_tu_dau.md`), ghi chú nguồn dữ liệu (`bao_cao_nguon.md`, `danh_gia_nguon_du_lieu.md`).
- `src/`: mã nguồn: `ingestion/` (thu thập, nạp CSV nhập tay), `etl/` (làm sạch tin, kiểm tra chất lượng), `dbt_dw/` (kho dữ liệu), `ml/` (cảm xúc, phân cụm, dự báo, khuyến nghị), `backend/` (FastAPI), `frontend/` (React), `superset/`, `n8n/`, `etl_runner/`, `database/` (khởi tạo PostgreSQL), `handover/` (kiểm tra bàn giao, gói seed).
- `tests/`: `unit/` (không cần Docker), `smoke/` (cần hệ thống chạy). `tools/`: hook Git. `data/`: dữ liệu và bộ nhớ đệm, **không đưa vào git**.

## 3. Hướng dẫn cài đặt và khởi chạy
Thông tin thành viên và phân công xem tại [`danhsachnhom.md`](./danhsachnhom.md).

### 3.1. Yêu cầu
- Docker Desktop (Compose v2), Python 3.12 (chỉ cần để chạy test), Node 22 (chỉ cần nếu chạy frontend ngoài Docker).

### 3.2. Chạy toàn bộ hệ thống
Chạy các lệnh tại thư mục `nhom01-65httt/`:
```bash
cp .env.example .env        # đổi mật khẩu trong .env nếu cần, không commit .env
docker compose up -d --build
docker compose ps           # chờ tất cả dịch vụ ở trạng thái healthy (Superset mất khoảng 1–2 phút)
```

| Dịch vụ | Địa chỉ | Ghi chú |
|---------|---------|---------|
| Backend (FastAPI) | http://localhost:8000/health | Tài liệu API: `/docs`; contract chốt: `docs/api_contract.md` |
| Frontend (React) | http://localhost:5173 | Đăng ký/đăng nhập, dashboard nhúng; tài khoản quản trị tạo từ `APP_ADMIN_*` trong `.env` |
| Bộ chạy ETL | http://localhost:8100/health | Chạy thu thập, dbt, kiểm tra chất lượng theo yêu cầu của n8n hoặc trang quản trị |
| Superset | http://localhost:8088 | Tài khoản `SUPERSET_ADMIN_*` trong `.env` |
| n8n | http://localhost:5678 | Tạo tài khoản chủ sở hữu ở lần đầu mở |
| PostgreSQL | localhost:5432 | Database `bi_dw`, các schema `raw`, `stg`, `dw`, `app` |

Nếu cổng bị trùng với phần mềm khác trên máy, đổi `*_PORT` trong `.env`.

Tài khoản PostgreSQL: `bi_admin` (toàn quyền, dùng cho ETL và dbt), `bi_app` (backend: đọc `dw`, ghi `app`), `bi_readonly` (Superset: chỉ đọc `dw`).

Dừng hệ thống: `docker compose down`. Xóa cả dữ liệu để chạy lại từ đầu: `docker compose down -v` (script khởi tạo database chỉ chạy khi volume rỗng). **Cẩn thận:** `down -v` xóa vĩnh viễn toàn bộ dữ liệu trong PostgreSQL (hàng giờ thu thập); hãy xuất gói seed trước (mục 3.7) hoặc thử trong một dự án tách biệt (mục 3.8).

### 3.3. Kiểm thử
```bash
pip install -r src/backend/requirements-dev.txt
pytest                # unit test, không cần Docker
pytest -m smoke       # smoke test, cần hệ thống đang chạy bằng docker compose
ruff check .
```

### 3.4. Thu thập dữ liệu (seed ban đầu và cập nhật hằng ngày)
Mã thu thập ở `src/ingestion/`. Cài thư viện rồi chạy từ thư mục `src/` (cần PostgreSQL đang chạy):
```bash
pip install -r src/ingestion/requirements.txt
cd src
python -m ingestion.cli init-db            # tạo các bảng raw
python -m ingestion.cli vndirect           # giá, khối ngoại, tự doanh toàn thị trường từ 09/2020 (khoảng 1,5–2 giờ)
python -m ingestion.cli vietcap-symbols    # danh sách mã và nhóm chỉ số
python -m ingestion.cli vietcap-companies  # ICB cấp 2 và 4, vốn hóa (khoảng 2 giờ, tiếp tục được nếu bị ngắt)
python -m ingestion.cli cafef-index        # VN-Index
python -m ingestion.cli yfinance           # 7 chuỗi quốc tế
python -m ingestion.cli hf-download && python -m ingestion.cli hf-load   # EconVNNews (1,5 GB)
python -m ingestion.cli cafef-news-list && python -m ingestion.cli cafef-news-fetch  # tin CafeF 10/2024 – nay (vài giờ)
python -m ingestion.cli rss                # tin mới từ RSS
python -m ingestion.cli daily              # cập nhật hằng ngày (gộp các bước nhẹ)
python -m ingestion.cli status             # số dòng từng bảng và trạng thái các lần chạy
python -m ingestion.cli check              # kiểm tra thu thập đã XONG chưa (mã thoát 0 = xong hết)
```
Mọi lệnh chạy lại được và tiếp tục được từ chỗ dừng. Cách kiểm tra đã xong chưa: `docs/kiem_tra_thu_thap.md`. Lịch cập nhật hằng ngày: `docs/ke_hoach_thu_thap_hang_ngay.md`. Dữ liệu tải về (EconVNNews) nằm ở `data/` và không đưa vào git.

### 3.5. Làm sạch, xây dựng kho dữ liệu và kiểm tra chất lượng
Chạy sau khi đã có dữ liệu `raw` (từ thư mục `src/`):
```bash
pip install -r dbt_dw/requirements.txt
python dbt_dw/run.py seed                   # nạp seed (ICB, nhóm nhà đầu tư, nguồn tin, chỉ số)
python dbt_dw/run.py run                    # dựng stg và dw (fact nạp tăng dần; thêm --full-refresh để dựng lại từ đầu)
python -m etl.news.pipeline                 # làm sạch tin, gán phiên (15h), nhận diện mã/ngành, đánh dấu trùng
python dbt_dw/run.py run --select dim_article bridge_article_entity   # đưa tin vào dw
python dbt_dw/run.py test                   # kiểm thử dbt (khóa, khóa ngoại, tính nhất quán...)
python -m etl.quality_checks                # đối chiếu chéo, ghi dw.dq_log
python -m etl.news.crosscheck               # đối chiếu số khối ngoại trong bài tổng hợp phiên
python -m etl.news.samples                  # xuất mẫu gán nhãn và mẫu kiểm tra thủ công vào data/samples/
pytest -m smoke tests/smoke/test_warehouse.py   # kiểm thử 5 thao tác OLAP trên kho thật
```
`dim_model`, `dim_event`, `stock_cluster`, `fact_prediction`, `fact_news_sentiment` do mô hình hoặc nhập tay ghi vào nên được cấu hình **không bao giờ xóa nạp lại** (`full_refresh: false`), `--full-refresh` không làm mất dữ liệu của chúng.

### 3.5b. Superset: dataset và metric dùng chung
```bash
python dbt_dw/run.py run --select superset         # dựng các dataset (view và materialized view trong dw), từ thư mục src/
python src/superset/provision.py                   # tạo/cập nhật kết nối BI_DW, dataset, metric, biểu đồ thử (chạy lại được), từ thư mục nhom01-65httt/
pytest -m smoke tests/smoke/test_superset.py       # mỗi metric phải khớp SQL gốc trên bảng fact
```
Danh sách dataset, metric, bộ lọc dùng chung: `docs/superset_dataset_metric.md`. Định nghĩa gốc: `src/superset/spec.py`.

### 3.5c. Website, phân quyền, n8n
```bash
docker compose up -d --build                   # thêm JWT_SECRET, SERVICE_KEY, APP_ADMIN_* vào .env trước (xem .env.example)
python src/superset/provision.py               # dataset, metric, dashboard mẫu và bật nhúng (lần đầu và khi đổi spec.py)
python src/backend/export_openapi.py           # cập nhật docs/openapi.json sau khi đổi API
python src/n8n/build_workflows.py              # sinh lại workflow n8n; cách nhập và bật: src/n8n/README.md
cd src/frontend && npm ci && npm test          # test giao diện (phân quyền route, API client)
```
Vai trò: khách (không đăng nhập) < nhà đầu tư < quản trị. Mỗi thành viên chỉ thêm tệp vào thư mục của mình: `src/backend/app/routers/tvN/`, `src/frontend/src/pages/tvN/` và một dòng vào `src/frontend/src/routes.jsx`. Chi tiết: `docs/api_contract.md` mục 6.

### 3.5d. Mô hình học máy (N8)
```bash
cd src && pip install -r ml/requirements.txt
python -m ml.sentiment --embed-only             # (một lần, ~85 phút trên CPU) tính embedding cho mọi bài, lưu data/ml_cache; các lần sau chỉ tính bài mới
python -m ml.sentiment                          # cảm xúc tin tức (TF-IDF + embedding) -> dw.fact_news_sentiment (nhãn: src/ml/labels/)
python -m ml.clustering                         # phân cụm cổ phiếu (cụm chính + nhóm phụ) -> dw.stock_cluster (thêm --dry-run để chỉ xem)
python -m ml.forecast                           # dự báo dòng tiền ngành x tuần -> dw.fact_prediction (thêm --dry-run để chỉ xem kết quả)
python -m ml.recommend                          # khuyến nghị tăng/giảm tỷ trọng ngành + backtest sơ bộ -> dw.fact_recommendation (--dry-run chỉ xem)
python dbt_dw/run.py run --select "dim_stock+"  # đưa nhãn cụm vào dim_stock. PHẢI có dấu +, nếu thiếu dbt xóa các view phụ thuộc
python -m ml.sentiment_validity                 # kiểm chứng điểm cảm xúc với lợi suất thật của mã (chỉ đọc)
```
Thí nghiệm cải thiện (đường cong học, so biến thể, chọn bài cần gán nhãn, kiểm chứng cụm theo thời gian): `python -m ml.sentiment_experiments curve|select|compare --out <thư mục>`, `python -m ml.clustering_experiments --out <thư mục>`; kết quả đã chạy lưu ở `docs/ml_thi_nghiem/`.

Kết quả, giới hạn và cách đọc: `docs/ml_ket_qua.md`; bản nháp insight có số liệu: `docs/insight_nhap.md` (số liệu: `python -m ml.insights`). Nhãn cảm xúc huấn luyện do Claude gán (chưa phải nhãn chuẩn của con người).

### 3.6. Cấu trúc mã nguồn
- `docker-compose.yml`, `.env.example`: định nghĩa và cấu hình toàn bộ dịch vụ.
- `src/database/init/`: script khởi tạo PostgreSQL (tài khoản, schema, `dw.dq_log`).
- `src/backend/`: FastAPI (lõi `app/core`, `routers/core_*`, module từng người `routers/tv2..tv5`). `src/frontend/`: React + Tailwind (Vite). `src/superset/`: image, cấu hình, đặc tả dataset/metric (`spec.py`) và `provision.py`.
- `src/etl_runner/`: dịch vụ chạy ETL theo yêu cầu. `src/n8n/`: workflow n8n (sinh từ `build_workflows.py`).
- `src/ingestion/`: thu thập vào `raw`. `src/dbt_dw/`: dbt (stg, dw, seed, OLAP, kiểm thử). `src/etl/`: kiểm tra chất lượng và xử lý tin. `src/ml/`: học máy (cảm xúc, phân cụm, dự báo).
- `tests/unit/`, `tests/smoke/`: kiểm thử.
- `tools/`: hook Git (`tools/hooks/commit-msg`) và script cài đặt (`tools/setup-git-hooks.sh`). `CLAUDE.md`, `.claude/skills/`: quy chuẩn cho agent (xem mục 4).

### 3.7. Gói dữ liệu seed: dev nhanh không cần thu thập lại
Thu thập từ đầu mất nhiều giờ, nên có hai gói `pg_dump` (nằm ở `data/seed/`, **không đưa vào git**, chia sẻ qua ổ đĩa nhóm). Chạy từ `src/`, khi hệ thống đang chạy:
```bash
python -m handover.seed export dev                        # chỉ schema dw (kho đã dựng + kết quả mô hình), dùng cho TV2-TV5
python -m handover.seed export full                       # raw + stg + dw, dùng để chạy lại dbt, ETL tin, mô hình từ dữ liệu thô
python -m handover.seed restore data/seed/dw_dev.dump     # phục hồi vào hệ thống đang chạy (mất schema tương ứng trước đó)
python -m ingestion.cli init-db                           # tạo bảng raw mới nếu mã mới hơn gói
python dbt_dw/run.py seed && python dbt_dw/run.py run     # nếu gói cũ hơn mã
```
Tài khoản website (schema `app`) không nằm trong gói: backend tự tạo tài khoản quản trị và tài khoản mẫu khi khởi động. Tệp mẫu cảm xúc cho TV5 (`data/samples/`) và bộ nhớ đệm embedding (`data/ml_cache/`) đi kèm gói; nếu thiếu, xuất lại bằng `python -m etl.news.samples` và `python -m ml.sentiment --embed-only` (khoảng 85 phút CPU).

### 3.8. Kiểm tra bàn giao và chạy lại từ đầu
```bash
python -m handover.check                                  # 10 hạng mục của gói bàn giao trên hệ thống đang chạy (từ src/)
```
Để thử **chạy lại từ đầu mà không xóa dữ liệu đang dùng**, dựng một dự án compose tách biệt (volume mới, cổng khác), phục hồi gói `full` rồi chạy chuỗi ETL, dbt, mô hình, kiểm thử trong đó. Lệnh, thời gian từng bước và kết quả đã chạy: `docs/kiem_thu_tu_dau.md`.

## 4. Quy chuẩn commit và cài hook Git

### 4.1. Cài hook (mỗi thành viên làm một lần sau khi clone)
Chạy trong Git Bash, tại thư mục gốc của kho:
```bash
sh nhom01-65httt/tools/setup-git-hooks.sh
git config core.hooksPath    # kết quả phải là: nhom01-65httt/tools/hooks
```
Git không tự chia sẻ hook qua clone, nên chưa chạy lệnh trên thì hook chưa có tác dụng. Hook chạy qua `sh` của Git for Windows, không cần cài thêm.

### 4.2. Cú pháp commit
```text
<loại>(nhom01-65httt): <mô tả ngắn gọn>
```
- `<loại>`: `feat` (chức năng hoặc mã nguồn mới), `fix` (sửa lỗi), `docs` (tài liệu), `chore` (việc phụ trợ, cấu hình).
- Mô tả bắt đầu bằng chữ thường, không có dấu chấm cuối. Phần thân (tùy chọn) cách một dòng trống, mỗi ý một gạch đầu dòng.
- Ví dụ: `feat(nhom01-65httt): add news ETL pipeline`.

### 4.3. Những điều hook từ chối
- Dòng tiêu đề sai cú pháp ở mục 4.2.
- Dòng `Co-Authored-By` của agent hoặc AI (Claude, Copilot, ChatGPT, Gemini...) và nhãn `Generated with ...`. Commit chỉ mang danh tính của sinh viên.

Không dùng `git commit --no-verify` để bỏ qua hook. Khi bị từ chối, sửa message rồi commit lại.

### 4.4. Khi dùng agent (Claude Code)
`CLAUDE.md` và skill `git-commit-rules` trong thư mục nhóm yêu cầu agent tuân thủ các quy chuẩn trên khi commit. Các quy chuẩn chung về nhánh, `git add <tennhom-tenlop>/` và Pull Request nằm trong `README.md` ở thư mục gốc của kho.

## 5. Làm việc nhóm: nhánh, Pull Request, ranh giới thư mục

Quy chuẩn chung về Fork, nhánh, `git add <tennhom-tenlop>/` và nộp bài nằm trong `README.md` ở thư mục gốc của kho (mục 2 và 5–6); commit theo mục 4 ở trên. Cách áp dụng trong dự án:

- **Nhánh.** `nhom01-65httt` là nhánh chung của nhóm (kho Fork của nhóm trưởng). Mỗi thành viên làm trên nhánh riêng tạo từ nhánh chung, đặt tên `<tên>-nhom01-65httt` (ví dụ `hoangvu-nhom01-65httt`); tính năng lớn tách thêm nhánh con. **Không commit thẳng vào `main`.**
- **Pull Request nội bộ.** Khi xong một phần: `git pull origin nhom01-65httt` để cập nhật, chạy `pytest`, `ruff check .` (và `dbt test` nếu đổi `dbt_dw/`), rồi mở PR từ nhánh cá nhân vào nhánh chung, mô tả ngắn việc đã làm và cách kiểm tra. Cần ít nhất một thành viên khác xem trước khi gộp. Chỉ nộp bài (PR từ Fork về `main` kho gốc) khi cả nhóm đã chốt.
- **Ranh giới thư mục** (tránh xung đột khi gộp): mỗi người chỉ thêm tệp vào thư mục của mình: `src/backend/app/routers/tvN/`, `src/frontend/src/pages/tvN/` và đúng **một dòng** vào `src/frontend/src/routes.jsx` và `src/backend/app/main.py`. Việc sửa phần lõi (`routers/core_*`, `app/core`, `dbt_dw`, `ml`, `ingestion`, `docker-compose.yml`) báo trước cho TV1. Đổi schema API, đặt tên dataset hoặc metric Superset chung: báo cả nhóm (`docs/api_contract.md`, `docs/superset_dataset_metric.md`).
- **Thêm chức năng:** endpoint mới (`docs/api_contract.md` mục 6), dashboard Superset mới (mục 4 cùng tệp), workflow n8n mới (`src/n8n/README.md`), số liệu nhập tay từ CSV (`src/ingestion/templates/README.md`), dữ liệu mẫu cảm xúc để gán nhãn (`docs/huong_dan_gan_nhan_cam_xuc.md`).
- **Không commit:** `.env` (chứa mật khẩu), `data/` (dữ liệu, gói seed, bộ nhớ đệm), `src/dbt_dw/target/`. Hook commit ở mục 4 chặn tiêu đề sai cú pháp và dòng co-author của AI.

## 6. Nguồn dữ liệu và giới hạn đã biết

Nguồn, độ tin cậy và quyết định về nguồn: `docs/bao_cao_nguon.md`, `docs/danh_gia_nguon_du_lieu.md`. Thiết kế kho: `docs/thiet_ke_kho.md`. Các giới hạn quan trọng (chi tiết ở `docs/ban_giao_GD1.md` mục 5 và `docs/ml_ket_qua.md` mục 7):
- Nguồn giá, khối ngoại, tự doanh (VNDirect) và tin (CafeF, RSS) là API/trang công khai không chính thức: có thể đổi hoặc chặn bất cứ lúc nào; tự doanh theo mã chỉ từ 17/05/2022.
- Nhãn cảm xúc do mô hình ngôn ngữ gán (chưa phải nhãn người); mô hình dự báo chiều dòng tiền ngành chưa vượt có ý nghĩa thống kê mô hình cơ sở "tuần sau giống tuần này"; khuyến nghị không tạo lợi suất vượt sau phí. Mọi kết quả kèm lưu ý đầu tư, không phải lời khuyên.
- Embedding và mô hình học máy chạy ngoài Docker; `POST /ml/sentiment` trong Docker trả dữ liệu mẫu (`stub`).
- Cấu hình nhúng Superset là cấu hình phát triển; chưa giới hạn số lần đăng nhập sai.
