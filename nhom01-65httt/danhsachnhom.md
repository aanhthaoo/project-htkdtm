# Danh Sách Nhóm Và Phân Công Nhiệm Vụ

## 1. Thông Tin Chung

- **Tên nhóm:** Nhóm 1
- **Tên lớp học phần:** 65HTTT
- **Tên đề tài:** Hệ thống phân tích dòng tiền và luân chuyển ngành trên thị trường chứng khoán Việt Nam, ứng dụng AI phân tích cảm xúc tin tức và dự báo dòng tiền
- **Giảng viên hướng dẫn:** TS. Đỗ Oanh Cường

---

## 2. Danh Sách Thành Viên

| STT | Họ và Tên | Mã Sinh Viên | Lớp Sinh Hoạt | Vai Trò | Nhiệm Vụ Phân Công | Tỷ Lệ Đóng Góp (%) | Email |
| :-: | :--- | :-: | :-: | :--- | :--- | :-: | :--- |
| 1 | Trương Thảo Anh | 2351160505 | 65HTTT | Nhóm trưởng (TV1) | Nền tảng, dữ liệu, kho, mô hình, tích hợp (đã bàn giao giai đoạn 1, hoàn thiện ở giai đoạn 3): hạ tầng Docker; toàn bộ thu thập dữ liệu và ETL; kho Star Schema (dbt) và toàn bộ SQL dataset Superset; backend và frontend khung, đăng nhập và phân quyền; n8n lõi; ba mô hình ML (cảm xúc, phân cụm, dự báo dòng tiền ngành), quy tắc khuyến nghị hằng tuần, backtest và API mô hình; bộ mẫu, tài liệu bàn giao, hỗ trợ và review PR của các thành viên; giai đoạn 3: huấn luyện lại mô hình bản cuối, chốt insight, tích hợp, demo | | |
| 2 | Phạm Hoàng Vũ | 2351160566 | 65HTTT | Thành viên (TV2) | Trang chi tiết mã, theo dõi và cảnh báo, quản trị, chatbot: trang chi tiết mã cổ phiếu (lịch sử giá, dòng tiền theo nhóm nhà đầu tư, tin liên quan, cụm hành vi); chatbot LLM + RAG trên kho tin với 10–15 truy vấn mẫu (LLM chỉ chọn truy vấn, không tự sinh SQL) và giao diện khung chat nhúng mọi trang; danh sách theo dõi và đăng ký cảnh báo (kể cả endpoint nội bộ cho n8n); trang quản trị (người dùng, nguồn thu thập, chạy lại ETL, nhật ký chất lượng, hiệu năng mô hình) | | |
| 3 | Phan Thị Sông Thương | 2351160557 | 65HTTT | Thành viên (TV3) | KPI, 6 dashboard Superset, trang Tổng quan và Phân tích ngành: định nghĩa KPI (`docs/dinh_nghia_kpi.md`); dựng 6 dashboard Superset (Tổng quan thị trường, Luân chuyển ngành, Nhà đầu tư, Dòng tiền và tâm lý, Vĩ mô và khối ngoại, Dự báo và khuyến nghị) và lưu vào kho mã; API KPI và top mã gom/xả, `GET /api/sectors/{icb_l2_code}`; thư viện biểu đồ và thành phần Thẻ KPI dùng chung; trang Tổng quan, trang Phân tích ngành; bộ lọc dùng chung và drill-down | | |
| 4 | Vũ Văn Quảng | 2351160543 | 65HTTT | Thành viên (TV4) | Nhập số liệu thủ công, trang Dự báo và khuyến nghị, trang Tài khoản, báo cáo: nhập CSV vĩ mô (CPI, SXCN, xuất nhập khẩu), nhà đầu tư cá nhân theo tuần, dòng vốn ETF bằng bộ nạp có sẵn (số liệu thật, có nguồn); API và trang Dự báo và khuyến nghị (dự báo ngành tuần tới, khuyến nghị, độ chính xác theo tuần so với mô hình cơ sở); trang Tài khoản (hồ sơ, đổi mật khẩu, đăng ký cảnh báo); tổng hợp báo cáo cuối kỳ | | |
| 5 | Nguyễn Văn Quang | 2351160542 | 65HTTT | Thành viên (TV5) | Sơ đồ, nhãn cảm xúc, n8n, trang Vĩ mô và Tin tức, kiểm thử, slide: sơ đồ (kiến trúc, Star Schema, luồng dữ liệu, luồng mô hình, luồng n8n); gán và kiểm tra nhãn cảm xúc của 390 bài (nhãn chuẩn của con người); API tin tức và vĩ mô (kể cả tương quan vĩ mô với khối ngoại), thành phần Tin nổi bật, trang Vĩ mô và Tin tức, chân trang lưu ý; workflow n8n (bản tin cuối tuần, cảnh báo đảo chiều dòng tiền và tin tiêu cực, báo lỗi ETL); kiểm thử toàn hệ thống (giao diện, danh sách lỗi); slide | | |


> Phân công khớp với `docs/Ke_hoach_thuc_hien_BTL_Nhom01.md` (mã TV1–TV5, hướng dẫn chi tiết từng người ở mục 3 của kế hoạch). Cột tỷ lệ đóng góp và email điền khi nộp bài.

---

## 3. Cấu Trúc Mã Nguồn Trong Thư Mục Nhóm

Mã nguồn của nhóm đặt trong thư mục này (mô tả chi tiết ở `README.md` mục 2 và 3.6):

```text
nhom01-65httt/
├── danhsachnhom.md        # Tệp thông tin nhóm này (kèm hướng dẫn cài đặt và chạy ở mục 4)
├── README.md              # Hướng dẫn kỹ thuật chi tiết (thu thập dữ liệu, dbt, mô hình, quy chuẩn commit...)
├── CLAUDE.md              # Quy chuẩn bắt buộc khi dùng agent (Claude Code) trong thư mục nhóm
├── docker-compose.yml     # Toàn bộ dịch vụ: PostgreSQL, backend, frontend, Superset, n8n, bộ chạy ETL
├── .env.example           # Mẫu cấu hình (sao chép thành .env, KHÔNG commit .env)
├── docs/                  # Kế hoạch, thiết kế kho, API contract, mô hình, bàn giao, báo cáo
├── src/
│   ├── backend/ frontend/ database/   # website (FastAPI, React) và khởi tạo cơ sở dữ liệu
│   ├── ingestion/ etl/ dbt_dw/        # thu thập, làm sạch, kho dữ liệu Star Schema
│   ├── ml/                            # mô hình cảm xúc, phân cụm, dự báo, khuyến nghị
│   ├── superset/ n8n/ etl_runner/     # dashboard, tự động hóa, bộ chạy ETL
│   └── handover/                      # kiểm tra bàn giao, gói dữ liệu seed
├── tests/                 # unit/ (không cần Docker) và smoke/ (cần hệ thống đang chạy)
├── tools/                 # Git hook và script cài hook
└── data/                  # Dữ liệu, gói seed, bộ nhớ đệm (KHÔNG đưa vào git)
```

---

## 4. Hướng Dẫn Cài Đặt Và Thực Thi Mã Nguồn

Hướng dẫn dành cho thành viên mới (sau khi nhóm trưởng đã giao quyền Collaborator của kho Fork). Làm lần lượt từ 4.2 đến 4.7; mất khoảng 30 đến 45 phút nếu có sẵn gói dữ liệu seed. Chi tiết kỹ thuật từng phần xem `README.md` và `docs/ban_giao_GD1.md`.

### 4.1. Môi trường yêu cầu

| Thành phần | Yêu cầu | Ghi chú |
|------------|---------|---------|
| Hệ điều hành | Windows 10/11 (Git Bash), Linux hoặc macOS | Lệnh trong tài liệu viết cho Git Bash/bash |
| Docker | Docker Desktop (Compose v2) | Cấp cho Docker **từ 8 GB RAM** và còn trống **khoảng 15 GB đĩa** (dữ liệu 4,8 GB, ảnh Docker, bản sao lưu) |
| Git | Git 2.x (Windows: Git for Windows, có Git Bash) | Cần để cài hook (4.3) |
| Python | 3.12 | Chỉ để chạy test, công cụ dữ liệu, mô hình trên máy; hệ thống chạy trong Docker không cần |
| Node.js | 22 | Chỉ cần để chạy test giao diện (`npm test`) hoặc chạy frontend ngoài Docker |
| PostgreSQL | 16 (chạy trong Docker) | **Không** cần cài trên máy |
| Tài khoản | GitHub | Gửi username cho nhóm trưởng để được mời |

Các cổng mặc định sẽ được dùng: 5432 (PostgreSQL), 8000 (backend), 5173 (web), 8088 (Superset), 5678 (n8n), 8100 (bộ chạy ETL). Cổng bị trùng thì đổi `*_PORT` trong `.env` (4.4).

### 4.2. Lấy mã nguồn và tạo nhánh làm việc

```bash
git config --global user.name  "Họ và Tên"                 # hiện trong lịch sử commit
git config --global user.email "email-da-dang-ky-github@..." # phải trùng email tài khoản GitHub
git clone https://github.com/<github-nhom-truong>/project-htkdtm.git
cd project-htkdtm
git checkout --track origin/nhom01-65httt                   # nhánh chung của nhóm
git checkout -b <tên>-nhom01-65httt                         # nhánh riêng, ví dụ hoangvu-nhom01-65httt (nếu đã có: git checkout --track origin/<tên>-nhom01-65httt)
```
Không commit thẳng vào `main`. Mọi lệnh bên dưới chạy trong thư mục `nhom01-65httt/` trừ khi ghi khác.

### 4.3. Bật Git hook kiểm tra commit (bắt buộc, làm một lần)

Hook `commit-msg` chặn commit sai quy chuẩn. Git **không** tự chia sẻ hook qua clone nên phải bật thủ công. Chạy trong Git Bash, tại **thư mục gốc của kho** (`project-htkdtm/`):
```bash
sh nhom01-65httt/tools/setup-git-hooks.sh
git config core.hooksPath          # kết quả phải là: nhom01-65httt/tools/hooks
```
Quy chuẩn commit (hook từ chối nếu sai):
```text
<loại>(nhom01-65httt): <mô tả ngắn gọn>
```
- `<loại>` là `feat` (chức năng mới), `fix` (sửa lỗi), `docs` (tài liệu) hoặc `chore` (việc phụ trợ, cấu hình); mô tả viết thường, không có dấu chấm cuối. Ví dụ: `feat(nhom01-65httt): add stock detail page`.
- **Không** có dòng `Co-Authored-By` của agent hoặc AI (Claude, Copilot, ChatGPT, Gemini...) và nhãn `Generated with ...`; commit chỉ mang danh tính của sinh viên.
- Chỉ đưa tệp trong thư mục nhóm vào commit: `git add nhom01-65httt/` (không dùng `git add .` hay `git add -A` ở thư mục gốc). Không dùng `git commit --no-verify`.

Thử hook (commit sai phải bị từ chối): `git commit --allow-empty -m "sai quy chuan"` → báo lỗi, không tạo commit.

### 4.5. Khởi động hệ thống

```bash
docker compose up -d --build        # lần đầu 5 đến 15 phút (dựng ảnh Docker)
docker compose ps                   # chờ cả 6 dịch vụ ở trạng thái healthy (Superset mất 1–2 phút)
```

| Dịch vụ | Địa chỉ | Ghi chú |
|---------|---------|---------|
| Website (React) | http://localhost:5173 | Đăng nhập bằng `APP_ADMIN_*` (quản trị) hoặc `APP_DEMO_*` (nhà đầu tư), hoặc tự đăng ký |
| Backend (FastAPI) | http://localhost:8000/docs | Tài liệu API tương tác; kiểm tra sống: `/health` |
| Superset | http://localhost:8088 | Tài khoản `SUPERSET_ADMIN_*` |
| n8n | http://localhost:5678 | Lần đầu mở sẽ yêu cầu tạo tài khoản chủ sở hữu (hoặc `python src/n8n/setup_owner.py`) |
| Bộ chạy ETL | http://localhost:8100/health | Chạy thu thập, dbt, kiểm tra chất lượng theo yêu cầu |
| PostgreSQL | localhost:5432 | Cơ sở `bi_dw`, các schema `raw`, `stg`, `dw`, `app` |

Lệnh thường dùng: `docker compose logs -f backend` (xem nhật ký), `docker compose restart backend`, `docker compose stop` (dừng, giữ dữ liệu), `docker compose up -d` (chạy lại). **Cẩn thận:** `docker compose down -v` xóa vĩnh viễn toàn bộ dữ liệu trong PostgreSQL; chỉ dùng khi chắc chắn đã có bản sao (gói seed) và đừng dùng nó để "thử lại cho sạch" (xem `docs/kiem_thu_tu_dau.md` để thử từ đầu mà không mất dữ liệu).

### 4.6. Nạp dữ liệu và dựng dashboard

Thu thập từ đầu mất nhiều giờ, nên thành viên dùng **gói dữ liệu seed** do nhóm trưởng chia sẻ (tệp `dw_dev.dump`, 187 MB; thư mục `data/` không nằm trong git).

```bash
# 1. Chuẩn bị Python (một lần), tại nhom01-65httt/
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash; Linux/macOS: source .venv/bin/activate
pip install -r src/backend/requirements-dev.txt -r src/ingestion/requirements.txt -r src/dbt_dw/requirements.txt

# 2. Đặt gói seed vào data/seed/ rồi phục hồi (khoảng 1 phút), từ thư mục src/
mkdir -p data/seed                      # sao chép dw_dev.dump vào đây
cd src
python -m handover.seed restore ../data/seed/dw_dev.dump
python -m ingestion.cli init-db         # tạo bảng raw mới nếu mã mới hơn gói

# 3. Dựng dataset, metric, dashboard Superset và bật nhúng (từ nhom01-65httt/)
cd ..
python src/superset/provision.py

# 4. Workflow n8n (từ nhom01-65httt/); bật workflow cần dùng, ví dụ etl-hourly
python src/n8n/build_workflows.py
docker exec htkdtm_nhom01-n8n-1 n8n import:workflow --separate --input=/workflows
docker exec htkdtm_nhom01-n8n-1 n8n update:workflow --id=etl-hourly --active=true
docker restart htkdtm_nhom01-n8n-1      # bắt buộc để kích hoạt có hiệu lực
```
Trên Git Bash (Windows), thêm `MSYS_NO_PATHCONV=1` đứng trước lệnh `docker exec` ở bước 4 (tránh Git Bash đổi đường dẫn `/workflows`). Muốn chạy mô hình học máy trên máy: `pip install -r src/ml/requirements.txt` (cần thêm torch, xem chú thích trong tệp). Muốn thu thập dữ liệu từ đầu thay cho gói seed: `README.md` mục 3.4 đến 3.5d.

### 4.7. Kiểm tra cài đặt thành công

```bash
python -m handover.check --only 1 2 4 5   # từ thư mục src/; 4 hạng mục đầu của gói bàn giao
pytest                                    # từ nhom01-65httt/: unit test, không cần Docker
pytest -m smoke                           # smoke test, cần hệ thống đang chạy
ruff check .                              # kiểm tra mã
cd src/frontend && npm ci && npm test     # test giao diện (cần Node 22)
```
Thành công khi: tất cả dịch vụ `healthy`; đăng nhập được ở http://localhost:5173; mở trang Luân chuyển ngành thấy dashboard Superset; `python -m handover.check --only 1 2 4 5` báo 4/4 đạt.

### 4.8. Làm việc hằng ngày

```bash
git checkout <tên>-nhom01-65httt
git pull origin nhom01-65httt              # lấy thay đổi mới của nhóm (rebase hoặc merge rồi giải quyết xung đột)
# ... sửa mã trong thư mục của mình (xem docs/Ke_hoach_thuc_hien_BTL_Nhom01.md mục 3) ...
ruff check . && pytest                     # trước khi commit
git status                                 # chỉ được có tệp trong nhom01-65httt/
git add nhom01-65httt/                     # chạy tại thư mục gốc của kho
git commit -m "feat(nhom01-65httt): add stock detail page"
git push origin <tên>-nhom01-65httt        # rồi mở Pull Request vào nhánh nhom01-65httt
```
Mỗi PR nhỏ (một việc), mô tả *làm gì, kiểm tra thế nào, ảnh hưởng ai*, và đáp ứng các ràng buộc ở `docs/ban_giao_GD1.md` mục 7. Quy chuẩn nhánh, Pull Request và nộp bài về kho gốc: `README.md` mục 4 và 5 và `README.md` ở thư mục gốc của kho.

### 4.9. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|-------------|---------------------------|
| `docker compose up` báo thiếu biến (`Chua co .env`) | Chưa tạo `.env`: `cp .env.example .env` (4.4) |
| Cổng đã được dùng (`port is already allocated`) | Đổi `*_PORT` trong `.env` rồi `docker compose up -d` |
| Dịch vụ không lên hoặc `unhealthy` | `docker compose logs <tên dịch vụ>`; Superset lần đầu cần 1–2 phút; kiểm tra Docker còn đủ RAM (từ 8 GB) |
| Commit không bị hook kiểm tra | Chưa bật hook: chạy lại 4.3, kiểm tra `git config core.hooksPath` |
| Hook từ chối commit | Sửa tiêu đề theo `loại(nhom01-65httt): mô tả`, bỏ dòng co-author; không dùng `--no-verify` |
| `ModuleNotFoundError` (psycopg, pandas...) | Chưa kích hoạt `.venv` hoặc chưa `pip install` (4.6) |
| Lỗi đường dẫn `/workflows` khi `docker exec` trên Git Bash | Thêm `MSYS_NO_PATHCONV=1` trước lệnh |
| Trang Luân chuyển ngành trống hoặc lỗi nhúng | Chưa chạy `python src/superset/provision.py`, hoặc backend/Superset chưa healthy |
| Smoke test bị bỏ qua (`deselected`) | Mặc định `pytest` bỏ nhóm smoke: dùng `pytest -m smoke` hoặc `pytest -m "smoke or not smoke"` |
| Phục hồi seed báo `errors ignored: 1` | Bình thường (câu `CREATE SCHEMA` vì schema đã có) |
| Cần chạy dbt | Dùng `python dbt_dw/run.py <lệnh>` từ `src/`; **không** chạy `dbt run --select dim_stock` thiếu dấu `+` (xóa view phụ thuộc), dùng `dim_stock+` |
| Mất dữ liệu sau `down -v` | Phục hồi từ gói seed (4.6) |

Cập nhật dữ liệu hằng ngày (nhóm trưởng làm sau 15h): `python -m ingestion.cli daily` → `python -m etl.news.pipeline` → `python dbt_dw/run.py run` (từ `src/`). Hỏi ai khi gặp vấn đề: mở Issue trên kho Fork với bốn mục *việc đang làm, điều đã thử, lệnh và kết quả, kỳ vọng*, hoặc nhắn nhóm trưởng.
