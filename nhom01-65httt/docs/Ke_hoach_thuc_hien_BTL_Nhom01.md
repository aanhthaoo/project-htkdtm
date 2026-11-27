# Kế hoạch thực hiện BTL – Nhóm 01 (65HTTT)

Đề tài: Hệ thống phân tích dòng tiền và luân chuyển ngành trên thị trường chứng khoán Việt Nam (BI + AI).
Căn cứ: `De_cuong_BTL__Nhom01.docx` (mục 16 – Kế hoạch, mục 17 – Phân công). Thời gian: 6 tuần.

**Ký hiệu thành viên**

| Mã | Họ tên | Vai trò |
|----|--------|---------|
| TV1 | Trương Thảo Anh | Nền tảng, dữ liệu, kho, ML, tích hợp (làm trước và làm nốt) |
| TV2 | Phạm Hoàng Vũ | Trang chi tiết mã, theo dõi/cảnh báo, quản trị, chatbot |
| TV3 | Phan Thị Sông Thương | KPI, 6 dashboard Superset, trang Tổng quan + Phân tích ngành |
| TV4 | Vũ Văn Quảng | Nhập CSV, trang Dự báo & khuyến nghị, trang Tài khoản, báo cáo |
| TV5 | Nguyễn Văn Quang | Sơ đồ, nhãn cảm xúc, n8n, trang Vĩ mô/Tin tức, kiểm thử, slide |

## 1. Tổng quan 3 giai đoạn

```
Tuần:   1      2      3     |  4      5     |  6
TV1:   [========GĐ1========]  (hỗ trợ/review) [====GĐ3====]
TV2:        (chuẩn bị)       [=====GĐ2======]  (báo cáo/QA)
TV3:        (chuẩn bị)       [=====GĐ2======]  (báo cáo/QA)
TV4:        (chuẩn bị)       [=====GĐ2======]  (báo cáo)
TV5:        (chuẩn bị)       [=====GĐ2======]  (slide/QA)
                            ^ Cổng G1             ^ Cổng G2
```

| Giai đoạn | Thời gian | Ai làm | Mục tiêu |
|-----------|-----------|--------|----------|
| GĐ1 – Nền tảng + mô hình | Tuần 1–3 (có thể tràn sang đầu Tuần 4 phần ML, xem mục 2) | **Chỉ TV1** | Dựng hạ tầng, dữ liệu, kho, khung hệ thống, **huấn luyện 3 mô hình ML, quy tắc khuyến nghị, backtest sơ bộ** và "gói bàn giao" để 4 người còn lại làm song song không phải chờ nhau |
| GĐ2 – Song song | Tuần 4–5 | **TV2, TV3, TV4, TV5 cùng lúc** (TV1 chỉ hỗ trợ, review PR, gỡ vướng; dùng thời gian rảnh để xử lý nốt ML nếu còn tràn) | Mỗi người hoàn thành module riêng, không dẫm chân nhau |
| GĐ3 – Hoàn thiện | Tuần 6 | **TV1** (4 người kia hỗ trợ báo cáo/QA) | Huấn luyện lại bản cuối với nhãn đã kiểm tra và dữ liệu vĩ mô đủ, chốt insight, tích hợp, demo |

Trong GĐ1, TV2–TV5 không bị chặn hoàn toàn: dùng thời gian này để đọc đề cương, cài môi trường (Docker, Node, Python), vẽ wireframe trang của mình, đọc tài liệu Superset/n8n/dbt. Việc này không tính vào deliverable nhưng giúp vào GĐ2 chạy ngay.

---

## 2. Giai đoạn 1 – Nền tảng và mô hình (Tuần 1–3, TV1)

> Kế hoạch chi tiết theo nhóm việc tuần tự, kèm kiểm thử và cổng kiểm tra, nằm ở `Ke_hoach_GD1_TV1.md`. Thứ tự việc trong file đó (dbt làm ngay sau dữ liệu có cấu trúc, tin tức sau) thay cho phân tuần ở dưới.

> **Trạng thái GĐ1 (cập nhật 27/11/2026): ĐÃ XONG, đạt cả 10 hạng mục bàn giao.** Kiểm tra bằng `python -m handover.check` (10/10 đạt trên hệ thống chính và trên hệ thống dựng lại từ đầu); chi tiết ở `ban_giao_GD1.md` và `kiem_thu_tu_dau.md`. Khác kế hoạch ban đầu, để mọi người không tìm nhầm:
>
> | Kế hoạch ghi | Thực tế đã làm |
> |---|---|
> | Fine-tune PhoBERT, cần GPU | Không dùng PhoBERT. Mô hình cảm xúc = TF-IDF + embedding `multilingual-e5-small` (chạy CPU), 69,6% trên nhãn do Claude gán. |
> | Tập mẫu 300–500 bài do LLM gán nhãn cho TV5 | 390 bài **chưa có nhãn nào** (`data/samples/sentiment_validation_sample.csv`), TV5 gán **mù** (không xem nhãn của mô hình) rồi đo bằng `python -m ml.sentiment_check`. Không còn cột nhãn LLM để "kiểm tra lại". |
> | Script nạp CSV | Có: `python -m ingestion.cli load-csv macro\|individual\|etf` (kiểm tra từng dòng, ghi `dq_log`). |
> | Khuyến nghị, backtest, API mô hình | Đã làm; `/api/recommendations`, `/ml/predict`, `/ml/cluster` dùng dữ liệu thật; `/ml/sentiment` trong Docker vẫn `stub`. |
> | Dữ liệu seed nhỏ | Gói dev 187 MB (chỉ schema `dw`) phục hồi trong 1 phút: `python -m handover.seed restore`. |
>
> **Còn là dữ liệu mẫu (`stub`) cần người làm thật:** `POST /api/chat` (TV2), `GET /api/sectors/{icb_l2_code}` (TV3), `GET /api/macro/correlation` (TV5). **Còn thiếu so với kế hoạch GĐ2 (phát hiện khi bàn giao, đã giao việc ở mục 3):** `GET /api/alerts/subscriptions` (TV2), đổi mật khẩu và sửa hồ sơ (TV4), hai view Superset cho dự báo/khuyến nghị và vĩ mô tháng (TV3), thư viện biểu đồ dùng chung cho frontend (TV3), lưu dashboard Superset vào kho mã (TV3).
>
> **Kết quả mô hình các bạn cần biết trước khi viết giao diện và báo cáo** (đọc `ml_ket_qua.md`): dự báo chiều dòng tiền ngành 63,4% so với cơ sở 62,6% (chưa vượt có ý nghĩa thống kê); khuyến nghị khớp chiều dòng tiền khối ngoại tuần sau nhưng không tạo lợi suất vượt mua đều sau phí; cảm xúc yếu và chỉ có ý nghĩa cùng phiên. **Mọi trang hiển thị dự báo, khuyến nghị hay cảm xúc phải nói đúng như vậy** (mục 3.0, ràng buộc R7).

Nguyên tắc:
- Làm theo thứ tự "cái gì chặn người khác thì làm trước": hạ tầng, kho, khung web, API contract (hạng mục 1–5 của gói bàn giao) **ưu tiên cao hơn ML**.
- Gom càng nhiều việc của TV1 vào giai đoạn này càng tốt, kể cả ML, khuyến nghị, backtest, để Tuần 6 chỉ còn chốt và tích hợp.
- Chốt **hợp đồng giao tiếp (API contract)** sớm để người khác code song song.
- Phần ML nào không phụ thuộc kho `dw` (cảm xúc) chạy sớm và chạy nền trong lúc làm dbt; phần phụ thuộc `dw` (dự báo, phân cụm) bắt đầu ngay khi bảng Fact đầu tiên có dữ liệu.

### Tuần 1 – Hạ tầng và kiểm chứng nguồn
- Kiểm tra API CafeF (giá, khối ngoại, tự doanh), API Vietcap, tải EconVNNews; ghi lại nguồn nào dùng được.
- Dựng Docker Compose: PostgreSQL (schema `raw`, `dw`, `app`), Superset, n8n, backend FastAPI, frontend React.
- Chốt Star Schema (Fact/Dim theo mục 8 đề cương) và sơ đồ kiến trúc bản nháp.
- Tạo cấu trúc thư mục repo và quy ước nhánh/PR cho nhóm.

### Tuần 2 – Thu thập dữ liệu, ETL thô, bắt đầu cảm xúc
- Nạp backfill EconVNNews vào `raw`.
- Viết script: API CafeF (giá, khối ngoại, tự doanh), danh sách mã/ngành Vietcap, yfinance, RSS VnEconomy/Vietstock/VnExpress, crawl CafeF + Tin nhanh Chứng khoán.
- Script nạp CSV (vĩ mô, nhà đầu tư cá nhân, ETF) kèm **file CSV mẫu** để TV4 dùng.
- ETL: làm sạch, chuẩn hóa, loại trùng; **ưu tiên nạp xong dữ liệu giá + khối ngoại + tự doanh dạng API (JSON, nhanh) để dbt và ML dự báo có dữ liệu sớm**.
- Cảm xúc (không cần chờ `dw`): lọc bài chứng khoán, nhận diện mã/ngành, tách từ; dùng LLM gán nhãn sơ bộ một tập mẫu lớn (vài nghìn bài) để huấn luyện, trích riêng 300–500 bài cho TV5.

### Tuần 3 – Kho dữ liệu, khung ứng dụng, mô hình ML, bộ bàn giao
Thứ tự đề xuất (cái chặn người khác làm trước, ML làm sau hoặc chạy nền):
1. dbt: các bảng Dim/Fact, kiểm thử `dbt test`, đối chiếu chéo, bảng nhật ký chất lượng. Làm `Fact_Money_Flow`, `Fact_Daily_Price` trước vì ML cần.
2. OLAP: ROLLUP/CUBE/GROUPING SETS, materialized view (dòng tiền ngành × tuần × nhóm NĐT, KPI phiên gần nhất).
3. Superset: kết nối `dw`, dataset SQL + metric dùng chung.
4. Backend/frontend khung: đăng nhập, phân quyền 3 vai trò, layout, router, nhúng iframe Superset; n8n lõi (thu thập theo giờ + ETL sau 15h, webhook gọi lại ETL).
5. **Mô hình cảm xúc** (chạy nền từ cuối Tuần 2): baseline TF-IDF + Logistic Regression, fine-tune PhoBERT trên nhãn LLM; ghi `Fact_News_Sentiment`. Nếu máy không có GPU, huấn luyện trên Colab/Kaggle.
6. **Mô hình dự báo dòng tiền ngành** (ngay khi có `Fact_Money_Flow` + `Fact_Daily_Price` + yfinance): XGBoost/LightGBM, walk-forward, so baseline "tuần sau giống tuần này"; thử có/không đặc trưng cảm xúc; ghi `Fact_Prediction`. Chưa có CPI/ETF (TV4 nhập ở GĐ2) nên bản này thiếu hai nhóm đặc trưng đó, sẽ huấn luyện lại ở GĐ3.
7. **Phân cụm K-Means** trên đặc trưng dòng tiền, Silhouette, đặt tên cụm; ghi `Dim_Stock`.
8. **Quy tắc khuyến nghị hằng tuần** + **backtest sơ bộ** so với VN-Index; bản nháp insight.
9. **API mô hình** (FastAPI: `/predict`, `/sentiment`, `/cluster`) chạy mô hình thật. Nếu mô hình nào chưa xong khi đến cổng G1, endpoint đó trả dữ liệu mẫu đúng schema (stub) để không chặn người khác, rồi thay bằng bản thật mà không đổi schema.

Rủi ro thời gian: mục 5–8 phụ thuộc `dw` nên dồn vào cuối Tuần 3. Quy tắc cắt: **hạng mục 1–5 của gói bàn giao (mục dưới) phải xong đúng hạn, ML được phép tràn sang đầu Tuần 4** (TV1 làm tiếp trong lúc 4 người kia đã bắt đầu GĐ2 trên stub). Phần ML nên làm sớm nhất: cảm xúc (không phụ thuộc `dw`).

### Gói bàn giao GĐ1 (cổng G1 – cuối Tuần 3)

TV1 chỉ coi GĐ1 xong khi **tất cả** mục dưới đây đã có trên nhánh chung:

| # | Hạng mục | Ai dùng |
|---|----------|---------|
| 1 | `docker compose up` chạy được toàn bộ dịch vụ, README hướng dẫn cài | Cả 4 |
| 2 | Kho `dw` có dữ liệu thật (ít nhất vài tháng đầy đủ, ưu tiên toàn kỳ) + dữ liệu seed nhỏ để dev nhanh | Cả 4 |
| 3 | Dataset + metric Superset đã định nghĩa | TV3 |
| 4 | Khung backend/frontend: auth, phân quyền, layout, thư viện component dùng chung, cách nhúng Superset | TV2, TV3, TV4, TV5 |
| 5 | Tài liệu API contract (endpoint, request/response mẫu) cho: KPI, top gom/xả, stock detail, tin tức, vĩ mô, dự báo, watchlist | Cả 4 |
| 6 | API ML chạy mô hình thật (hoặc stub đúng schema cho endpoint chưa xong) + `Fact_Prediction`, `Fact_News_Sentiment`, nhãn cụm đã ghi vào `dw` | TV4, TV2 (chatbot giải thích dự báo), TV3 |
| 7 | Tập mẫu cảm xúc 300–500 bài do LLM gán nhãn | TV5 |
| 8 | Bộ mẫu (template): trang React, API router, workflow n8n, file CSV | Cả 4 |
| 9 | Endpoint kích hoạt/chạy lại ETL + bảng nhật ký chất lượng | TV2 (trang quản trị), TV5 (cảnh báo lỗi ETL) |
| 10 | Hướng dẫn làm việc: nhánh theo tên, PR về nhánh chung, quy ước đặt tên | Cả 4 |

Cuối Tuần 3: TV1 họp 30–45 phút giao việc cho 4 người, demo `docker compose up` + gói bàn giao.

---

## 3. Giai đoạn 2 – Song song (Tuần 4–5, TV2–TV5)

Nguyên tắc chống xung đột: **mỗi người sở hữu thư mục riêng** (backend router, frontend page, thư mục dashboard/workflow), chỉ sửa file chung (layout, router gốc, component dùng chung) qua PR và báo trước. Dùng dữ liệu thật trong `dw` và API stub của TV1.

Chia hai nhịp: **Tuần 4 = làm phần cốt lõi**, **Tuần 5 = hoàn thiện + nối với module người khác**. Cuối Tuần 4 họp 15 phút đồng bộ.

### 3.0. Quy trình chung và ràng buộc cho cả bốn người (đọc trước khi bắt đầu)

**Nhịp làm việc.**
- Ngày 1 Tuần 4: mỗi người dựng môi trường theo `ban_giao_GD1.md` mục 1 (khoảng 30 phút), chạy `python -m handover.check --only 1 2 4 5`, tạo nhánh cá nhân từ `nhom01-65httt`, mở PR nháp (rỗng) để mọi người thấy ai đang làm gì.
- Mỗi PR nhỏ (một việc, dưới khoảng 400 dòng thay đổi) và gộp vào `nhom01-65httt` **ít nhất mỗi hai ngày**; không để nhánh sống quá 3 ngày mà không đồng bộ (`git pull origin nhom01-65httt` rồi rebase/merge mỗi sáng).
- Họp đứng 10 phút mỗi sáng (hoặc nhắn tin): hôm qua xong gì, hôm nay làm gì, đang bị chặn bởi ai. Cuối Tuần 4 họp 15 phút đồng bộ (mục "Điểm nối").
- Gặp vấn đề của TV1 (dữ liệu sai/thiếu, mô hình, hạ tầng, Superset hỏng): mở một Issue trên kho Fork với mẫu: *việc đang làm / điều đã thử / lệnh và kết quả / kỳ vọng*; TV1 phản hồi trong 1 ngày làm việc. Không tự sửa `dbt_dw/models/marts`, `src/ml`, `src/ingestion`, `docker-compose.yml`.

**Mỗi PR phải có (Definition of Done chung):** (1) `ruff check .` sạch và `pytest` (unit) qua; (2) với backend: test trong `tests/smoke/test_api.py` cho từng endpoint mới (đủ ba trường hợp: không đăng nhập, sai vai trò, đúng vai trò) và đã chạy `python src/backend/export_openapi.py` để `docs/openapi.json` khớp; (3) với frontend: `cd src/frontend && npm test` qua và trang hiển thị đúng trên hệ thống chạy thật (kèm ảnh chụp màn hình trong PR); (4) đổi `dbt_dw`: `dbt test` qua; (5) mô tả PR ghi *làm gì, kiểm tra thế nào, ảnh hưởng người khác ra sao*; (6) commit theo `loại(nhom01-65httt): mô tả`, **không** có co-author AI (hook chặn).

**Ràng buộc bắt buộc.** Đầy đủ kèm lý do ở `ban_giao_GD1.md` mục 7; bản tóm tắt để tra nhanh:

| Mã | Ràng buộc |
|----|-----------|
| R1 | Chỉ sửa trong thư mục của mình (`routers/tvN/`, `pages/tvN/`); file dùng chung (`routes.jsx`, `main.py`, `Layout.jsx`, `components/`, `package.json`) chỉ thêm dòng/qua PR có TV1 và người liên quan xem trước |
| R2 | API contract đã chốt: **không đổi** tên trường, kiểu, mã lỗi đã có; chỉ được **thêm** trường tùy chọn hoặc endpoint mới, sau khi báo cả nhóm và cập nhật `docs/api_contract.md` + `docs/openapi.json` |
| R3 | Backend chỉ **đọc** `dw`, chỉ **ghi** `app`; câu lệnh SQL dùng tham số (`text(...)` + dict), không ghép chuỗi; không gọi trực tiếp `raw`/`stg` (tài khoản `bi_app` không có quyền) |
| R4 | Không chạy `docker compose down -v`, `dbt run --select dim_stock` (thiếu dấu `+`), hay xóa/ghi đè `dw.dim_model`, `fact_prediction`, `fact_news_sentiment`, `fact_recommendation`, `stock_cluster`; thử nghiệm phá hủy làm trong dự án compose riêng (`-p tên-riêng`) |
| R5 | Không commit `.env`, mật khẩu, khóa API, dữ liệu trong `data/`, gói seed; khóa LLM/SMTP đặt trong `.env` hoặc credential của n8n |
| R6 | Không dùng dữ liệu tương lai: số liệu vĩ mô nhập tay phải có `published_date` thật; mọi tính toán thống kê/ML chỉ dùng thông tin có tại thời điểm đó |
| R7 | Trình bày kết quả mô hình trung thực: dự báo/khuyến nghị luôn kèm `Disclaimer` và **mô hình cơ sở bên cạnh**; không viết "nên mua/nên bán", không nói "độ chính xác cao"; dùng đúng thuật ngữ API (`tăng/giảm tỷ trọng`) |
| R8 | Phân quyền theo hợp đồng (khách < nhà đầu tư < quản trị); khách chỉ xem tổng quan, tối đa 5 tin, dashboard `overview`; mọi kiểm tra quyền làm **ở backend**, không chỉ ẩn nút ở giao diện |
| R9 | Đơn vị và quy ước: tiền **tỷ đồng** (`_bn`), giá **đồng** (`_vnd`), ngày `YYYY-MM-DD`, múi giờ Việt Nam, tuần bắt đầu **thứ Hai**; không tự đổi đơn vị trong giao diện mà không ghi rõ |
| R10 | Không sửa mô hình (`src/ml`) và không gọi thư viện học máy từ backend; cần thêm đặc trưng/kết quả mới thì nhờ TV1 |
| R11 | Không đưa toàn văn bài báo ra API/giao diện (chỉ tiêu đề, nguồn, đường dẫn gốc, tóm tắt ngắn); tôn trọng bản quyền nguồn |
| R12 | Thêm thư viện (npm, pip) phải báo trước vì làm đổi `package-lock.json`/image; không thêm thư viện nặng vào image backend |

**Quy ước dùng chung** (tránh mỗi người một kiểu): thư viện biểu đồ frontend **dùng một thư viện duy nhất** (đề xuất `recharts`) do TV3 thêm trong ngày 1 Tuần 4 kèm hai wrapper `TimeSeriesChart`, `BarChart` ở `src/frontend/src/components/charts/`; ba người còn lại **chờ PR này** (trong lúc chờ dùng `DataTable`), không tự thêm thư viện biểu đồ khác. Định dạng số (`1.234,5`), nhãn trạng thái, màu cho "vào/ra", thẻ KPI: dùng `KpiCard`, `Disclaimer`, `Alert`, `Spinner` có sẵn; muốn thêm component dùng chung thì thêm vào `components/` và báo TV3 (người giữ bộ component).

### TV2 – Phạm Hoàng Vũ
| Tuần | Công việc | Phụ thuộc |
|------|-----------|-----------|
| 4 | Trang chi tiết mã cổ phiếu (lịch sử giá, dòng tiền theo nhóm NĐT, tin liên quan, cụm hành vi) + API | `dw`, khung web |
| 4 | Chatbot: 10–15 truy vấn mẫu trên `dw`; LLM chỉ chọn truy vấn và điền tham số, không tự sinh SQL; RAG trên kho tin | `dw`, bảng tin tức |
| 5 | Giao diện khung chat nhúng mọi trang, kèm nguồn và câu lưu ý không phải khuyến nghị đầu tư | Chatbot backend |
| 5 | Danh sách theo dõi + đăng ký cảnh báo (lưu trong schema `app`); gọi workflow cảnh báo của TV5 | Workflow n8n của TV5 (thống nhất payload sớm trong Tuần 4) |
| 5 | Trang quản trị: người dùng, nguồn thu thập, chạy lại ETL, nhật ký chất lượng, hiệu năng mô hình | Endpoint ETL và nhật ký của TV1 |


**Hướng dẫn chi tiết cho TV2** (nhánh `hoangvu-nhom01-65httt`; thư mục của bạn: `src/backend/app/routers/tv2/`, `src/frontend/src/pages/tv2/`)

*Đã có sẵn:* API mã cổ phiếu thật (`GET /api/stocks`, `/{symbol}`, `/{symbol}/prices`, `/{symbol}/flow`, `/api/stocks/top-net`); danh sách theo dõi và đăng ký cảnh báo thật (`/api/watchlist`, `POST/DELETE /api/alerts/subscriptions`, loại cảnh báo `flow_reversal`, `negative_news`, `weekly_digest`, đối tượng `STOCK` hoặc `SECTOR`); quản trị thật (`/api/admin/users`, `/sources`, `/models`, `/etl/run`, `/etl/runs`, `/dq-log`); trang mẫu `StocksPage.jsx` và `Admin.jsx`; `POST /api/chat` là **stub** (schema đã chốt: `{message}` → `{answer, sources[], disclaimer, stub}`).

| # | Việc | Làm ở đâu | Xong khi | Ngày |
|---|------|-----------|----------|------|
| 2.1 | Trang chi tiết mã `/stocks/:symbol` (thêm một dòng vào `routes.jsx`) | `pages/tv2/StockDetailPage.jsx` | Hiển thị: tên, sàn, ngành ICB cấp 2 và 4, nhóm vốn hóa, VN30, **nhãn cụm kèm giải thích tiếng Việt**, giá 30/90/250 phiên, dòng tiền theo nhóm nhà đầu tư (ngày và tuần), 10 tin liên quan kèm cảm xúc (`/api/news?symbol=`), nút thêm vào theo dõi. Thử với VNM, FPT, VCB, HPG và một mã nhóm `phu_`; mã không có thì hiện trang 404 thân thiện | T4 N1–3 |
| 2.2 | Bảng giải thích cụm | `pages/tv2/clusterLabels.js` | Ánh xạ nhãn → mô tả: `ngoai_giao_dich_deu+thanh_khoan_cao` (khối ngoại giao dịch đều, thanh khoản cao), `ngoai_giao_dich_thua+dong_tien_on_dinh`, `dong_tien_bat_on+ngoai_mua_deu`, `tu_doanh_chu_dao+thanh_khoan_cao`, ba nhãn `phu_...` (xem `ml_ket_qua.md` mục 1) và `chua_du_du_lieu`. Nhãn lạ (khi TV1 huấn luyện lại) hiện nguyên văn, không báo lỗi | T4 N2 |
| 2.3 | Chatbot backend | `routers/tv2/chat.py` (tách khỏi `stocks_watch.py`) | Xem hướng dẫn chatbot bên dưới; 12–15 truy vấn mẫu, mỗi truy vấn có test so với SQL gốc | T4 N3–5 |
| 2.4 | Khung chat nhúng mọi trang | `components/ChatWidget.jsx` + một dòng trong `Layout.jsx` (PR có TV1 và TV3 xem) | Nút nổi, mở/đóng, lịch sử trong phiên, hiện nguồn và câu lưu ý; chưa đăng nhập thì ẩn | T5 N1–2 |
| 2.5 | Cảnh báo và theo dõi | `routers/tv2/` + `pages/tv2/WatchlistPanel.jsx` | (a) **thêm `GET /api/alerts/subscriptions`** (hiện thiếu, TV4 cần cho trang Tài khoản); (b) `WatchlistPanel` dùng được ở trang Tài khoản của TV4 (TV4 nhúng, không viết lại); (c) hai endpoint nội bộ cho n8n (xem "Điểm nối TV2 ↔ TV5") | T5 N2–4 |
| 2.6 | Trang quản trị hoàn chỉnh | `pages/Admin.jsx` (bạn sở hữu file này) | Người dùng (đổi vai trò, khóa, **không tự hạ quyền/khóa mình**), nguồn thu thập (bật/tắt), chạy lại ETL (xác nhận trước khi chạy job `news`, hiện trạng thái đang chạy, 409 khi bận), nhật ký `etl_runs`, `dq_log` có bộ lọc, **bảng hiệu năng mô hình** từ `/api/admin/models` (accuracy mô hình và cơ sở cạnh nhau) | T5 N3–5 |

**Chatbot: cách làm và giới hạn.**
- LLM **chỉ chọn một truy vấn trong danh sách và điền tham số** (dạng gọi hàm, trả JSON); **không** sinh SQL. Mỗi truy vấn là một hàm Python có tham số kiểm tra (mã cổ phiếu có trong `dw.dim_stock`, số phiên trong khoảng cho phép...), SQL cố định đọc `dw`, và hàm định dạng câu trả lời kèm **nguồn** (tên bảng/dataset và ngày dữ liệu).
- Gợi ý 12–15 truy vấn: giá và thay đổi của mã; khối ngoại mua/bán ròng của mã trong N phiên; top mã khối ngoại mua/bán ròng tuần; dòng tiền ngành tuần gần nhất; dự báo ngành tuần tới (`/api/predictions`); khuyến nghị và lý do tín hiệu của một ngành; tin mới về một mã; cảm xúc tin của ngành; nhãn cụm của mã; so sánh dòng tiền hai mã; VN-Index và khối ngoại phiên gần nhất; độ chính xác dự báo so với cơ sở; giải thích thuật ngữ (từ điển tĩnh); USD/VND.
- **Phải chạy được khi không có khóa LLM**: bộ định tuyến dự phòng bằng từ khóa và biểu thức chính quy (để test, demo, và khi hết hạn mức). Khóa LLM đọc từ biến môi trường (`CHAT_LLM_API_KEY`... thêm vào `.env.example` không kèm giá trị), giới hạn độ dài trả lời và số lượt hỏi mỗi người dùng mỗi phút.
- Câu hỏi ngoài phạm vi (hỏi "mua mã nào", dự đoán giá, chuyện không liên quan) → từ chối lịch sự và nhắc đây không phải khuyến nghị đầu tư; mọi câu trả lời có `disclaimer`.
- Nội dung bài báo/văn bản người dùng nhập là **dữ liệu không tin cậy**: không làm theo chỉ dẫn nằm trong đó (chống prompt injection).
- "RAG trên kho tin": phiên bản đầu dùng **tiêu đề, nguồn, ngày, cảm xúc** của `dw.dim_article` và `fact_news_sentiment` (đọc được bằng `bi_app`). Toàn văn nằm ở `stg.news_article`, tài khoản `bi_app` **không** có quyền; nếu cần đoạn trích để trả lời, mở Issue cho TV1 thêm view `dw` (đừng cấp quyền tự ý).
- Ghi nhật ký hỏi đáp (câu hỏi, truy vấn được chọn, thời gian) vào bảng mới trong schema `app` qua migration `src/backend/app/migrations/002_*.sql` để đánh giá chất lượng.

**Ràng buộc riêng.** Quản trị: mọi endpoint `/api/admin/*` kiểm tra quyền admin ở backend; thao tác không đảo ngược (khóa tài khoản, chạy `news`) phải hỏi xác nhận trong giao diện. Danh sách theo dõi và đăng ký cảnh báo chỉ của chính người dùng (không đọc được của người khác; có test). Email người dùng không xuất hiện trong nhật ký hay câu trả lời chat. Mã cổ phiếu từ người dùng phải được kiểm tra với `dw.dim_stock` trước khi dùng (không đưa thẳng vào SQL).

**Kiểm thử bắt buộc.** Mỗi truy vấn chatbot một test so với SQL gốc; test bộ định tuyến dự phòng (câu hỏi mẫu → đúng truy vấn); test từ chối câu ngoài phạm vi; test cách ly dữ liệu giữa hai người dùng (watchlist, cảnh báo); test không tự hạ quyền; test vitest cho khóa quyền trang quản trị; kiểm thử thủ công mục 5 của `kiem_thu_tu_dau.md` cho trang của bạn.

**Cung cấp cho người khác / cần từ người khác.** Cần: khung và component của TV1 (có sẵn), thư viện biểu đồ của TV3 (ngày 1 Tuần 4), payload cảnh báo thống nhất với TV5 (ngày 1–2 Tuần 4, xem "Điểm nối"). Cung cấp: `GET /api/alerts/subscriptions` và `WatchlistPanel` cho TV4; endpoint nội bộ cho TV5.

**Nộp (DoD của TV2):** 2.1–2.6 đã gộp vào nhánh chung; `docs/api_contract.md` cập nhật endpoint mới; mục "Chatbot" trong báo cáo (TV4 ghép) gồm danh sách truy vấn, sơ đồ luồng, cách chống sinh SQL tùy ý, ví dụ hỏi đáp; kết quả kiểm thử thủ công.
### TV3 – Phan Thị Sông Thương
| Tuần | Công việc | Phụ thuộc |
|------|-----------|-----------|
| 4 | Chốt định nghĩa KPI, ghi vào tài liệu; dựng 4 dashboard dùng dữ liệu thật: Tổng quan thị trường, Luân chuyển ngành, Nhà đầu tư, Dòng tiền và tâm lý | Dataset/metric Superset |
| 4 | API KPI + top mã gom/xả | Materialized view |
| 5 | 2 dashboard còn lại: Vĩ mô và khối ngoại, Dự báo và khuyến nghị (dùng `Fact_Prediction` thật của TV1); bộ lọc dùng chung, drill-down | Dữ liệu vĩ mô (TV4 nhập CSV), `Fact_Prediction` |
| 5 | Thành phần Thẻ KPI, trang Tổng quan, trang Phân tích ngành (nhúng dashboard) | Component dùng chung |


**Hướng dẫn chi tiết cho TV3** (thư mục của bạn: `src/superset/`, `src/backend/app/routers/tv3/`, `src/frontend/src/pages/tv3/`, `src/frontend/src/components/`, và thư mục `src/dbt_dw/models/superset/`)

*Đã có sẵn:* 10 dataset Superset (`ds_flow_daily`, `ds_sector_flow_weekly`, `ds_market_flow_series`, `ds_stock_flow_daily`, `ds_stock_daily`, `ds_macro_daily`, `ds_news_article`, `ds_news_stock_daily`, `ds_news_sentiment`, `ds_prediction`) cùng metric dùng chung và 2 dashboard mẫu nhúng được (`tong-quan-demo` cho khách, `luan-chuyen-nganh-demo` cho nhà đầu tư); danh sách và công thức: `docs/superset_dataset_metric.md`, định nghĩa gốc `src/superset/spec.py`; API KPI thật (`/api/market/overview`, `/api/sectors/flow`, `/api/stocks/top-net`); `GET /api/sectors/{icb_l2_code}` là **stub** (schema đã chốt: `net_bn_by_week[]`, `sentiment_label`, `top_stocks[]`); trang mẫu `SectorsPage.jsx`, `Home.jsx`; component `KpiCard`, `DataTable`, `SupersetEmbed`.

| # | Việc | Làm ở đâu | Xong khi | Ngày |
|---|------|-----------|----------|------|
| 3.1 | **Thư viện biểu đồ chung** (làm đầu tiên, vì cả nhóm chờ) | `package.json` + `components/charts/` | PR riêng thêm `recharts` (hoặc thư viện bạn chọn, báo nhóm), hai wrapper `TimeSeriesChart`, `BarChart` có trạng thái tải/lỗi/rỗng, định dạng số kiểu Việt, một test vitest; gộp trong ngày 1 | T4 N1 |
| 3.2 | **Định nghĩa KPI** | `docs/dinh_nghia_kpi.md` (mới) | Ít nhất 10 KPI, mỗi KPI một dòng: tên, công thức, đơn vị, dataset và metric/SQL nguồn, hạn chế khi đọc (ví dụ nhóm "trong nước khác" là phần dẫn xuất, gồm tự doanh trước 17/05/2022). Mọi KPI truy được về `spec.py` hoặc SQL trên `dw` | T4 N1–2 |
| 3.3 | **4 dashboard Tuần 4** | Superset + `spec.py` + `core_superset.py` | Xem bảng dashboard bên dưới. Mỗi dashboard đã đăng ký (khóa, slug, vai trò tối thiểu), nhúng được, đúng phân quyền, tải dưới 5 giây | T4 N2–5 |
| 3.4 | **Lưu dashboard vào kho mã** | `src/superset/dashboards/*.zip` + mục trong `src/superset/README.md` | Dashboard dựng bằng giao diện Superset chỉ nằm trong volume Superset và **mất khi `down -v`**; phải xuất vào kho: `docker exec htkdtm_nhom01-superset-1 superset export-dashboards -f /tmp/d.zip` rồi `docker cp`; nạp lại: `superset import-dashboards -p /tmp/d.zip -u admin`. Thứ tự đề xuất: `provision.py` (kết nối, dataset) → import zip → `provision.py` lần nữa (bật nhúng, đặt slug). Lệnh đã có trong Superset 5.0 nhưng **chưa thử đầu cuối**: ngày đầu làm chung với TV1 và chứng minh trên dự án compose riêng (`-p`) rằng dựng từ đầu vẫn có đủ dashboard | T4 N2 và cuối mỗi tuần |
| 3.5 | `GET /api/sectors/{icb_l2_code}` thật | `routers/tv3/market_sectors.py` | Giữ nguyên schema; `net_bn_by_week` (tối thiểu 26 tuần, theo nhóm khối ngoại), `sentiment_label` (từ cảm xúc ngành tuần gần nhất), `top_stocks` (mã vào/ra nhiều nhất); `stub` thành `false`; test so với SQL gốc; mã ngành lạ trả 404 | T4 N4–5 |
| 3.6 | **2 dashboard Tuần 5** | view dbt mới + Superset | (a) *Vĩ mô và khối ngoại*: cần dataset tháng, **tạo view `ds_macro_monthly`** (đọc `dw.fact_macro_indicator` với `source = 'manual_csv'`, kèm `published_date`) + `ds_individual_weekly`, `ds_etf_monthly`; (b) *Dự báo và khuyến nghị*: **tạo view `ds_recommendation`** (tuần, ngành, hành động, độ chắc chắn, điểm, tín hiệu, xác suất) cạnh `ds_prediction` có sẵn. File view đặt ở `src/dbt_dw/models/superset/`, khai báo test trong `models/staging/staging.yml` hoặc tệp yml cạnh, thêm vào `spec.py`, `docs/superset_dataset_metric.md`; chạy `dbt run --select superset` và `dbt test` | T5 N1–3 |
| 3.7 | Bộ lọc dùng chung và drill-down | Superset | Bộ lọc thời gian, sàn, ngành, nhóm nhà đầu tư, nhóm vốn hóa dùng chung (xem mục "Bộ lọc dùng chung" của tài liệu dataset); từ biểu đồ ngành/mã có liên kết sang `/sectors` hoặc `/stocks/<mã>` | T5 N2–4 |
| 3.8 | Trang Tổng quan và Phân tích ngành | `Home.jsx` (bạn sở hữu phần nội dung), `pages/tv3/SectorsPage.jsx` | Tổng quan (khách xem được): thẻ KPI từ `/api/market/overview` + dashboard `overview` + 5 tin nổi bật (component của TV5); Phân tích ngành: chọn ngành, hiện `/api/sectors/{code}` và nhúng dashboard luân chuyển ngành | T5 N3–5 |

**6 dashboard (bản đề xuất, nhóm chốt cuối Tuần 4).**

| Dashboard | Khóa → slug | Vai trò | Nội dung gợi ý | Dataset |
|-----------|-------------|---------|----------------|---------|
| 1. Tổng quan thị trường | `overview` | khách | Thẻ KPI (khối ngoại ròng phiên gần nhất, giá trị giao dịch, VN-Index), chuỗi mua/bán ròng theo nhóm nhà đầu tư, top ngành vào/ra | `ds_market_flow_series`, `ds_sector_flow_weekly` |
| 2. Luân chuyển ngành | `sector-rotation` | nhà đầu tư | Heatmap ngành × tuần (mua/bán ròng, tỷ lệ ròng/giao dịch), xu hướng 4/12 tuần, tỷ trọng dòng tiền ngành | `ds_sector_flow_weekly`, `ds_flow_daily` |
| 3. Nhà đầu tư | `investors` | nhà đầu tư | Khối ngoại, tự doanh, trong nước khác: lũy kế, tỷ trọng, so sánh theo sàn và nhóm vốn hóa | `ds_flow_daily`, `ds_market_flow_series` |
| 4. Dòng tiền và tâm lý | `flow-sentiment` | nhà đầu tư | Cảm xúc tin theo ngành/mã bên cạnh dòng tiền cùng kỳ, số bài, mã được nhắc nhiều | `ds_news_sentiment`, `ds_news_stock_daily`, `ds_flow_daily` |
| 5. Vĩ mô và khối ngoại | `macro` | nhà đầu tư | USD/VND, DXY, S&P 500, dầu, vàng, lợi suất Mỹ cạnh dòng tiền khối ngoại; CPI, SXCN, xuất nhập khẩu, ETF, nhà đầu tư cá nhân theo kỳ | `ds_macro_daily`, view mới của 3.6 |
| 6. Dự báo và khuyến nghị | `forecast` | nhà đầu tư | Dự báo ngành tuần tới và thực tế, độ chính xác theo tuần **cạnh mô hình cơ sở**, khuyến nghị, tín hiệu đảo chiều/lệch pha | `ds_prediction`, `ds_recommendation` (mới) |

**Ràng buộc riêng.** Mỗi metric mới thêm vào `spec.py` phải **khớp SQL gốc** (test `tests/smoke/test_superset.py` kiểm tra; bổ sung test cho metric mới). Dashboard cho khách (`min_role: guest`) chỉ dùng dataset không chứa dữ liệu nhà đầu tư cá nhân hay thông tin riêng; mọi dashboard khác `investor` trở lên. Không nhúng Superset bằng tài khoản quản trị trong trình duyệt: luôn qua `/api/superset/embed/{key}` (guest token 10 phút, một dashboard). View dbt mới chỉ ở thư mục `models/superset/`, không sửa `models/marts`; mỗi view có mô tả và test. Dashboard dự báo/khuyến nghị phải có chú thích mô hình cơ sở và lưu ý đầu tư (R7). Màu "vào/ra" và định dạng số thống nhất cả 6 dashboard (xanh: mua ròng, đỏ: bán ròng). Tối đa khoảng 12 biểu đồ mỗi dashboard; truy vấn nặng dùng materialized view đã có hoặc xin TV1 thêm.

**Kiểm thử bắt buộc.** Test metric khớp SQL cho mọi metric mới; test phân quyền dashboard (khách không mở được dashboard `investor`; token dashboard A không đọc được B: test hiện có, mở rộng cho dashboard mới); test `GET /api/sectors/{code}` (có dữ liệu, 404, quyền); vitest cho `charts/` và thẻ KPI; kiểm tra dựng từ đầu: dựng dự án compose riêng, import dashboard, chạy `provision.py`, mở từng dashboard.

**Cung cấp / cần.** Cung cấp: thư viện biểu đồ và bộ component dùng chung (ngày 1 Tuần 4), định nghĩa KPI, dashboard `overview` cho trang chủ. Cần: dữ liệu vĩ mô tháng từ TV4 (đầu Tuần 4, bạn dựng dashboard 5 sau khi có), tin nổi bật từ TV5, giá trị dự báo/khuyến nghị thật từ TV1 (đã có).

**Nộp (DoD của TV3):** 6 dashboard hoạt động, nhúng được, đúng phân quyền và **có trong `src/superset/dashboards/`**; `dinh_nghia_kpi.md`; `docs/superset_dataset_metric.md` cập nhật; `/api/sectors/{code}` thật; trang Tổng quan và Phân tích ngành; mô tả từng dashboard (mục đích, câu hỏi nó trả lời, cách đọc) cho báo cáo.
### TV4 – Vũ Văn Quảng
| Tuần | Công việc | Phụ thuộc |
|------|-----------|-----------|
| 4 (ưu tiên đầu tuần) | Nhập CSV: vĩ mô (CPI, SXCN, XNK), nhà đầu tư cá nhân từ báo cáo tuần, dòng vốn ETF; chạy script nạp của TV1 và kiểm tra khớp | Script/mẫu CSV của TV1. **Làm xong sớm vì TV3 và TV5 cần dữ liệu này** |
| 4 | API + trang Dự báo & khuyến nghị (dự báo ngành tuần tới, khuyến nghị, lịch sử độ chính xác) dựa trên API ML và `Fact_Prediction` của TV1 (stub nếu chưa xong) | Hợp đồng API ML |
| 5 | Trang Tài khoản (hồ sơ, đổi mật khẩu, danh sách đăng ký cảnh báo) | Auth của TV1 |


**Hướng dẫn chi tiết cho TV4** (thư mục của bạn: `src/backend/app/routers/tv4/`, `src/frontend/src/pages/tv4/`, `src/frontend/src/pages/Account.jsx`, dữ liệu nhập tay, báo cáo)

*Đã có sẵn:* bộ nạp CSV và tệp mẫu (`src/ingestion/templates/`, hướng dẫn và quy tắc kiểm tra ở `README.md` cùng thư mục); `GET /api/predictions` (19 ngành, kèm `rank`, thực tế nếu đã kết thúc), `/api/predictions/accuracy` (độ chính xác theo tuần so với cơ sở), `GET /api/recommendations` (hành động, độ chắc chắn, điểm, tín hiệu, lý do) đều **dữ liệu thật**; trang mẫu `ForecastPage.jsx`, `Account.jsx` (đã có theo dõi mã mẫu).

| # | Việc | Làm ở đâu | Xong khi | Ngày |
|---|------|-----------|----------|------|
| 4.1 | **Nhập số liệu thủ công (làm đầu tiên, TV3 và TV5 chờ)** | CSV của bạn + lệnh bên dưới | Ba tệp thật nạp xong, `dbt test` qua, tài liệu nguồn `docs/nhap_lieu_thu_cong.md` ghi từng nguồn (tên, đường dẫn/số hiệu báo cáo, ngày truy cập) | T4 N1–2 |
| 4.2 | Trang Dự báo và khuyến nghị | `pages/tv4/ForecastPage.jsx` | Xem chi tiết bên dưới | T4 N2–5 |
| 4.3 | Trang Tài khoản | `pages/Account.jsx`, `routers/tv4/account.py` (mới) | Hồ sơ (họ tên, email chỉ đọc), **đổi mật khẩu**, danh sách theo dõi và đăng ký cảnh báo (nhúng `WatchlistPanel` của TV2) | T5 N1–3 |
| 4.4 | Báo cáo cuối kỳ | `docs/baocao_doan.*` (định dạng theo yêu cầu môn học) | Theo dàn ý bên dưới; mọi số liệu truy được | T5 N2–T6 |

**4.1. Nhập số liệu: cách làm.**
- Dữ liệu cần: (a) vĩ mô tháng từ 09/2020 đến tháng gần nhất đã công bố: `CPI_YOY`, `IIP_YOY`, `EXPORT_USD_BN`, `IMPORT_USD_BN` (nguồn gợi ý: Tổng cục Thống kê); (b) mua/bán của nhà đầu tư cá nhân trong nước theo tuần, từ báo cáo tuần của sàn/công ty chứng khoán (nếu không đủ mọi tuần thì nạp tuần có số liệu thật, **không nội suy, không ước lượng**); (c) dòng vốn ròng các quỹ ETF theo tháng (báo cáo quỹ).
- Quy trình mỗi tệp: sao chép tệp mẫu, **xóa dòng mẫu** (dòng có ghi chú "Mẫu minh họa" bị bộ nạp từ chối), điền số thật; cột `source` ghi nguồn cụ thể; `published_date` là **ngày công bố thật** (không biết chính xác thì chọn ngày muộn hơn, không bao giờ sớm hơn) vì mô hình dùng nó để không nhìn trước tương lai. Chạy từ `src/`: `python -m ingestion.cli load-csv macro tệp.csv --dry-run` (sửa mọi lỗi báo ra) rồi bỏ `--dry-run`; sau đó `python dbt_dw/run.py run --select "stg_macro_manual+ stg_individual_weekly+ stg_etf_monthly+"` và `python dbt_dw/run.py test --select "fact_macro_indicator fact_individual_flow_weekly fact_etf_flow_monthly manual_macro_published_after_period"`.
- Kiểm tra khớp (ghi kết quả vào `nhap_lieu_thu_cong.md`): số kỳ nạp so với số kỳ cần; ví dụ mua/bán cá nhân từng tuần không vượt tổng giá trị giao dịch toàn thị trường cùng tuần trong `dw` (`ds_market_flow_series`); giá trị CPI nằm trong khoảng hợp lý (dưới 20% so với cùng kỳ); không có hai nguồn cho cùng một kỳ mà không giải thích.
- Sửa số liệu sai: sửa CSV rồi nạp lại (ghi đè theo khóa); dòng vĩ mô tháng trong `dw` tự đồng bộ ở lần chạy dbt kế tiếp.
- Hạn chót: ngày 2 Tuần 4, báo TV3, TV5 và TV1 ngay khi xong (TV1 huấn luyện lại mô hình ở GĐ3 bằng các số liệu này).

**4.2. Trang Dự báo và khuyến nghị: nội dung và cách trình bày trung thực.**
- *Dự báo tuần tới:* bảng 19 ngành xếp theo `rank` (1 = dự báo mua ròng mạnh nhất): hướng (vào/ra), xác suất mua ròng, giá trị ròng dự báo (tỷ đồng); khi tuần đã kết thúc hiện thêm thực tế và đúng/sai. Có bộ chọn tuần (`?week=`). Hiện rõ **tuần mục tiêu**; nếu chưa có dự báo cho tuần sau thì nói rõ "chưa có dự báo trực tiếp" thay vì hiện tuần cũ như mới.
- *Độ chính xác:* biểu đồ theo tuần (`/api/predictions/accuracy`) với **hai đường: mô hình và cơ sở "tuần sau giống tuần này"**, kèm tổng thể. Câu chú thích bắt buộc, đúng thực tế: dự báo chiều dòng tiền chưa vượt có ý nghĩa thống kê mô hình cơ sở; dự báo giá trị ròng tốt hơn rõ (`ml_ket_qua.md` mục 2). Không dùng cụm "độ chính xác cao".
- *Khuyến nghị:* bảng theo ngành: hành động (tăng/giảm/giữ tỷ trọng), độ chắc chắn, điểm, các tín hiệu đã kích hoạt kèm lời giải thích (`reason`), cảnh báo lệch pha (`signal = mismatch`) nổi bật. Có phần "Cách đọc": quy tắc đã công bố ở `ml_ket_qua.md` mục 5 (ngưỡng đặt trước, không chỉnh theo backtest), khuyến nghị khớp chiều dòng tiền khối ngoại tuần sau nhưng không chuyển thành lợi suất ngành vượt mua đều sau phí.
- Luôn có `Disclaimer`; trạng thái tải, lỗi, rỗng; hiển thị tốt trên điện thoại. Không dùng ngôn từ khuyên mua/bán.

**4.3. Trang Tài khoản.** Backend: **chưa có** đổi mật khẩu và sửa hồ sơ, bạn thêm `PATCH /api/auth/me` (họ tên) và `POST /api/auth/change-password` trong `routers/tv4/account.py`, dùng hàm băm có sẵn trong `app/core/security.py` (bcrypt). Yêu cầu: kiểm tra mật khẩu cũ (sai trả 401 `invalid_credentials`), mật khẩu mới từ 8 ký tự và khác mật khẩu cũ, không trả mật khẩu hay mã băm ở bất kỳ phản hồi nào, không ghi mật khẩu vào nhật ký. Ghi chú giới hạn: token cũ vẫn hợp lệ đến khi hết hạn (60 phút), chấp nhận và ghi vào báo cáo. Thêm endpoint → R2 (báo nhóm, cập nhật contract). Tài khoản mẫu (`APP_DEMO_*`) không được đổi vai trò từ trang này.

**4.4. Dàn ý báo cáo (gợi ý, đối chiếu đề cương).** (1) Bài toán và mục tiêu; (2) Kiến trúc hệ thống (sơ đồ của TV5); (3) Dữ liệu: nguồn, thu thập, làm sạch, chất lượng (`bao_cao_nguon.md`, `kiem_tra_thu_thap.md`, `danh_gia_nguon_du_lieu.md`); (4) Kho dữ liệu Star Schema và OLAP (`thiet_ke_kho.md`); (5) Mô hình: cảm xúc, phân cụm, dự báo, khuyến nghị và backtest (`ml_ket_qua.md`, **giữ nguyên các nhận định trung thực**); (6) Dashboard và website (`superset_dataset_metric.md`, `dinh_nghia_kpi.md`); (7) Insight (`insight_nhap.md`, bản cuối do TV1 chốt Tuần 6); (8) Kiểm thử và đánh giá hệ thống (`kiem_thu_tu_dau.md`); (9) Hạn chế và hướng phát triển (`ban_giao_GD1.md` mục 5); (10) Phụ lục: hướng dẫn cài đặt, API. **Mỗi con số** trong báo cáo ghi nguồn (tệp, truy vấn hoặc lệnh tạo ra nó); không làm tròn có lợi; không bỏ phần kết quả không thuận.

**Ràng buộc riêng.** Dữ liệu nhập tay phải thật và có nguồn, không dùng số ước lượng hay số của LLM; không nạp dòng mẫu vào hệ thống thật; không sửa trực tiếp bảng `raw.manual_*` hoặc `dw` bằng SQL tay (luôn qua CSV và bộ nạp để có `dq_log`). Trang dự báo tuân thủ R7. Endpoint tài khoản chỉ tác động tài khoản của chính người gọi.

**Kiểm thử bắt buộc.** Bộ nạp CSV đã có test (`tests/unit/test_manual_csv.py`); thêm kiểm tra dữ liệu thật như mục 4.1. Backend tài khoản: đổi mật khẩu đúng/sai, mật khẩu ngắn, không đăng nhập, không lộ mã băm; sau khi đổi, đăng nhập bằng mật khẩu mới được và mật khẩu cũ bị từ chối. Frontend: vitest hiển thị trang dự báo với dữ liệu giả (có dòng cơ sở và `Disclaimer`); kiểm thử thủ công mục 5.

**Cung cấp / cần.** Cung cấp: dữ liệu nhập tay (TV3, TV5, TV1), báo cáo. Cần: `GET /api/alerts/subscriptions` và `WatchlistPanel` của TV2 (Tuần 5), sơ đồ của TV5, insight cuối của TV1 (Tuần 6).

**Nộp (DoD của TV4):** ba bộ số liệu thật đã nạp và qua `dbt test`; `nhap_lieu_thu_cong.md`; trang Dự báo và Tài khoản; báo cáo đủ chương, đủ nguồn số liệu.
### TV5 – Nguyễn Văn Quang
| Tuần | Công việc | Phụ thuộc |
|------|-----------|-----------|
| 4 | Kiểm tra 300–500 nhãn cảm xúc, tính Cohen's κ giữa nhãn LLM và nhãn người, sửa nhãn sai, trả lại bộ nhãn chuẩn cho TV1 | Tập mẫu của TV1 |
| 4 | API tin tức và vĩ mô, thành phần Tin nổi bật, trang Vĩ mô, chân trang lưu ý | Dữ liệu vĩ mô (TV4 nhập CSV, trước đó dùng yfinance) |
| 5 | Workflow n8n: bản tin cuối tuần, cảnh báo đảo chiều dòng tiền/tin tiêu cực, báo lỗi ETL | n8n lõi của TV1; payload thống nhất với TV2 |


**Hướng dẫn chi tiết cho TV5** (thư mục của bạn: `src/backend/app/routers/tv5/`, `src/frontend/src/pages/tv5/`, `src/n8n/`, `docs/so_do/`, `data/samples/`)

*Đã có sẵn:* tập 390 bài chưa gán nhãn (`data/samples/sentiment_validation_sample.csv`) kèm hướng dẫn và công cụ (`docs/huong_dan_gan_nhan_cam_xuc.md`, `python -m ml.sentiment_check`); API tin tức thật (`GET /api/news`, `/api/news/highlights`, khách xem tối đa 5 tin, cảm xúc `null` với bài không nhắc mã/ngành nào) và vĩ mô thật (`GET /api/macro/series`); `GET /api/macro/correlation` là **stub** (schema đã chốt: `against`, `items[{code, correlation, window}]`); 4 workflow n8n (`etl-hourly`, `etl-after-close`, `etl-rerun-webhook`, mẫu `alert-dispatch-sample`) sinh từ `src/n8n/build_workflows.py` (hướng dẫn `src/n8n/README.md`); trang mẫu `NewsPage.jsx`.

| # | Việc | Làm ở đâu | Xong khi | Ngày |
|---|------|-----------|----------|------|
| 5.1 | **Gán nhãn cảm xúc 390 bài (làm đầu tiên)** | `data/samples/sentiment_validation_sample.csv` | Cột `label_human` đủ 390 dòng, `python -m ml.sentiment_check --no-db` báo 0 lỗi; một người khác gán độc lập 100 bài đầu để đo độ nhất quán; gửi TV1 tệp chuẩn | T4 N1–3 |
| 5.2 | Đo mô hình trên nhãn người | `python -m ml.sentiment_check --json` | Có accuracy, F1, kappa, ma trận nhầm của mô hình so với nhãn người; ghi vào báo cáo và gửi TV1 | T4 N3 |
| 5.3 | API vĩ mô thật + tương quan | `routers/tv5/news_macro.py` | `GET /api/macro/correlation` thật (xem bên dưới); chuỗi vĩ mô tháng (CPI...) lấy được từ `/api/macro/series` (thêm tham số tùy chọn `frequency=monthly`, giữ nguyên hành vi cũ) kèm `published_date` | T4 N2–4 |
| 5.4 | Giao diện tin tức và vĩ mô | `pages/tv5/NewsPage.jsx`, `MacroPage.jsx` (mới), `components/` | Thành phần **Tin nổi bật** (dùng được ở trang chủ của TV3), trang Tin tức (lọc theo mã/ngành/ngày, phân trang, nhãn cảm xúc), trang Vĩ mô (7 chuỗi ngày, 4 chỉ số tháng, tương quan với khối ngoại), **chân trang lưu ý** (một dòng trong `Layout.jsx`, PR có TV1 xem) | T4 N3–T5 N1 |
| 5.5 | Workflow n8n | `src/n8n/build_workflows.py` + `workflows/` | Ba workflow: bản tin cuối tuần, cảnh báo (đảo chiều dòng tiền, tin tiêu cực), báo lỗi ETL; xem bên dưới | T5 N1–4 |
| 5.6 | **Sơ đồ cho báo cáo** | `docs/so_do/` | Kiến trúc hệ thống, luồng dữ liệu, sơ đồ Star Schema, luồng mô hình, luồng n8n: tệp nguồn (draw.io) + ảnh PNG/SVG; nộp TV4 hạn **ngày 3 Tuần 5** | T4 N4–T5 N3 |
| 5.7 | Kiểm thử toàn hệ thống và slide | `docs/loi_kiem_thu.md` (mới), slide | Danh sách lỗi có người nhận; chạy `python -m handover.check` và checklist `kiem_thu_tu_dau.md` mục 5 vào cuối mỗi tuần; slide Tuần 6 | T5–T6 |

**5.1. Gán nhãn: cách làm đúng.** Làm theo `docs/huong_dan_gan_nhan_cam_xuc.md` (định nghĩa nhãn ở đó). **Gán mù**: không xem nhãn mô hình dự đoán trước khi xong (sẽ làm lệch kết quả). Không dùng công cụ AI để gán thay (nhãn chuẩn của con người là mục đích). Tập này **không** được dùng huấn luyện cho đến khi đo xong lần đầu (TV1 giữ làm tập kiểm tra độc lập; ở GĐ3 nếu cần dùng để huấn luyện lại sẽ tách đôi). Độ nhất quán: người thứ hai gán độc lập 100 bài đầu, điền vào cột `label_llm` của một bản sao (cột này dùng làm "lượt gán thứ hai") rồi chạy `ml.sentiment_check`; kappa dưới 0,6 → họp thống nhất định nghĩa trước khi tiếp. Kế hoạch gốc ghi "tính kappa giữa nhãn LLM và nhãn người": nay không có nhãn LLM cho tập này, thay bằng kappa giữa hai người và độ khớp người-mô hình.

**5.3. Tương quan vĩ mô-khối ngoại.** `against=foreign_net` (khối ngoại mua/bán ròng toàn thị trường theo ngày, từ `dw.mv_market_daily_kpi`); `codes` là mã chỉ số trong `ds_macro_daily` (USDVND, DXY, SP500, WTI, BRENT, GOLD, US10Y); `window` là số phiên. Tương quan tính trên **thay đổi %** hằng ngày của chỉ số quốc tế (không tính trên mức giá, tránh tương quan giả) với dòng ròng khối ngoại cùng ngày; chỉ dùng cửa sổ gần nhất (`window` phiên) và ghi rõ trong phản hồi/giao diện: tương quan không phải nhân quả, chỉ số quốc tế đóng cửa sau thị trường Việt Nam nên có thể thử độ trễ 1 ngày (nếu thêm, thêm tham số tùy chọn `lag`, mặc định 0). Phản hồi giữ schema đã chốt, `stub` thành `false`. Test bằng dữ liệu giả có tương quan biết trước (kết quả khớp công thức) và 404/422 cho mã chỉ số hoặc `window` sai.

**5.5. Workflow n8n: cách làm.**
- Thêm hàm sinh trong `build_workflows.py` (mẫu: `alert_sample`), đăng ký trong `main()`, thêm vào test `tests/unit/test_n8n_workflows_runner.py` (cấu trúc nút, mọi lời gọi HTTP mang `X-Service-Key`, địa chỉ lấy từ biến môi trường, **không có mật khẩu ghi cứng**); sửa script rồi sinh lại JSON, không sửa tay tệp JSON.
- Luồng cảnh báo (thống nhất với TV2, xem "Điểm nối TV2 ↔ TV5"): sau khi `etl-after-close` thành công, n8n gọi endpoint nội bộ của TV2 để lấy danh sách điều kiện đã kích hoạt, với mỗi điều kiện gọi `POST /api/internal/alerts/dispatch` để lấy người nhận rồi gửi email.
- Gửi email: nút Send Email (SMTP) dùng **credential của n8n** (không đưa vào kho mã); môi trường phát triển có thể dùng hộp thư thử (ví dụ MailHog, nếu cần thêm dịch vụ vào `docker-compose.yml` thì báo TV1). Email có đường dẫn về website và câu lưu ý không phải khuyến nghị đầu tư; không gửi quá một thư cùng loại cho cùng người và cùng đối tượng trong một ngày.
- Bản tin cuối tuần: chạy chiều thứ Sáu sau `etl-after-close`; nội dung từ endpoint nội bộ của TV2 (top ngành, dự báo tuần tới, khuyến nghị nổi bật, tin nổi bật), có đủ lưu ý ở R7.
- Báo lỗi ETL: workflow hiện đã ghi sự kiện lỗi vào `app.etl_runs`; thêm email cho quản trị.

**Ràng buộc riêng.** Nhãn người phải do người thật gán (5.1). Không đưa toàn văn bài báo ra giao diện hay email (R11); trang tin chỉ hiện tiêu đề, nguồn, ngày, cảm xúc và liên kết gốc. Khách chỉ thấy tối đa 5 tin (đã được backend áp dụng, giữ nguyên). Cảm xúc là **mức bài** (một bài nhắc nhiều mã có cùng điểm) và chỉ có ý nghĩa cùng phiên: không diễn giải thành "tin tốt nên giá sẽ tăng" (R7). Khóa SMTP, địa chỉ email thật không vào kho mã (R5). n8n chỉ gọi endpoint nội bộ bằng khóa dịch vụ, không dùng token người dùng.

**Kiểm thử bắt buộc.** `ml.sentiment_check` báo 0 lỗi cho tệp nhãn; test `macro/correlation` với dữ liệu giả; test `macro/series` tháng (có `published_date`, không trả số liệu có ngày công bố ở tương lai); test cấu trúc cho mỗi workflow mới (mở rộng test hiện có) và chạy thử thủ công từng workflow qua webhook (ghi lại kết quả); vitest cho thành phần Tin nổi bật; kiểm thử thủ công mục 5 `kiem_thu_tu_dau.md` cho toàn hệ thống.

**Cung cấp / cần.** Cung cấp: bộ nhãn chuẩn và kết quả đo (TV1, đầu Tuần 4), Tin nổi bật (TV3), sơ đồ (TV4), danh sách lỗi (mọi người), slide. Cần: dữ liệu vĩ mô tháng từ TV4 (ngày 2 Tuần 4; trước đó dùng chuỗi yfinance), endpoint nội bộ cảnh báo từ TV2.

**Nộp (DoD của TV5):** tệp nhãn chuẩn + kết quả `ml.sentiment_check`; `macro/correlation` thật; trang Tin tức và Vĩ mô; ba workflow n8n có test và đã chạy thử; sơ đồ trong `docs/so_do/`; `loi_kiem_thu.md` có kết quả vòng kiểm thử cuối Tuần 5; slide.
### Điểm nối giữa các thành viên trong GĐ2 (cần chốt từ đầu Tuần 4)

| Nối | Giữa | Nội dung cần chốt |
|-----|------|-------------------|
| Cảnh báo | TV2 ↔ TV5 | Payload watchlist/cảnh báo, ai gọi ai, tần suất |
| Dữ liệu vĩ mô | TV4 → TV3, TV5 | Tên bảng/cột CSV, thời hạn nạp xong |
| Sơ đồ → báo cáo | TV5 → TV4 | Định dạng và thời hạn nộp sơ đồ |
| Component dùng chung | TV3 → TV2, TV4, TV5 | Thẻ KPI, quy ước dùng; tránh mỗi người tự viết một bản |
| Dự báo | TV4 ↔ TV3 ↔ TV1 | Schema `Fact_Prediction` và API ML không đổi giữa GĐ1, GĐ2 và GĐ3 (GĐ3 chỉ thay giá trị do huấn luyện lại) |
| Nhãn cảm xúc | TV5 → TV1 | TV5 trả bộ nhãn đã kiểm tra trong Tuần 4 để TV1 huấn luyện lại ở GĐ3 |


**Quyết định đề xuất cho các điểm nối (chốt trong 2 ngày đầu Tuần 4; ai không đồng ý nói ngay ở họp đầu Tuần 4, sau đó coi là đã thống nhất):**

| Nối | Quyết định đề xuất | Người làm |
|-----|--------------------|-----------|
| **Cảnh báo TV2 ↔ TV5** | n8n **không** tự tính điều kiện. TV2 thêm hai endpoint nội bộ (khóa dịch vụ `X-Service-Key`, không dùng JWT): `GET /api/internal/alerts/triggers?date=YYYY-MM-DD` trả `{date, items:[{alert_type, entity_type, entity_code, reason, facts}]}` và `GET /api/internal/digest?entity_type=&entity_code=` trả nội dung bản tin (số liệu tuần). Điều kiện: `flow_reversal` = ngành có tín hiệu `reversal_up`/`reversal_down` trong khuyến nghị mới nhất (`dw.fact_recommendation.signals`); `negative_news` = mã/ngành có cảm xúc trung bình ≤ -0,3 từ ít nhất 5 bài trong phiên gần nhất (`dw.fact_news_sentiment`); `weekly_digest` = mọi (đối tượng) có ít nhất một đăng ký còn hiệu lực, chỉ trả vào thứ Sáu. TV5 gọi `triggers`, với mỗi mục gọi `POST /api/internal/alerts/dispatch` (đã có) lấy người nhận rồi gửi email. Để không gửi trùng, TV2 thêm bảng `app.alert_log` (khóa duy nhất: loại, đối tượng, ngày nghiệp vụ, người dùng) và `dispatch` bỏ qua người đã nhận | TV2 (endpoint, bảng), TV5 (workflow) |
| **Dữ liệu vĩ mô TV4 → TV3, TV5** | Bảng đích: `dw.fact_macro_indicator` (nguồn `manual_csv`, 4 chỉ số tháng `CPI_YOY`, `IIP_YOY`, `EXPORT_USD_BN`, `IMPORT_USD_BN`), `dw.fact_individual_flow_weekly`, `dw.fact_etf_flow_monthly`. Hạn nạp: ngày 2 Tuần 4. TV3 tạo view `ds_macro_monthly`, `ds_individual_weekly`, `ds_etf_monthly` cho Superset; TV5 thêm `frequency=monthly` vào `/api/macro/series`. Chuỗi tháng luôn hiển thị kèm ngày công bố | TV4, TV3, TV5 |
| **Theo dõi và Tài khoản TV2 ↔ TV4** | TV2 sở hữu API theo dõi/cảnh báo và component `WatchlistPanel`; TV4 chỉ nhúng vào trang Tài khoản. TV2 thêm `GET /api/alerts/subscriptions` trước cuối Tuần 4 | TV2, TV4 |
| **Thư viện biểu đồ và component TV3 → cả nhóm** | TV3 thêm `recharts` và `components/charts/` ngày 1 Tuần 4 (PR riêng, gộp trong ngày); thẻ KPI, chân trang lưu ý, `Disclaimer` dùng chung; component mới dùng chung thêm vào `components/` và báo TV3 | TV3 |
| **Tin nổi bật TV5 → TV3** | TV5 làm component `HighlightNews` (dùng `/api/news/highlights`, khách xem được, tối đa 5 tin); TV3 đặt vào trang Tổng quan | TV5, TV3 |
| **Sơ đồ TV5 → TV4** | Thư mục `docs/so_do/`; mỗi sơ đồ có tệp nguồn (draw.io) và ảnh PNG/SVG; hạn nộp ngày 3 Tuần 5; sơ đồ theo `thiet_ke_kho.md` và `ban_giao_GD1.md`, không vẽ thành phần chưa có | TV5, TV4 |
| **Nhãn cảm xúc TV5 → TV1** | Tệp chuẩn + kết quả `ml.sentiment_check` trong 3 ngày đầu Tuần 4; TV1 giữ làm tập kiểm tra độc lập, ở GĐ3 tách đôi nếu dùng để huấn luyện lại | TV5, TV1 |
| **Dự báo, khuyến nghị TV4 ↔ TV3 ↔ TV1** | Schema `fact_prediction`, `fact_recommendation` và API `/api/predictions`, `/api/recommendations` không đổi; TV3 dựng view `ds_recommendation` từ `fact_recommendation` (TV1 không đổi cột). Số liệu bản cuối do TV1 ghi lại ở GĐ3, giao diện không phải sửa | TV1, TV3, TV4 |
| **Lưu dashboard Superset TV3 ↔ TV1** | Quy trình xuất/nạp dashboard vào kho mã chưa thử đầu cuối; ngày 2 Tuần 4 TV1 và TV3 cùng chạy thử trên dự án compose riêng rồi chốt | TV3, TV1 |

**Việc TV1 làm trong GĐ2 (hỗ trợ, không chặn bạn):** phản hồi Issue trong 1 ngày làm việc; review PR của bạn trong 1 ngày; cập nhật dữ liệu hằng ngày (`ingestion.cli daily` → pipeline tin → dbt, sau 15h) và dự báo/khuyến nghị tuần mới (chiều thứ Sáu); thêm view `dw` hoặc quyền đọc khi có lý do chính đáng; kiểm tra ngày 2 Tuần 4 cùng TV3 (lưu dashboard); mỗi cuối tuần chạy `python -m handover.check` và `pytest` trên nhánh chung, báo ai làm hỏng.

### Cổng G2 (cuối Tuần 5)
- Mỗi trang/chức năng của TV2–TV5 chạy được trên môi trường `docker compose`, merge vào nhánh chung, không phá build.
- 6 dashboard Superset hoạt động, nhúng được vào website, đúng phân quyền.
- Chatbot, n8n, trang quản trị chạy được với dữ liệu thật hoặc stub.
- Danh sách lỗi từ kiểm thử đã giao lại, các lỗi nghiêm trọng đã xử lý.
- `python -m handover.check` vẫn 10/10 đạt, `pytest -m "smoke or not smoke"` và `dbt test` qua trên nhánh chung; không còn endpoint `stub` ngoài `POST /ml/sentiment` trong Docker.
- Dashboard Superset có trong `src/superset/dashboards/` và dựng lại được từ đầu; số liệu nhập tay thật đã nạp và qua `dbt test`.
- Mỗi trang kèm lưu ý đầu tư và mô hình cơ sở (ràng buộc R7); kiểm thử thủ công giao diện (`kiem_thu_tu_dau.md` mục 5) đã làm và ghi kết quả.
- Mọi commit theo `loại(nhom01-65httt): mô tả`, không co-author AI; không có `.env`, dữ liệu hay gói seed trong git.

---

## 4. Giai đoạn 3 – Hoàn thiện (Tuần 6, TV1)

Các mô hình, API, khuyến nghị và backtest sơ bộ đã có từ GĐ1. Tuần 6 TV1 chỉ chốt bản cuối, tích hợp và demo. TV2–TV5 hỗ trợ: sửa lỗi trang của mình, hoàn thiện báo cáo/slide.

| # | Công việc TV1 | Ghi chú |
|---|---------------|---------|
| 1 | Hoàn tất nốt phần ML còn tràn từ GĐ1/GĐ2 (nếu có) | Không để quá đầu Tuần 6 |
| 2 | Đo mô hình cảm xúc hiện tại trên bộ nhãn người của TV5 (`ml.sentiment_check`); nếu dùng nhãn người để huấn luyện lại thì **tách đôi** (một nửa huấn luyện, một nửa kiểm tra độc lập); ghi Accuracy, F1, Cohen's κ | Chạy lại ghi `Fact_News_Sentiment` |
| 3 | Huấn luyện lại mô hình dự báo với đủ đặc trưng (có CPI, ETF, nhà đầu tư cá nhân do TV4 nhập) và nhãn cảm xúc mới; chạy so sánh có/không cảm xúc, có/không vĩ mô; ghi lại `Fact_Prediction` | Schema không đổi nên TV3, TV4 không phải sửa |
| 4 | Chạy lại phân cụm nếu dữ liệu đổi, rà tên cụm | |
| 5 | Chạy lại backtest khuyến nghị với dự báo bản cuối, so với VN-Index | |
| 6 | Chốt 3–5 insight có số liệu, mỗi insight kèm đề xuất hành động (cập nhật bản nháp từ GĐ1) | Chuyển cho TV4 đưa vào báo cáo, cho TV5 đưa vào slide |
| 7 | Tích hợp, chạy thử từ đầu `docker compose up`, sửa lỗi, tối ưu truy vấn chậm | |
| 8 | Duyệt báo cáo cuối kỳ + slide, chuẩn bị và tập demo cả nhóm | |

**Hỗ trợ trong Tuần 6**
- TV4: hoàn thiện báo cáo cuối kỳ (ghép insight, kết quả mô hình, backtest).
- TV5: hoàn thiện slide, chạy lại kiểm thử toàn hệ thống sau tích hợp.
- TV2, TV3: sửa lỗi trang/dashboard khi dữ liệu thật thay stub, phụ TV5 kiểm thử.

---

## 5. Rủi ro và cách giảm

| Rủi ro | Hậu quả | Cách giảm |
|--------|---------|-----------|
| GĐ1 của TV1 là nút cổ chai (khối lượng lớn, 3 tuần, TV2–TV5 chờ) | Cả nhóm trễ | Ưu tiên theo thứ tự "chặn người khác trước"; giao gói bàn giao theo mục; nếu hạng mục 1–5 xong sớm thì mở GĐ2 sớm, các mục còn lại bàn giao dần |
| API CafeF/Vietcap đổi hoặc chặn (là API không chính thức) | Thiếu dữ liệu | Lưu thô vào `raw` ngay khi lấy; chốt nguồn dự phòng (bài tổng hợp phiên VnEconomy/Vietstock) trong Tuần 1 |
| GĐ1 của TV1 quá tải hơn nữa vì thêm ML | Gói bàn giao trễ, 4 người kia chờ | ML xếp sau hạng mục 1–5 của gói bàn giao; ML được tràn sang đầu Tuần 4 với API stub; cảm xúc chạy nền sớm; huấn luyện trên Colab/Kaggle nếu thiếu GPU; cắt phạm vi phụ (hồi quy giá trị) nếu trễ |
| Mô hình GĐ1 huấn luyện bằng nhãn LLM chưa kiểm và thiếu CPI/ETF | Kết quả bản đầu chưa phản ánh đúng | Chấp nhận như bản nháp; GĐ3 huấn luyện lại bằng nhãn chuẩn và đủ đặc trưng; giữ nguyên schema nên không ảnh hưởng module khác |
| Đổi schema/API giữa chừng làm hỏng module người khác | Trang lỗi hàng loạt | Đóng băng API contract ở cổng G1; thay đổi phải thông báo cả nhóm và cập nhật tài liệu |
| Xung đột merge khi 4 người làm song song | Mất thời gian sửa | Sở hữu thư mục riêng, PR nhỏ, sửa file chung qua PR, rebase thường xuyên |
| TV4 nhập CSV chậm làm TV3, TV5 chờ dữ liệu vĩ mô | Dashboard và trang Vĩ mô trống | TV4 làm đầu Tuần 4; TV5 dùng dữ liệu yfinance trong lúc chờ |
| Nhãn cảm xúc kiểm tra chậm | Không huấn luyện được PhoBERT kịp | TV5 làm nhãn ngay đầu Tuần 4; TV1 có thể dùng nhãn LLM để chạy baseline trước |
| Dashboard Superset dựng bằng giao diện chỉ nằm trong volume Superset | Mất sạch khi `docker compose down -v` hoặc dựng máy mới, không chạy lại từ đầu được | TV3 xuất dashboard vào `src/superset/dashboards/` mỗi cuối tuần; TV1 và TV3 chứng minh dựng lại từ đầu ở ngày 2 Tuần 4 (mục 3, TV3, việc 3.4) |
| Mỗi người tự thêm một thư viện biểu đồ hoặc component riêng | Giao diện không đồng nhất, `package-lock.json` xung đột | TV3 thêm một thư viện chung ngày 1 Tuần 4; ba người còn lại chờ PR đó (R12) |
| Chatbot gọi LLM ngoài: hết hạn mức, tốn phí, trả lời sai hoặc bị chèn chỉ dẫn từ nội dung bài báo | Demo hỏng, câu trả lời sai thành "lời khuyên" | LLM chỉ chọn truy vấn có sẵn; bộ định tuyến dự phòng không cần khóa; giới hạn số lượt hỏi; mọi câu trả lời kèm nguồn và lưu ý (mục 3, TV2) |
| Giao diện trình bày dự báo, khuyến nghị quá lạc quan | Sai sự thật (mô hình chưa vượt cơ sở), rủi ro bị hỏi khi bảo vệ | R7: luôn cạnh mô hình cơ sở và lưu ý; TV1 duyệt chữ trên trang dự báo trước khi nộp |
| Số liệu nhập tay không có nguồn hoặc có `published_date` sớm hơn thực tế | Mô hình nhìn trước tương lai, báo cáo không kiểm chứng được | Bộ nạp chặn ngày công bố trước cuối kỳ; `nhap_lieu_thu_cong.md` ghi nguồn từng dòng (mục 3, TV4) |
| Chỉ kiểm thử tự động, giao diện chưa ai thao tác thật | Lỗi hiển thị lộ ra lúc demo | Checklist thủ công `kiem_thu_tu_dau.md` mục 5, mỗi người làm cho trang của mình; TV5 tổng hợp `loi_kiem_thu.md` |

## 6. Mốc kiểm soát

| Mốc | Thời điểm | Điều kiện đạt |
|-----|-----------|---------------|
| G1 | Cuối Tuần 3 | Gói bàn giao GĐ1 đủ 10 hạng mục (hạng mục 6 được phép là stub cho endpoint ML chưa xong) |
| G1-ML | Đầu Tuần 4 | Cả 3 mô hình bản đầu chạy qua API thật, đã ghi vào `dw`, backtest sơ bộ có kết quả |
| Đồng bộ | Cuối Tuần 4 | Mỗi người báo cáo phần cốt lõi, chốt điểm nối còn lại; TV5 trả bộ nhãn đã kiểm tra |
| G2 | Cuối Tuần 5 | Hệ thống chạy tích hợp với dữ liệu thật, lỗi nghiêm trọng đã xử lý |
| Hoàn tất | Cuối Tuần 6 | Mô hình bản cuối, backtest, báo cáo, slide, demo chạy bằng một lệnh Docker Compose |
