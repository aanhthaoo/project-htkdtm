# Thiết kế kho dữ liệu (Star Schema) – chốt ở N2

Căn cứ: mục 8 đề cương và kết quả kiểm chứng nguồn trong [bao_cao_nguon.md](bao_cao_nguon.md). Đây là đặc tả để N3 (stg) và N4 (dbt) cài đặt; DDL thực tế do dbt sinh ra.

## 1. Quy ước chung

| Hạng mục | Quy ước |
|----------|---------|
| Schema | `raw` (thô) → `stg` (sạch) → `dw` (Star Schema). Tên bảng chữ thường, `snake_case`, tiền tố `dim_` / `fact_` |
| Khóa chiều | Khóa thay thế số nguyên (`*_key`), khóa tự nhiên giữ lại làm cột (ví dụ `symbol`) |
| Khóa ngày | `date_key` = số nguyên `YYYYMMDD` (ví dụ 20240110) |
| Tiền | Tỷ VNĐ, `numeric(18,4)`, hậu tố `_bn`. Giá cổ phiếu: đồng, hậu tố `_vnd` |
| Khối lượng | Số cổ phiếu, `bigint` |
| Múi giờ | `timestamptz`, lưu UTC, hiển thị GMT+7 |
| Ngày giao dịch | Một ngày là ngày giao dịch nếu VN-Index có dữ liệu giá hôm đó (không dùng lịch nghỉ lễ gõ tay) |
| Ngành | ICB cấp 1 đến cấp 4; cấp 2 (siêu ngành) là mức phân tích và dự báo; xem mục 4 |
| Cập nhật chiều | Loại 1 (ghi đè giá trị hiện tại). Hạn chế đã biết: ngành/sàn của mã không lưu lịch sử thay đổi |
| Truy vết | Mọi bảng `stg` và `dw` có `source`, `loaded_at`; bản ghi bị loại ghi vào `dw.dq_log` |

## 2. Bảng chiều (Dim)

| Bảng | Khóa | Cột chính | Nguồn |
|------|------|-----------|-------|
| `dim_time` | `date_key` | `date`, `day_of_week`, `week_start_date` (thứ Hai), `week_key`, `month`, `quarter`, `year`, `is_trading_day`, `next_trading_date` | Sinh từ lịch + VN-Index |
| `dim_stock` | `stock_key` | `symbol`, `name_vi`, `exchange` (HOSE/HNX/UPCOM), `security_type` (STOCK/INDEX), `sector_key`, `listing_date`, `delisted_date`, `is_active`, `issue_shares`, `market_cap_bn`, `cap_group` (large/mid/small), `index_group` (VN30/VNMidCap/VNSmallCap/HNX30), `liquidity_group`, `max_foreign_pct`, `cluster_label`, `cluster_model_key` | Vietcap `getAll`, Vietcap iQ công ty, nhóm chỉ số; cụm do ML (N8) |
| `dim_sector` | `sector_key` | `icb_l4_code`, `icb_l4_name`, `icb_l3_code`, `icb_l3_name`, `icb_l2_code`, `icb_l2_name_vi`, `icb_l2_name_en`, `icb_l1_code`, `icb_l1_name`, `analysis_group` | Mã từ Vietcap iQ (cấp 2 và 4), cấp 1 và 3 suy ra từ tiền tố; tên các cấp từ bảng ICB (seed) |
| `dim_investor_type` | `investor_type_key` | `code` (FOREIGN / PROP / OTHER_DOMESTIC), `name_vi`, `derived` (true cho OTHER_DOMESTIC) | Seed |
| `dim_source` | `source_key` | `name`, `section`, `source_type` (BACKFILL / RSS / CRAWL), `publisher`, `feed_timezone` | Seed |
| `dim_article` | `article_key` | `title`, `url`, `published_at`, `session_date_key`, `source_key`, `category`, `content_hash`, `is_market_related` | `stg` tin tức |
| `dim_indicator` | `indicator_key` | `code`, `name_vi`, `unit`, `frequency` (daily / weekly / monthly), `scope` (domestic / international), `origin` (yfinance / manual_csv / cafef) | Seed |
| `dim_model` | `model_key` | `name`, `task` (sentiment / forecast / cluster), `version`, `trained_at`, `train_range`, `metrics` (jsonb) | Ghi khi huấn luyện |
| `dim_event` | `event_key` | `event_type` (FTSE / MSCI / ETF_REBALANCE ...), `name`, `announce_date_key`, `effective_date_key` | Nhập tay (CSV, TV4) |

Thay đổi so với đề cương:
- Thêm `dim_article`: bảng sự kiện cảm xúc cần tiêu đề, đường dẫn và nguồn để hiển thị trên website; để trong chiều tránh lặp lại ở mỗi dòng.
- Nhóm vốn hóa lấy từ Vietcap iQ (`marketCap`, `issueShare`), đúng như đề cương. Vốn hóa là **ảnh chụp hiện tại**: `cap_group` chia theo ngưỡng cố định trên vốn hóa hiện tại và áp dụng cho cả lịch sử (một mã có thể đã thuộc nhóm khác ở năm trước). Thêm `index_group` (VN30, VNMidCap, VNSmallCap, HNX30 từ Vietcap, cũng là danh sách hiện tại) và `liquidity_group` (tứ phân vị giá trị giao dịch trung bình 3 tháng) làm các cách nhóm bổ sung.
- `dim_stock` chứa cả VN-Index (`security_type = 'INDEX'`) để dùng chung `fact_daily_price` cho chỉ số tham chiếu và backtest.

## 3. Bảng sự kiện (Fact)

### 3.1. `fact_money_flow`
- Grain: 1 mã × 1 ngày giao dịch × 1 nhóm nhà đầu tư.
- Khóa: (`date_key`, `stock_key`, `investor_type_key`) duy nhất.
- Số đo: `buy_value_bn`, `sell_value_bn`, `net_value_bn` (= mua − bán), `buy_volume`, `sell_volume`, `net_volume`.
- Cờ: `is_derived`, `includes_prop` (xem dưới), `source`.
- Cách tính:
  - FOREIGN và PROP lấy từ **VNDirect** (`foreigns`, `proprietary_trading`), giá trị trả bằng đồng, chia 10^9 để ra tỷ VNĐ. VNDirect gồm cả giao dịch thỏa thuận; CafeF chỉ khớp lệnh (xem báo cáo nguồn mục 2.5).
  - OTHER_DOMESTIC: mỗi giao dịch có một bên mua và một bên bán nên tổng mua = tổng bán = tổng giá trị giao dịch của mã. Do đó `buy = T − foreign_buy − prop_buy`, `sell = T − foreign_sell − prop_sell`, với `T` = giá trị khớp lệnh + giá trị thỏa thuận (`nmValue + ptValue` của VNDirect). Vì khối ngoại và tự doanh của VNDirect đã gồm thỏa thuận nên định nghĩa `T` thống nhất. Kiểm tra ở N3: nếu tỷ lệ bản ghi OTHER_DOMESTIC âm vượt `money_flow.max_other_negative_rate` thì xem lại định nghĩa.
  - Khối ngoại theo mã đủ từ 01/09/2020. Tự doanh theo mã chỉ từ 17/05/2022 (xem báo cáo nguồn mục 2.3); mã nhỏ chỉ có dòng ở những ngày có giao dịch tự doanh, ngày không có dòng sau mốc này coi là 0. Với những ngày trước 17/05/2022, không tạo dòng PROP, và dòng OTHER_DOMESTIC gắn `includes_prop = true` (nghĩa là gộp cả tự doanh). Bài toán dự báo chính dùng khối ngoại nên không bị ảnh hưởng.

### 3.2. `fact_daily_price`
- Grain: 1 mã (hoặc chỉ số) × 1 ngày giao dịch.
- Số đo: `open_vnd`, `high_vnd`, `low_vnd`, `close_vnd`, `adj_close_vnd`, `pct_change`, `matched_volume`, `matched_value_bn`, `putthrough_volume`, `putthrough_value_bn`, `total_value_bn` (= khớp + thỏa thuận).
- Nguồn VNDirect `stock_prices`: giá tính bằng nghìn đồng, nhân 1000 khi nạp; giá trị khớp lệnh và thỏa thuận tính bằng đồng, chia 10^9. `adj_close` là giá điều chỉnh (chia cổ tức/tách cổ phiếu). VN-Index lấy từ CafeF (VNDirect không có).

### 3.3. `fact_news_sentiment`
- Grain: 1 bài báo × 1 thực thể được nhắc (một mã hoặc một ngành).
- Khóa: (`article_key`, `entity_type`, `stock_key` hoặc `sector_key`).
- Số đo/thuộc tính: `sentiment_score` (−1..1), `sentiment_label` (positive / neutral / negative), `confidence`, `model_key`, `session_date_key` (phiên giao dịch gán cho bài, theo quy tắc 15h).
- `entity_type` ∈ {STOCK, SECTOR}; đúng một trong `stock_key`, `sector_key` khác rỗng (ràng buộc CHECK).

### 3.4. `fact_macro_indicator`
- Grain: 1 chỉ số × 1 kỳ (ngày với chỉ số hằng ngày, tháng/tuần với chỉ số khác).
- Số đo: `value`, `pct_change_prev` (so với kỳ trước), `period_start_date_key`, `period_end_date_key`, `published_date_key` (ngày công bố; với chỉ số tháng dùng để tránh nhìn trước tương lai).
- Chứa cả các chuỗi nhập tay: nhà đầu tư cá nhân (mua/bán ròng theo tuần, từ báo cáo FiinTrade), dòng vốn ETF theo tuần, CPI, sản xuất công nghiệp, xuất nhập khẩu. Chuỗi mua/bán ròng của nhà đầu tư cá nhân để ở đây, không ở `fact_money_flow`, vì chỉ có mức toàn thị trường theo tuần.

### 3.5. `fact_prediction`
- Grain: 1 ngành × 1 tuần mục tiêu × 1 mô hình × 1 chân trời (1–4 tuần).
- Số đo: `predicted_class` (INFLOW / OUTFLOW), `prob_inflow`, `predicted_net_value_bn`, `actual_net_value_bn` và `actual_class` (cập nhật sau khi tuần kết thúc), `made_at`.
- Ghi tại thời điểm dự báo; không ghi đè dự báo cũ để theo dõi độ chính xác theo thời gian.

## 4. Ngành

ICB (Industry Classification Benchmark) chia ngành thành 4 cấp, mỗi mã cổ phiếu thuộc đúng một nhánh. Ví dụ Vinamilk (VNM):

| Cấp | Tên cấp | Mã | Tên (ví dụ VNM) |
|-----|---------|----|-----------------|
| 1 | Industry (ngành) | 3000 | Consumer Goods |
| 2 | Supersector (siêu ngành) | 3500 | Food & Beverage |
| 3 | Sector (nhóm ngành) | 3570 | Food Producers |
| 4 | Subsector (phân ngành) | 3577 | Food Products |

Nguồn dữ liệu: Vietcap iQ trả mã **cấp 2 (`icbCodeLv2`) và cấp 4 (`icbCodeLv4`)** cho từng mã. Cấp 1 và 3 suy ra từ tiền tố mã cấp 4: cấp 1 = chữ số đầu + `000`, cấp 3 = ba chữ số đầu + `0`. Tên tiếng Việt và tiếng Anh của cấp 1, 3, 4 không có trong phản hồi nên phải lập bảng seed từ tài liệu ICB và đối chiếu thủ công trước khi dùng. (Ví dụ trên theo cấu trúc ICB 2008; tên cấp 3 và 4 chỉ để minh họa, bảng seed là bản chốt.)

Cấp 2 có 19 mã (cổ phiếu đang niêm yết), dùng làm mức phân tích và dự báo:

| Cấp 1 (industry) | Cấp 2 (mã: tên) |
|------------------|-----------------|
| 0001 Dầu khí | 0500 Oil & Gas |
| 1000 Vật liệu cơ bản | 1300 Chemicals; 1700 Basic Resources |
| 2000 Công nghiệp | 2300 Construction & Materials; 2700 Industrial Goods & Services |
| 3000 Hàng tiêu dùng | 3300 Automobiles & Parts; 3500 Food & Beverage; 3700 Personal & Household Goods |
| 4000 Y tế | 4500 Health Care |
| 5000 Dịch vụ tiêu dùng | 5300 Retail; 5500 Media; 5700 Travel & Leisure |
| 6000 Viễn thông | 6500 Telecommunications |
| 7000 Tiện ích | 7500 Utilities |
| 8000 Tài chính | 8300 Banks; 8500 Insurance; 8600 Real Estate; 8700 Financial Services |
| 9000 Công nghệ | 9500 Technology |

- 19 cổ phiếu thiếu mã ngành trong `getAll`; cần gọi Vietcap iQ để xem có bổ sung được không, nếu không thì gán "Chưa phân loại" và loại khỏi dự báo theo ngành.
- Dự báo ở cấp 2. Ngành có dưới `min_liquid_stocks_per_sector` (5) mã đủ thanh khoản được gộp vào nhóm "khác" qua `dim_sector.analysis_group`. Số mã niêm yết (chưa lọc thanh khoản) trong các ngành nhỏ: Viễn thông 8, Bảo hiểm 13, Dầu khí 12, Ô tô và phụ tùng 18; tính lại ở N4 sau khi lọc thanh khoản.
- Drill-down trên dashboard: toàn thị trường → cấp 1 → cấp 2 → cấp 3 → cấp 4 → mã.

## 5. Luồng dữ liệu nguồn → kho

| Nguồn | `raw` | `stg` | `dw` |
|-------|-------|-------|------|
| VNDirect giá | `raw.vnd_stock_prices` | `stg.price_daily` | `fact_daily_price` |
| VNDirect khối ngoại | `raw.vnd_foreigns` | `stg.flow_daily` (gộp ba nhóm) | `fact_money_flow` |
| VNDirect tự doanh | `raw.vnd_proprietary` | `stg.flow_daily` | `fact_money_flow` |
| CafeF (VN-Index; đối chiếu) | `raw.cafef_price`, `raw.cafef_foreign` | `stg.price_daily`, `stg.flow_check` | `fact_daily_price` (VN-Index); kiểm tra chéo vào `dq_log` |
| Vietcap `getAll`, nhóm chỉ số, iQ công ty | `raw.vietcap_symbols`, `raw.vietcap_company` | `stg.stock_master` | `dim_stock`, `dim_sector` |
| yfinance | `raw.yf_prices` | `stg.macro_daily` | `fact_macro_indicator` |
| CSV nhập tay | `raw.manual_*` | `stg.macro_manual` | `fact_macro_indicator`, `dim_event` |
| Tin tức (backfill, RSS, crawl) | `raw.news_*` | `stg.news_article` | `dim_article`, `fact_news_sentiment` |

Bảng `raw.*` lưu nguyên phản hồi (jsonb hoặc cột gốc) kèm `source`, `fetched_at`, tham số gọi. Khóa chống trùng: (nguồn, mã, ngày) cho dữ liệu giao dịch; băm nội dung chuẩn hóa cho tin tức.

## 6. Ngưỡng chất lượng

Toàn bộ ngưỡng được chốt trong [quality_thresholds.yml](../src/etl/config/quality_thresholds.yml). Các ngưỡng đáng chú ý:
- Đối chiếu chéo tổng ròng khối ngoại/tự doanh toàn thị trường: đạt nếu lệch ≤ 5 tỷ hoặc ≤ 2%.
- Tỷ lệ mã có giá mỗi ngày giao dịch ≥ 90%; tỷ lệ thiếu giá ≤ 0,5%.
- Mã giữ lại để phân tích: giá trị giao dịch trung bình 20 phiên ≥ 0,5 tỷ.
- Tỷ lệ OTHER_DOMESTIC âm ≤ 1%.
- Cohen's κ giữa nhãn LLM và nhãn người ≥ 0,6.

## 7. Đối chiếu câu hỏi nghiệp vụ → bảng/cột

| # | Câu hỏi (mục 3.3 đề cương) | Bảng và cột trả lời |
|---|----------------------------|---------------------|
| 1 | Dòng tiền vào/ra ngành nào theo ngày, tuần, tháng | `fact_money_flow.net_value_bn` ⨝ `dim_stock.sector_key` ⨝ `dim_sector` ⨝ `dim_time` (`week_start_date`, `month`) |
| 2 | Khối ngoại và tự doanh mua hay bán ở ngành/mã nào; cùng chiều hay trái chiều | `fact_money_flow` lọc `dim_investor_type.code` ∈ {FOREIGN, PROP}; so dấu `net_value_bn` giữa hai nhóm (tự doanh theo mã chỉ có từ cuối 2022; trước đó dùng mức toàn thị trường/ngành từ bài tổng hợp) |
| 3 | Tâm lý tin tức từng ngành, tương quan với dòng tiền | `fact_news_sentiment.sentiment_score` (entity SECTOR hoặc STOCK→sector) gộp theo tuần, nối `fact_money_flow` theo ngành và tuần |
| 4 | Vĩ mô và quốc tế ảnh hưởng thế nào đến dòng tiền khối ngoại | `fact_macro_indicator.value`/`pct_change_prev` nối `fact_money_flow` (FOREIGN) theo ngày/tuần; chỉ số tháng dùng `published_date_key` |
| 5 | Tuần tới ngành nào hút tiền | `fact_prediction.predicted_class`, `prob_inflow`, `predicted_net_value_bn` |
| 6 | Cổ phiếu nào được gom đều, cổ phiếu nào bị xả | `fact_money_flow` (chuỗi mua/bán ròng theo mã) và `dim_stock.cluster_label` |

KPI mục 10.1 đề cương: giá trị ròng (`net_value_bn`), tỷ trọng dòng tiền ngành (`fact_daily_price.total_value_bn` theo ngành / toàn thị trường), chuỗi mua/bán ròng (cửa sổ trên `fact_money_flow`), chỉ số cảm xúc ngành (`fact_news_sentiment` có trọng số nguồn), độ chính xác dự báo (`fact_prediction.predicted_class = actual_class`). Cả sáu câu hỏi và năm KPI đều trả lời được từ thiết kế trên.

## 8. Điểm khác với đề cương (cần ghi vào báo cáo cuối kỳ)

1. Nguồn dữ liệu giao dịch chính là VNDirect (CafeF là nguồn phụ và nguồn VN-Index).
2. Thêm `dim_article`.
3. Tự doanh theo mã chỉ từ 17/05/2022 (khối ngoại và giá từ 01/09/2020); cờ `includes_prop` ghi nhận.
4. Vốn hóa và ICB là ảnh chụp hiện tại, áp dụng cho cả lịch sử.
5. Chuỗi nhà đầu tư cá nhân và ETF nằm trong `fact_macro_indicator`.
6. Tên các cấp ICB 1, 3, 4 cần lập bảng seed từ tài liệu ICB.

## 9. Hiện thực (N3–N5): khác biệt so với đặc tả ở trên

Mã dbt: [src/dbt_dw/](../src/dbt_dw/). Khác biệt so với các mục trên:

| Hạng mục | Đặc tả | Hiện thực | Lý do |
|----------|--------|-----------|-------|
| Khóa thay thế | Số nguyên | `bigint` lấy 60 bit đầu của md5 khóa tự nhiên (`macros/keys.sql`) | Ổn định khi thêm dòng mới, nạp tăng dần không vỡ khóa |
| Cột giá trong `fact_daily_price` | `*_vnd` | `*_price` | VN-Index dùng chung bảng nên đơn vị là điểm; xem `dim_stock.security_type` |
| `fact_daily_price` | Giá, thanh khoản | Thêm `has_trading`, `is_outlier_pct` (biến động > 30%), `is_price_repaired` | Gắn cờ chất lượng, không lọc bỏ |
| `fact_money_flow` | Mọi dòng | Chỉ ngày khối ngoại "đủ" (`stg_day_quality.is_foreign_complete`); chỉ dòng có giao dịch (không có dòng = 0); thêm `includes_prop`, `is_clipped` | VNDirect thiếu 16 ngày khối ngoại trong lịch sử (xem mục 10) |
| `dim_sector` | ICB cấp 1 đến 4 | Mỗi dòng một phân ngành cấp 4 (kèm cấp 1 đến 3) + dòng `<cấp 2>_NA` cho mã chưa có cấp 4 + dòng `UNCLASSIFIED` | Vietcap iQ tải dần; mã chưa có cấp 4 vẫn gán được ngành cấp 2 |
| Bảng thêm | – | `stock_cluster` (nhãn cụm do ML ghi), `bridge_article_entity` (bài x mã/ngành), `mv_sector_weekly_flow`, `mv_market_daily_kpi` | `dim_stock` được dbt dựng lại nên nhãn cụm phải ở bảng riêng |
| Bảng giữ chỗ | – | `dim_model`, `dim_event`, `fact_prediction`, `fact_news_sentiment`, `stock_cluster`: incremental + `full_refresh: false` | Không bị xóa khi dbt dựng lại |
| Lịch giao dịch | VN-Index | Hợp VNDirect (≥ 100 mã khớp lệnh) và VN-Index CafeF | CafeF thiếu phiên 17/05/2024 và 03/02/2025 |
| Tên ICB cấp 3, 4 | – | Seed `icb.csv` viết theo cấu trúc ICB 2008, cột `name_verified = false` | Cần đối chiếu với tài liệu ICB |
| Tách từ tiếng Việt | Ở bước biến đổi | Chưa làm trong N5; làm ở N8 trên tập bài đã lọc | Tách từ 300 nghìn bài chậm, chỉ cần cho mô hình cảm xúc |

## 10. Kết quả kiểm tra chất lượng (chạy ngày 25/11/2026)

Bộ kiểm thử dbt (80 test) và `python -m etl.quality_checks` đều đạt. Đáng chú ý:

| Kiểm tra | Kết quả |
|----------|---------|
| Đối chiếu raw -> dw (khối ngoại ròng, tổng giá trị giao dịch) | Chênh lệch dưới 0,000001 tỷ đồng |
| Tổng khớp lệnh các mã HOSE (VNDirect) so với giá trị khớp lệnh VN-Index (CafeF) | 99,8% số ngày trong khoảng 0,80–1,02 (tỷ lệ bình thường 0,85–0,97) |
| Tỷ lệ ô (mã x ngày) thiếu giá | 0,06% (ngưỡng 0,5%) |
| Tỷ lệ dòng "trong nước khác" bị làm tròn về 0 vì âm | 0,20% (ngưỡng 1%); tính theo tổng giá trị gồm thỏa thuận cho kết quả tốt hơn không gồm (0,16% so với 0,21% khi xét thô) |
| Ngày khối ngoại thiếu hoặc không đủ | 16 ngày trong lịch sử (5 ngày bằng 0 hoàn toàn: 29/12/2023, 07/02/2024, 30/08/2024, 31/12/2024, 24/01/2025; các ngày còn lại chỉ có 79–119 mã hoạt động thay vì khoảng 300) |
| Ngày thiếu hẳn tự doanh sau 17/05/2022 | 19 ngày |
| Hai nguồn lịch giao dịch lệch nhau | 2 ngày (VN-Index CafeF thiếu) |
| VN-Index CafeF ngày 08/06/2026 | Dòng nguồn sai (giá cao nhất thấp hơn giá thấp nhất); đã sửa về biên của 4 giá và gắn `is_price_repaired` |

## 11. Thông tin công ty và ngành (sau khi Vietcap iQ tải xong)

- 1.519/1.519 cổ phiếu đang niêm yết có ICB cấp 4, vốn hóa và số cổ phiếu; **mọi mã ICB cấp 4 đều có trong seed `icb.csv`** (không có mã thiếu tên). Nhóm vốn hóa: lớn 116 mã (từ 10.000 tỷ), vừa 300 mã (1.000–10.000 tỷ), nhỏ 1.103 mã.
- Số mã thanh khoản (giá trị giao dịch trung bình 60 phiên ≥ 0,5 tỷ) theo ngành ICB cấp 2; ngưỡng gộp ngành khi dự báo là 5 mã (`min_liquid_stocks_per_sector`):

| Ngành | Niêm yết | Thanh khoản ≥ 0,5 tỷ | Xử lý khi dự báo (N8) |
|-------|----------|----------------------|------------------------|
| Viễn thông | 8 | 2 | Gộp |
| Công nghệ thông tin | 28 | 4 | Gộp |
| Bảo hiểm | 13 | 5 | Giữ (đúng ngưỡng) |
| Du lịch và giải trí | 46 | 6 | Giữ |
| Các ngành còn lại | | từ 7 trở lên | Giữ |

Việc gộp thực hiện ở N8 bằng cách đổi `dim_sector.analysis_group`; dữ liệu và dashboard vẫn giữ nguyên ngành cấp 2.
