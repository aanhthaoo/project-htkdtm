# Định nghĩa KPI (TV3)

Tài liệu chốt định nghĩa các KPI dùng trên 6 dashboard Superset và trang Tổng quan, Phân tích ngành. Mọi KPI truy được về dataset và metric khai báo trong `src/superset/spec.py` (danh sách chi tiết: `docs/superset_dataset_metric.md`), SQL tạo dataset nằm ở `src/dbt_dw/models/superset/`.

## Quy ước chung

- **Đơn vị:** giá trị tiền tính bằng **tỷ đồng**; giá cổ phiếu tính bằng **nghìn đồng**; tỷ lệ tính bằng **%** (riêng `accuracy` từ 0 đến 1).
- **Nhóm nhà đầu tư (`investor_type`):** `FOREIGN` (khối ngoại), `PROP` (tự doanh), `OTHER_DOMESTIC` (trong nước khác, phần dẫn xuất).
- **Ngày:** dòng tiền tính theo ngày giao dịch (`trade_date`); tuần bắt đầu thứ Hai (`week_start_date`); tin tức tính theo phiên (`session_date`), bài đăng sau 15h tính vào phiên kế tiếp.
- **Ngành:** ICB cấp 2 (`icb_l2_code`, `icb_l2_name_vi`).
- **Màu:** xanh là mua ròng (giá trị dương), đỏ là bán ròng (giá trị âm), thống nhất trên cả 6 dashboard.
- **Phiên gần nhất:** ngày `trade_date` lớn nhất có dữ liệu dòng tiền.

## Bảng KPI

| # | KPI | Công thức | Đơn vị | Dataset và metric nguồn | Hạn chế khi đọc |
|---|-----|-----------|--------|-------------------------|-----------------|
| 1 | Khối ngoại mua/bán ròng phiên gần nhất | Giá trị mua − giá trị bán của khối ngoại trong phiên gần nhất | tỷ đồng | `ds_market_flow_series.net_value_bn`, lọc `investor_type = 'FOREIGN'`, ngày lớn nhất | 16 ngày khối ngoại thiếu hoặc không đủ dữ liệu đã bị loại (xem `bao_cao_nguon.md`), nên "phiên gần nhất" có thể không phải phiên giao dịch gần nhất của thị trường |
| 2 | Tự doanh mua/bán ròng | Giá trị mua − giá trị bán của tự doanh trong kỳ | tỷ đồng | `ds_market_flow_series.net_value_bn` (hoặc `ds_stock_daily.prop_net_bn`), lọc `investor_type = 'PROP'` | Chỉ có dữ liệu từ 17/05/2022; trước ngày này giá trị trống, không phải bằng 0 |
| 3 | Trong nước khác mua/bán ròng | Phần dẫn xuất từ tổng giao dịch trừ khối ngoại và tự doanh (cách tính: `docs/thiet_ke_kho.md`) | tỷ đồng | `ds_market_flow_series.net_value_bn` (hoặc `ds_stock_daily.other_net_bn`), lọc `investor_type = 'OTHER_DOMESTIC'` | Là số suy ra, không phải số công bố; trước 17/05/2022 nhóm này gồm cả tự doanh, nên không so sánh trực tiếp hai giai đoạn |
| 4 | Lũy kế mua/bán ròng | Tổng cộng dồn giá trị ròng từ đầu kỳ dữ liệu đến ngày đang xét | tỷ đồng | `ds_market_flow_series.cum_net_value_bn` | Chỉ đúng khi nhóm theo ngày × `investor_type`; mốc bắt đầu là đầu kỳ dữ liệu, không phải đầu năm |
| 5 | Ròng cuốn chiếu 20 phiên | Tổng giá trị ròng của 20 phiên gần nhất tính đến ngày đang xét | tỷ đồng | `ds_market_flow_series.net_value_20d_bn` | Cùng điều kiện nhóm như KPI 4; các ngày bị loại (khoảng trống) làm cửa sổ 20 phiên trải dài hơn 20 ngày giao dịch thực |
| 6 | Giá trị giao dịch thị trường | Tổng giá trị giao dịch (khớp lệnh + thỏa thuận) của các mã trong ngày | tỷ đồng | `ds_stock_daily.total_value_bn` (tổng theo `trade_date`) | Bao gồm cả giao dịch thỏa thuận, nên có thể lệch với số "khớp lệnh" công bố trên báo |
| 7 | VN-Index đóng cửa | Giá trị đóng cửa của chỉ số VN-Index trong phiên | điểm | `ds_market_flow_series.vnindex_close` | Dùng để đặt cạnh dòng tiền, không cộng dồn hay lấy tổng |
| 8 | Tổng giao dịch theo nhóm nhà đầu tư | Giá trị mua + giá trị bán | tỷ đồng | `ds_flow_daily.turnover_bn` | Chỉ tính cổ phiếu (không gồm ETF, chứng quyền); khi lọc nhiều nhóm NĐT, tổng có thể đếm hai lần cùng một giao dịch (bên mua và bên bán) |
| 9 | Tỷ lệ ròng trên giao dịch | (Mua − bán) / (mua + bán) × 100 | % | `ds_flow_daily.net_ratio_pct` | Phải tính lại trên tổng của nhóm, không lấy trung bình các tỷ lệ; giá trị lớn trên ngành hoặc mã thanh khoản thấp dễ gây hiểu nhầm |
| 10 | Giá trị ròng ngành theo tuần | Mua − bán của các mã thuộc ngành trong tuần | tỷ đồng | `ds_sector_flow_weekly.net_value_bn` | Ngành ICB cấp 2; mã chưa có phân ngành không được tính |
| 11 | Tỷ trọng giao dịch của ngành | Giao dịch (mua + bán) của ngành / giao dịch toàn thị trường cùng tuần, cùng nhóm NĐT × 100 | % | `ds_sector_flow_weekly.turnover_share_pct` | Chỉ đúng khi lọc **một** `investor_type` và nhóm theo ngành × tuần (tổng các ngành = 100%) |
| 12 | Top mã gom/xả | Xếp hạng mã theo giá trị ròng trong kỳ; gom là giá trị ròng dương lớn nhất, xả là âm lớn nhất | tỷ đồng | `ds_stock_flow_daily.net_value_bn` (nhóm theo `symbol`) | Nên lọc một nhóm NĐT; mã thanh khoản lớn tự nhiên chiếm top, nên đọc kèm KPI 9 |
| 13 | Số phiên mua ròng của mã | Số phiên mã có giá trị ròng dương trong kỳ | phiên | `ds_stock_flow_daily.n_net_buy_days` | Không phản ánh độ lớn của dòng tiền; đọc kèm KPI 12 |
| 14 | Số bài liên quan chứng khoán | Số bài viết (đã loại trùng) được đánh dấu liên quan chứng khoán trong phiên | bài | `ds_news_article.n_market_articles` | Bài đăng sau 15h tính vào phiên kế tiếp; bài chưa gán được phiên đã bị loại |
| 15 | Điểm cảm xúc trung bình | Trung bình của P(tích cực) − P(tiêu cực) trên các bài | điểm, từ −1 đến 1 | `ds_news_sentiment.avg_sentiment` | Độ chính xác mô hình khoảng 64% (352 bài kiểm tra, `ml_ket_qua.md`); chỉ đọc trên nhiều bài, không suy luận từ một bài |
| 16 | Tỷ lệ tin tích cực / tiêu cực | Số bài tích cực (tiêu cực) / tổng số bài × 100 | % | `ds_news_sentiment.pct_positive`, `ds_news_sentiment.pct_negative` | Cùng hạn chế của KPI 15; xem cảm xúc ngành thì lọc `entity_type = 'SECTOR'` hoặc nhóm theo `icb_l2_name_vi` |
| 17 | Độ chính xác dự báo dòng tiền ngành | Số dự báo đúng chiều dòng tiền khối ngoại / tổng số dự báo | 0 đến 1 | `ds_prediction.accuracy` | Xấp xỉ mô hình cơ sở "tuần sau giống tuần này" (`ml_ket_qua.md`), nên luôn hiển thị cạnh mô hình cơ sở và kèm lưu ý đầu tư |
| 18 | Xác suất dòng tiền vào trung bình | Trung bình xác suất mô hình dự báo ngành có dòng tiền khối ngoại vào | 0 đến 1 | `ds_prediction.avg_prob_inflow` | Là xác suất của mô hình, không phải khuyến nghị mua bán; chỉ lấy mô hình mới nhất |

## KPI dùng ở đâu

| Nơi hiển thị | KPI |
|--------------|-----|
| Trang Tổng quan (thẻ KPI, khách xem được) | 1, 6, 7 |
| Dashboard 1 – Tổng quan thị trường (`overview`) | 1, 4, 6, 7, 10 |
| Dashboard 2 – Luân chuyển ngành (`sector-rotation`) | 9, 10, 11 |
| Dashboard 3 – Nhà đầu tư (`investors`) | 1, 2, 3, 4, 5, 8 |
| Dashboard 4 – Dòng tiền và tâm lý (`flow-sentiment`) | 10, 12, 14, 15, 16 |
| Dashboard 5 – Vĩ mô và khối ngoại (`macro`) | 1, 5 (cùng các chuỗi `ds_macro_daily`) |
| Dashboard 6 – Dự báo và khuyến nghị (`forecast`) | 17, 18 |
| Trang Phân tích ngành | 10, 12, 15 |

## Kiểm tra

Mọi metric ở trên đã có trong `spec.py` và được kiểm tra khớp SQL gốc bằng `pytest -m smoke tests/smoke/test_superset.py`. KPI nào cần metric mới thì thêm vào `spec.py`, bổ sung test, rồi cập nhật bảng này.
