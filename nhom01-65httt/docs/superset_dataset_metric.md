# Dataset và metric Superset dùng chung (cho TV3 dựng dashboard)

Superset: http://localhost:8088 (tài khoản `SUPERSET_ADMIN_*` trong `.env`). Kết nối cơ sở dữ liệu tên **BI_DW**, đọc schema `dw` bằng tài khoản chỉ đọc `bi_readonly`. Mọi dataset đã được tạo sẵn kèm metric; **không tạo lại dataset hoặc metric trùng tên**, chỉ dùng và tạo biểu đồ trên chúng.

Nguồn duy nhất của định nghĩa: `src/superset/spec.py`. Cấu hình lại hoặc cập nhật metric: sửa `spec.py` rồi chạy `python src/superset/provision.py` (chạy lại nhiều lần không nhân đôi). Câu SQL tạo từng dataset nằm ở `src/dbt_dw/models/superset/`. Mỗi dataset đã có một biểu đồ thử tên bắt đầu bằng `[Thử]` làm mẫu cách dùng.

Đơn vị: giá trị tiền là **tỷ đồng**; giá cổ phiếu là **nghìn đồng**. Nhóm nhà đầu tư (`investor_type`): `FOREIGN` (khối ngoại), `PROP` (tự doanh), `OTHER_DOMESTIC` (trong nước khác, suy ra). Nhóm vốn hóa (`cap_group`): `large` (từ 10.000 tỷ), `mid` (1.000–10.000 tỷ), `small`, `unknown` (chưa có dữ liệu vốn hóa). Sàn (`exchange`): `HOSE`, `HNX`, `UPCOM`. Ngành là ICB cấp 2 (`icb_l2_code`, `icb_l2_name_vi`).

## Bộ lọc dùng chung

Cả 4 dataset dòng tiền (`ds_flow_daily`, `ds_sector_flow_weekly`, `ds_stock_flow_daily`, `ds_market_flow_series`) có cùng tên cột cho bộ lọc, nên dùng được bộ lọc chéo trên dashboard:

| Bộ lọc | Cột | Có ở dataset |
|--------|-----|--------------|
| Thời gian | `trade_date` (hoặc `week_start_date`, `session_date` với tin) | tất cả |
| Sàn | `exchange` | `ds_flow_daily`, `ds_stock_flow_daily`, `ds_stock_daily`, `ds_news_stock_daily` |
| Ngành | `icb_l2_code`, `icb_l2_name_vi` | `ds_flow_daily`, `ds_sector_flow_weekly`, `ds_stock_flow_daily`, `ds_stock_daily`, `ds_news_stock_daily` |
| Nhóm nhà đầu tư | `investor_type` | `ds_flow_daily`, `ds_sector_flow_weekly`, `ds_stock_flow_daily`, `ds_market_flow_series` |
| Nhóm vốn hóa | `cap_group` | `ds_flow_daily`, `ds_stock_flow_daily`, `ds_stock_daily` |

## Dataset và metric

### ds_flow_daily: dòng tiền ngày × ngành × sàn × nhóm vốn hóa × nhóm NĐT (chỉ cổ phiếu)
Dùng cho: dòng tiền theo nhóm nhà đầu tư, so sánh sàn, nhóm vốn hóa, bộ lọc chung. Cột thời gian: `trade_date`, `week_start_date`, `month_start_date`, `year`.

| Metric | Ý nghĩa |
|--------|---------|
| `net_value_bn` | Giá trị ròng = mua − bán |
| `buy_value_bn`, `sell_value_bn` | Giá trị mua, bán |
| `turnover_bn` | Mua + bán |
| `net_ratio_pct` | Mua ròng chia (mua + bán), % |
| `n_trading_days` | Số phiên có dòng tiền |

### ds_sector_flow_weekly: dòng tiền ngành × tuần × nhóm NĐT (luân chuyển ngành)
Cột thời gian: `week_start_date` (thứ Hai). Có sẵn tỷ trọng.

| Metric | Ý nghĩa |
|--------|---------|
| `net_value_bn` | Giá trị ròng của ngành trong tuần |
| `turnover_bn` | Mua + bán của ngành |
| `turnover_share_pct` | Tỷ trọng giao dịch của ngành so với toàn thị trường cùng tuần, cùng nhóm NĐT (tổng các ngành = 100%). **Chỉ đúng khi lọc một `investor_type` và nhóm theo ngành × tuần** |

### ds_market_flow_series: chuỗi mua/bán ròng toàn thị trường × ngày × nhóm NĐT
Dùng cho biểu đồ chuỗi thời gian, lũy kế, so với VN-Index.

| Metric | Ý nghĩa |
|--------|---------|
| `net_value_bn` | Ròng trong ngày |
| `cum_net_value_bn` | Lũy kế ròng từ đầu kỳ dữ liệu. Dùng khi nhóm theo ngày × `investor_type` |
| `net_value_20d_bn` | Ròng cuốn chiếu 20 phiên. Cùng điều kiện như trên |
| `vnindex_close` | VN-Index đóng cửa |

### ds_stock_flow_daily: dòng tiền mã × ngày × nhóm NĐT
Dùng cho top mã gom/xả, drill xuống từng mã. Cột: `symbol`, `name_vi`, `is_vn30`.

| Metric | Ý nghĩa |
|--------|---------|
| `net_value_bn`, `buy_value_bn`, `sell_value_bn` | Giá trị ròng, mua, bán |
| `net_volume` | Khối lượng ròng (cổ phiếu) |
| `n_net_buy_days` | Số phiên mua ròng |

### ds_stock_daily: giá và dòng tiền mã × ngày
Mỗi mã mỗi ngày giao dịch một dòng; khối ngoại, tự doanh, trong nước khác là cột riêng.

| Metric | Ý nghĩa |
|--------|---------|
| `close_price` | Giá đóng cửa (nghìn đồng). Dùng khi lọc một mã |
| `total_value_bn` | Giá trị giao dịch (khớp lệnh + thỏa thuận) |
| `foreign_net_bn` | Khối ngoại ròng |
| `prop_net_bn` | Tự doanh ròng (chỉ có từ 17/05/2022) |
| `other_net_bn` | Trong nước khác ròng (suy ra, xem `thiet_ke_kho.md`) |

Cột khác: `pct_change`, `adj_close_price`, `matched_volume`, `foreign_buy_bn`, `foreign_sell_bn`.

### ds_macro_daily: vĩ mô và quốc tế × ngày
7 chuỗi: USD/VND, DXY, S&P 500, WTI, Brent, vàng, lợi suất Mỹ 10 năm. Lọc theo `indicator_code`.

| Metric | Ý nghĩa |
|--------|---------|
| `value` | Giá trị. Dùng khi lọc một chỉ số |
| `pct_change_prev` | Thay đổi so với kỳ trước (%) |

### ds_news_article: bài viết theo phiên giao dịch
Đã loại bài trùng và bài chưa gán được phiên. Bài đăng sau 15h tính vào phiên kế tiếp. Cột: `session_date`, `publisher`, `source_type` (`BACKFILL`, `CRAWL`, `RSS`), `category`, `title`, `url`, `is_market_related`, `relevance_reason`, `n_stock_mentions`.

| Metric | Ý nghĩa |
|--------|---------|
| `n_articles` | Số bài |
| `n_market_articles` | Số bài liên quan chứng khoán |
| `n_articles_with_stock` | Số bài nhắc ít nhất một mã |

### ds_news_stock_daily: bài liên quan nhắc từng mã
Mỗi bài × mã một dòng.

| Metric | Ý nghĩa |
|--------|---------|
| `n_articles` | Số bài (đếm riêng từng bài) nhắc mã |
| `n_title_articles` | Số bài nhắc mã ngay ở tiêu đề |

### ds_news_sentiment: cảm xúc tin tức theo phiên
Mỗi bài × mã hoặc ngành được nhắc một dòng; cảm xúc ở mức bài (mọi mã/ngành của cùng một bài có cùng điểm). Điểm = P(tích cực) − P(tiêu cực) trong [−1, 1]. Cột: `session_date`, `week_start_date`, `entity_type` (`STOCK`/`SECTOR`), `symbol`, `icb_l2_code`, `icb_l2_name_vi`, `publisher`, `sentiment_label` (`negative`/`neutral`/`positive`), `sentiment_score`, `confidence`. Để xem cảm xúc ngành, lọc `entity_type = 'SECTOR'` hoặc nhóm theo `icb_l2_name_vi` (gồm cả tin nhắc mã thuộc ngành).

| Metric | Ý nghĩa |
|--------|---------|
| `n_articles` | Số bài (đếm riêng từng bài) |
| `avg_sentiment` | Điểm cảm xúc trung bình |
| `pct_positive` | Tỷ lệ bài tích cực (%) |
| `pct_negative` | Tỷ lệ bài tiêu cực (%) |

Độ chính xác mô hình khoảng 64% trên 352 bài kiểm tra (xem `ml_ket_qua.md`); dùng điểm trung bình trên nhiều bài, đừng suy luận từ một bài.

### ds_prediction: dự báo dòng tiền ngành
Dự báo chiều dòng tiền khối ngoại theo ngành ICB cấp 2 × tuần mục tiêu kèm giá trị thực tế; chỉ mô hình dự báo mới nhất, dự báo ngoài mẫu walk-forward 2023–2026. Cột: `target_week_start`, `icb_l2_code`, `icb_l2_name_vi`, `predicted_class`, `prob_inflow`, `predicted_net_value_bn`, `actual_class`, `actual_net_value_bn`, `hit`.

| Metric | Ý nghĩa |
|--------|---------|
| `accuracy` | Tỷ lệ dự báo đúng chiều (0 đến 1) |
| `n_predictions` | Số dự báo |
| `avg_prob_inflow` | Xác suất dòng tiền vào trung bình |
| `predicted_net_bn`, `actual_net_bn` | Ròng dự báo và thực tế (tỷ đồng) |

**Khi trình bày:** độ chính xác xấp xỉ mô hình cơ sở "tuần sau giống tuần này" (xem `ml_ket_qua.md`); nên hiển thị lưu ý đầu tư.

## Lưu ý khi dựng biểu đồ

- Dữ liệu dòng tiền dùng **ngày giao dịch**; các ngày khối ngoại thiếu hoặc không đủ (16 ngày, xem `bao_cao_nguon.md`) đã bị loại khỏi dòng tiền, nên chuỗi có thể có khoảng trống nhỏ.
- Dữ liệu được làm mới khi chạy `python src/dbt_dw/run.py run`. Các dataset dạng bảng tổng hợp (`ds_flow_daily`, `ds_market_flow_series`, `ds_stock_daily`) cần dbt chạy lại mới có số mới; Superset tự bỏ qua bộ nhớ đệm khi bấm "Làm mới".
- Chỉ dùng cột và metric đã liệt kê. Nếu cần metric mới dùng chung, thêm vào `spec.py` để cả nhóm cùng dùng và được kiểm thử.
- Kiểm thử: `pytest -m smoke tests/smoke/test_superset.py` so từng metric với truy vấn SQL gốc trên bảng fact.
