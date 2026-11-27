# Mô hình học máy và khuyến nghị: kết quả và giới hạn (N8, N9)

Trạng thái: **ba mô hình (cảm xúc, phân cụm, dự báo) và quy tắc khuyến nghị đã xong**, đã chạy lần cải thiện thứ hai (phiên bản 0.2). Mã: `src/ml/`. Kết quả ghi vào `dw.dim_model` (chỉ số), `dw.fact_news_sentiment`, `dw.stock_cluster` (và nhãn trong `dw.dim_stock`), `dw.fact_prediction`, `dw.fact_recommendation`. Mỗi chỉ số trong tài liệu truy được về `dim_model.metrics` hoặc về tệp trong `docs/ml_thi_nghiem/`.

```bash
cd src
pip install -r ml/requirements.txt               # torch bản CPU: xem chú thích trong tệp
python -m ml.sentiment --embed-only              # (một lần, ~85 phút CPU) embedding mọi bài, lưu data/ml_cache; lần sau chỉ bài mới
python -m ml.sentiment [--dry-run]               # cảm xúc tin tức -> dw.fact_news_sentiment (+ lưu mô hình cho API)
python -m ml.clustering [--dry-run]              # phân cụm cổ phiếu -> dw.stock_cluster
python -m ml.forecast [--dry-run]                # dự báo ngành x tuần -> dw.fact_prediction
python -m ml.recommend [--dry-run]               # khuyến nghị + backtest -> dw.fact_recommendation
python dbt_dw/run.py run --select "dim_stock+"   # đưa nhãn cụm vào dim_stock; PHẢI có dấu +
python -m ml.sentiment_validity                  # kiểm chứng điểm cảm xúc với lợi suất thật (chỉ đọc)
python -m ml.insights                            # số liệu cho docs/insight_nhap.md (chỉ đọc)
```
Thứ tự: cảm xúc, phân cụm, dự báo (dùng đặc trưng cảm xúc), khuyến nghị (dùng dự báo và cảm xúc).
**Cảnh báo dbt:** không chạy `dbt run --select dim_stock` (thiếu dấu `+`): PostgreSQL xóa các view phụ thuộc (`ds_*`, `mv_*`).

**Tóm tắt trung thực (đọc trước):**
- Phân cụm: cụm có giá trị mô tả và bền theo thời gian vừa phải; hành vi mua/bán ròng của một mã **không** bền (không nên dùng để mô tả mã).
- Dự báo dòng tiền ngành: **chưa vượt có ý nghĩa thống kê** mô hình cơ sở "tuần sau giống tuần này"; vượt rõ ở dự báo **giá trị** ròng. Đặc trưng lịch, room ngoại, giá, vĩ mô, cảm xúc đều không cải thiện.
- Cảm xúc: khớp nhãn tốt hơn (từ 64% lên 70%), nhưng **liên hệ với lợi suất thật không tăng**.
- Khuyến nghị: phân biệt được chiều dòng tiền khối ngoại tuần sau, **không** tạo lợi suất ngành vượt mua đều sau phí.

---

## 1. Phân cụm hành vi dòng tiền của cổ phiếu (N8b, phiên bản 0.2)

**Dữ liệu và đặc trưng.** Giai đoạn 17/05/2022 đến nay (có khối ngoại và tự doanh theo mã). 10 đặc trưng ứng viên theo từng mã (chuẩn hóa theo giá trị giao dịch của mã): tỷ lệ mua ròng và tỷ trọng khối ngoại, tỷ lệ phiên mua ròng, độ biến động dòng tiền, tính xu hướng theo tuần, tỷ lệ phiên khối ngoại có giao dịch, tỷ lệ ròng và tỷ trọng tự doanh, biến động giá, thanh khoản. Tỷ lệ theo ngày cắt trong [-1, 1]; đặc trưng cắt đuôi 1%-99% rồi chuẩn hóa.

**Cải tiến 1: bỏ đặc trưng không bền.** Tính mỗi đặc trưng ở nửa đầu và nửa sau giai đoạn rồi lấy tương quan giữa hai nửa; đặc trưng có tương quan dưới 0,2 mô tả nhiễu nên bị loại. Kết quả trên toàn giai đoạn: loại **tỷ lệ mua ròng khối ngoại** và **tỷ lệ ròng tự doanh**. Nghĩa là một mã đang mua ròng ở nửa đầu không giữ xu hướng đó ở nửa sau, trong khi thanh khoản, mức hoạt động của khối ngoại và biến động dòng tiền thì bền (tương quan 0,7 đến 0,94).

**Cải tiến 2: chọn K theo độ bền theo thời gian.** Phân cụm nửa đầu, gán nửa sau bằng tâm cũ, đo ARI giữa nhãn hai nửa (mã có giữ cụm không), chọn K có ARI cao nhất trong các K hợp lệ (cụm nhỏ nhất ≥ 1%, ổn định giữa các seed ARI ≥ 0,6). ARI theo K: K=3 0,38; **K=4 0,45**; K=5 0,32; K=6 0,23. Thay cho chọn K theo Silhouette (cũ: K=6).

**Cải tiến 3: mở rộng phạm vi bằng nhóm phụ.** Trước đây chỉ 387 mã có cụm; 1.451 mã nhận nhãn quy tắc. Nay 951 mã ít khối ngoại hoặc thanh khoản thấp (đủ ≥ 200 phiên) được phân cụm riêng bằng đặc trưng không cần khối ngoại: biến động giá, thanh khoản, beta so với VN-Index, tác động giá (Amihud), tự tương quan lợi suất, tỷ lệ phiên tăng, tương quan |lợi suất| với khối lượng, độ lệch. Nhãn nhóm phụ có tiền tố `phu_`.

**Kết quả hiện tại.** Tổng **1.338/1.838 mã (73%)** có cụm học được (trước: 387); còn lại 499 mã `chua_du_du_lieu` (niêm yết mới hoặc dưới 200 phiên) và 1 mã `thanh_khoan_thap`.

| Cụm chính (K=4, Silhouette 0,245; tên theo hai đặc trưng nổi bật nhất) | Số mã |
|------|------|
| `ngoai_giao_dich_deu+thanh_khoan_cao` | 148 |
| `ngoai_giao_dich_thua+dong_tien_on_dinh` | 131 |
| `dong_tien_bat_on+ngoai_mua_deu` | 69 |
| `tu_doanh_chu_dao+thanh_khoan_cao` | 39 |

| Nhóm phụ (K=3, Silhouette 0,197) | Số mã |
|------|------|
| `phu_gia_hoi_quy+gia_it_bien_dong` (ổn định, giá hồi quy) | 393 |
| `phu_gia_bien_dong_manh+tac_dong_gia_lon` (biến động mạnh, kém thanh khoản) | 323 |
| `phu_tac_dong_gia_nho+bien_dong_theo_khoi_luong` (thanh khoản khá, nhạy thị trường) | 235 |

Silhouette thấp (0,2 đến 0,25): hành vi dòng tiền là dải liên tục hơn là nhóm tách biệt; nhãn cụm chỉ để mô tả xu hướng, không phải phân loại cứng. Tên cụm được test tự động khớp đặc trưng trung bình thật.

**Kiểm chứng theo thời gian** (`python -m ml.clustering_experiments`, `docs/ml_thi_nghiem/phan_cum.json`). Phân cụm 05/2022-06/2024, gán 07/2024-nay bằng tâm cũ, trên 313 mã có đủ dữ liệu ở cả hai giai đoạn. Đặc trưng được chọn chỉ bằng giai đoạn thiết kế (trước 07/2024).

| | Mã giữ cụm | Mức ngẫu nhiên | ARI | R² đặc trưng giai đoạn sau giải thích bởi cụm |
|-|-----------|---------------|-----|---------------|
| Cấu hình cũ (10 đặc trưng, K=6) | 68% | 30% | 0,41 | 0,25 |
| Bỏ đặc trưng không bền, K=5 | 71% | 31% | 0,44 | 0,28 |
| Bỏ đặc trưng không bền, K=6 | 64% | 23% | 0,33 | 0,29 |

Mã giữ cụm cao gấp 2 đến 3 lần ngẫu nhiên; cụm giải thích khoảng 0,25 đến 0,29 phương sai hành vi giai đoạn sau (dùng chính giá trị đặc trưng cũ để dự đoán là 0,31 đến 0,34), nên cụm giữ phần lớn thông tin bền. Cấu hình sản xuất (K=4) chọn theo nửa đầu và nửa sau của toàn giai đoạn nên số của nó (giữ cụm 77%, ARI 0,47) không phải kiểm chứng độc lập. Theo từng năm, **73% đến 78%** số mã giữ cụm năm sau (`yearly` trong tệp thí nghiệm).

**Đã thử và không dùng.** Gaussian Mixture (độ thuộc mềm): BIC chọn K=7, mỗi mã thuộc cụm rất rõ (độ thuộc trung bình 0,98) nhưng nhãn lệch K-Means (ARI 0,31), Silhouette cứng chỉ 0,03. HDBSCAN: 90% mã là nhiễu ở cỡ cụm tối thiểu 8, không có cụm nào ở cỡ 15 và 25, tức không có nhóm mật độ tự nhiên, củng cố nhận định hành vi là dải liên tục.

**Giới hạn.** Đặc trưng chỉ tính từ 17/05/2022 (mốc có tự doanh theo mã); khối ngoại phụ thuộc chế độ thị trường (đặc trưng mua/bán ròng đổi dấu theo giai đoạn); nhóm phụ có Silhouette thấp hơn; nhãn cụm không mang ý nghĩa khuyến nghị đầu tư.

## 2. Dự báo chiều dòng tiền khối ngoại của ngành (N8c, phiên bản 0.2)

**Bài toán (không đổi so với đề cương).** Với mỗi ngành ICB cấp 2 (19 ngành) và mỗi tuần t: khối ngoại sẽ mua ròng hay bán ròng ngành đó trong tuần t+1 (bài toán chính, phân lớp) và giá trị ròng (tỷ đồng, bài toán phụ, hồi quy). XGBoost, huấn luyện lại mỗi quý theo walk-forward mở rộng cửa sổ, **3.819 dự báo ngoài mẫu** (201 tuần × 19 ngành, từ 02/01/2023).

**Chống rò rỉ.** Đặc trưng tuần t chỉ dùng dữ liệu đến hết tuần t (kể cả đại lượng chuẩn hóa cuốn chiếu); huấn luyện cho khối bắt đầu ở T0 chỉ dùng dòng có tuần ≤ T0 − 1 tuần. Test tự động: thay toàn bộ dữ liệu sau tuần t bằng nhiễu thì đặc trưng các tuần ≤ t không đổi (kể cả đặc trưng room và lịch). Dự báo được ghi với `made_at` trước ngày bắt đầu tuần mục tiêu và dbt test kiểm tra điều đó.

**Chọn cấu hình theo kỷ luật.** Chọn chỉ bằng năm 2023 (tập chọn), báo cáo 2024-2026 (tập báo cáo). Quy tắc đặt trước: giữ cấu hình gọn nhất `dòng tiền + so sánh chéo ngành` (16 đặc trưng), chỉ thêm nhóm mới nếu cải thiện accuracy tập chọn ≥ 1 điểm **và** AUC ≥ 0,005. Không nhóm nào đạt.

**Đặc trưng mới thử ở lần này.** *Lịch* (8 đặc trưng, biết trước nên không rò rỉ): tháng, tuần trong tháng, tuần đáo hạn phái sinh (thứ Năm thứ ba), kỳ xem xét rổ VN30 (tháng 1/4/7/10), kỳ cơ cấu quỹ ETF (tháng 3/6/9/12), mùa nộp báo cáo, ngày làm việc cuối tháng, khoảng cách tới Tết. *Room ngoại* (4 đặc trưng, từ `raw.vnd_foreigns`, phủ trên 99%): tỷ lệ room đã dùng của ngành (trọng số giá trị giao dịch), thay đổi 1 và 4 tuần, tỷ trọng giao dịch của mã sát room (≥ 90%).

| Cấu hình (XGBoost nếu không ghi) | Tập chọn 2023: acc / AUC | Tập báo cáo 2024+: acc / AUC |
|---|---|---|
| Cơ sở "giống tuần này" | 64,3% / - | 62,0% / - |
| Chỉ dòng tiền | 62,9% / 0,678 | 62,7% / 0,655 |
| **Dòng tiền + so sánh chéo (chọn)** | 64,1% / 0,671 | 63,1% / 0,653 |
| + giá ngành | 64,1% / 0,671 | 62,6% / 0,656 |
| + giá + thị trường | 65,1% / 0,686 | 62,4% / 0,647 |
| + giá + thị trường + vĩ mô | 63,1% / 0,694 | 62,1% / 0,644 |
| + tự doanh | 62,0% / 0,675 | 63,2% / 0,657 |
| + **lịch** | 63,7% / 0,669 | 63,1% / 0,650 |
| + **room ngoại** | 64,0% / 0,671 | 63,2% / 0,656 |
| + lịch + room | 63,2% / 0,668 | 62,8% / 0,650 |
| + cảm xúc (mô hình cảm xúc mới) | 62,3% / 0,664 | 63,2% / 0,658 |
| Hồi quy logistic, cùng đặc trưng | 63,8% / 0,686 | 62,9% / 0,656 |

Mọi biến thể chênh nhau trong ±1,5 điểm, nằm trong nhiễu thống kê.

**Kết quả tổng (3.819 dự báo ngoài mẫu).** XGBoost: accuracy **63,4%**, F1 0,614, AUC 0,662. Cơ sở "giống tuần này": 62,6%. Cơ sở "lớp phổ biến": 57,6%. Hồi quy giá trị ròng: sai số tuyệt đối 200 tỷ so với 255 tỷ (cơ sở "bằng tuần trước") và 223 tỷ ("luôn bằng 0").

**Kiểm định thống kê** (bootstrap theo tuần, 2024+, 149 tuần). Chênh lệch accuracy so với cơ sở: **+1,1 điểm, khoảng tin cậy 95% [-0,4; +2,6]**, không có ý nghĩa. Chênh lệch sai số hồi quy: **-67 tỷ, khoảng tin cậy [-85; -50]**, có ý nghĩa: mô hình dự báo **giá trị** tốt hơn rõ, dự báo **chiều** chỉ ngang cơ sở.

**Cách đọc khác của cùng dự báo (không đổi bài toán gốc).**
- *Xếp hạng ngành* (xếp 19 ngành theo giá trị ròng dự báo; API trả `rank`): Spearman 0,30 (chuẩn hóa) và 0,36 (tỷ đồng) so với cơ sở 0,28 và 0,34; trong 5 ngành xếp đầu có 37% (chuẩn hóa) hoặc 39% (tỷ đồng) thật sự nằm top 5, cơ sở 39% và 41%, ngẫu nhiên 26%. Hơn ngẫu nhiên, **không hơn** cơ sở quán tính.
- *Phần bất thường* (dòng tiền tuần sau lệch bao nhiêu so với tuần này, và đảo chiều): 37,5% số dự báo tuần sau đổi dấu so với tuần này; mô hình bắt được **23%** các lần đảo chiều với độ chính xác 53% khi cảnh báo đảo chiều (cơ sở "giống tuần này" bắt 0%). Hướng thay đổi đúng 66,9%, thấp hơn cơ sở "quay về 0" (68,8%), tức quán tính đảo chiều về trung bình cũng giải thích nhiều.
- *Backtest ngành sơ bộ* (mua đều 3 ngành có giá trị ròng chuẩn hóa dự báo cao nhất, giữ một tuần; lợi suất rổ theo trọng số giá trị tuần trước nên đầu tư được; chưa tính phí): 2024-2026 lợi suất trung bình 0,118%/tuần so với mua đều 19 ngành 0,108%, chênh +0,01 điểm/tuần, khoảng tin cậy [-0,28; +0,31]; thắng mua đều 50% số tuần. Ngành dự báo mạnh nhất và yếu nhất cách nhau 0,20 điểm/tuần. **Không có lợi suất vượt có ý nghĩa**: dự báo dòng tiền khối ngoại không đồng nghĩa dự báo giá.

**Dự báo trực tiếp (tuần kế tiếp).** Chỉ ghi khi lập **trước** khi tuần mục tiêu bắt đầu (một tuần được coi là đủ từ thứ Sáu). Lúc chạy (27/11, trước giờ đóng phiên) tuần 23/11 chưa đủ, nên chưa có dự báo cho tuần 30/11: chạy lại `python -m ml.forecast` sau 15h thứ Sáu hoặc cuối tuần (sau `python -m ingestion.cli daily` và dbt để có dữ liệu 26-27/11).

**Giới hạn.** Chưa có CPI và dòng vốn ETF (TV4 nhập ở giai đoạn 2, sẽ huấn luyện lại ở giai đoạn 3). Bài toán nhiều nhiễu: trần chính xác dường như gần 64%. Quán tính dòng tiền là nguồn thông tin chính.

## 3. Cách dùng kết quả

- `dw.fact_prediction`: khóa ngành là dòng đại diện cấp 2 `<mã>_NA` của `dim_sector`; `actual_*` có với dự báo ngoài mẫu.
- API: `GET /api/predictions` (có `rank`), `/accuracy`, `GET /api/admin/models`, `GET /api/recommendations`, nhãn cụm ở `GET /api/stocks/{symbol}`; API mô hình nội bộ mục 6.
- Khi trình bày: nêu rõ độ chính xác xấp xỉ mô hình cơ sở; mọi dự báo và khuyến nghị kèm lưu ý đầu tư.

## 4. Mô hình cảm xúc tin tức (N8a, phiên bản 0.2)

**Nhãn huấn luyện.** Do Claude gán (chưa phải nhãn chuẩn của con người), chỉ gồm mã bài và nhãn (`src/ml/labels/`):
- Đợt 1 (1.500 bài, phân tầng theo năm và nguồn): khớp 92,7% và Cohen kappa 0,887 với lượt gán lại độc lập 150 bài.
- Đợt 2 (1.500 bài): 850 bài mô hình phân vân nhất (active learning) và 650 bài ngẫu nhiên, gồm 1.200 bài trước 2025 và 300 bài từ 2025 (nhóm này chỉ dùng cho mô hình cuối, không nằm trong tập kiểm tra). Khớp 91% và kappa 0,861 với lượt gán lại độc lập 100 bài (bài phân vân 94%, bài ngẫu nhiên 88%); khi cả hai lượt đều chắc, 64/64 bài khớp.
- Tổng 2.952 bài dùng được (48 bài đợt 1 không còn trong kho sau khi siết quy tắc lọc tin). Phân bố đợt 2: trung lập 43%, tích cực 34%, tiêu cực 23%.
Tập 390 bài của TV5 (`sentiment_validation_sample.csv`, cột `label_human`) vẫn để dành làm tập kiểm tra chuẩn của con người ở giai đoạn 2.

**Đường cong học** (`docs/ml_thi_nghiem/cam_xuc_duong_cong_hoc.json`, TF-IDF, 352 bài kiểm tra): 275 nhãn 57,2%; 550 nhãn 60,1%; 825 nhãn 62,9%; 1.100 nhãn 64,2%. Còn dốc, nên bổ sung nhãn là đúng hướng.

**So biến thể** (`cam_xuc_so_sanh.json`; mỗi biến thể chọn siêu tham số bằng tập chọn 07/2023-2024, đo trên tập kiểm tra 352 bài từ 2025, huấn luyện 1.100 nhãn):

| Biến thể | Accuracy | F1 macro | Recall lớp trung lập |
|---|---|---|---|
| TF-IDF (cơ sở) | 63,9% | 0,626 | 0,40 |
| TF-IDF sau tách từ (pyvi) | 64,8% | 0,636 | 0,41 |
| TF-IDF n-gram ký tự | 63,1% | 0,622 | 0,42 |
| Embedding e5-small + hồi quy logistic | 66,2% | 0,652 | 0,43 |
| Embedding e5-base | 66,5% | 0,659 | 0,47 |
| **Kết hợp TF-IDF + e5-small** | **68,2%** | 0,673 | 0,47 |

Từng biến thể đơn lẻ chưa khác cơ sở có ý nghĩa; **kết hợp** cao hơn cơ sở +4,3 điểm, khoảng tin cậy 95% [+0,6; +8,0]. Tách từ và n-gram ký tự không giúp. Nhân xác suất lớp trung lập lên (chọn trên tập chọn) chỉ nâng nhẹ recall lớp trung lập và không nâng accuracy tập kiểm tra nên không dùng. Chọn kết hợp TF-IDF + e5-small (`multilingual-e5-small`, chạy được trên CPU) vì gọn hơn e5-base mà gần như tương đương.

**Mô hình cuối.** Hồi quy logistic cân bằng lớp trên TF-IDF 1-2 gram (C=4) và trên embedding (C=8), lấy trung bình xác suất; nhãn lưỡng lự (độ chắc chắn 1) dùng với trọng số 0,5. Huấn luyện **2.300 bài** (đến 04/12/2024), kiểm tra **352 bài** (09/01/2025 đến 23/11/2026, cố định từ đợt 1):

| | Mô hình kết hợp | Chỉ TF-IDF (cùng dữ liệu) | Đoán lớp phổ biến |
|-|-|-|-|
| Accuracy | **69,6%** | 65,9% | 36,6% |
| F1 macro | 0,689 | 0,648 | - |

Theo lớp (precision / recall): tiêu cực 0,67 / 0,74; trung lập 0,78 / **0,50**; tích cực 0,67 / 0,86. Ma trận nhầm (hàng thật, cột dự đoán; tiêu cực, trung lập, tích cực): [[70, 9, 16], [26, 65, 38], [9, 9, 110]]. Mô hình vẫn bỏ sót nhiều bài trung lập (đoán thành tích cực hoặc tiêu cực).

**Chấm toàn kho.** 130.167 bài liên quan chứng khoán không trùng; phân bố: trung lập 40,8%, tích cực 35,3%, tiêu cực 23,9%. `dw.fact_news_sentiment` có 556.377 dòng (mỗi bài × mã hoặc ngành được nhắc; điểm = P(tích cực) − P(tiêu cực) trong [-1, 1]). Khoảng 12% bài (15.435) không nhắc mã hay ngành nào nên không có dòng. Điểm ở mức bài: mọi mã/ngành của cùng một bài có cùng điểm. Bảng chỉ giữ kết quả của mô hình cảm xúc mới nhất.

**Kiểm chứng ngoài nhãn** (`python -m ml.sentiment_validity`; `docs/ml_thi_nghiem/cam_xuc_kiem_chung_*.json`). Mỗi phiên, tương quan hạng (IC) giữa điểm cảm xúc trung bình của mã và lợi suất vượt VN-Index của mã, trên 5.216 mã-phiên có tin (432 phiên có từ 5 mã trở lên):

| Lợi suất | IC trung bình mô hình cũ (t) | IC mô hình mới (t) | IC gộp mới (khoảng tin cậy 95%) |
|---|---|---|---|
| Cùng phiên | 0,102 (4,6) | 0,079 (3,6) | 0,087 [0,055; 0,119] |
| Phiên kế tiếp | 0,057 (2,6) | 0,046 (2,0) | 0,021 [-0,015; 0,057] |
| Tổng 3 phiên kế tiếp | 0,020 (0,9) | 0,007 (0,3) | 0,023 [-0,013; 0,058] |

Điểm cảm xúc có ý nghĩa thị trường cùng phiên (tin và giá phản ứng cùng lúc), yếu và không có ý nghĩa thống kê khi gộp từ phiên kế tiếp. **Mô hình mới khớp nhãn LLM tốt hơn nhưng không liên hệ với lợi suất thật tốt hơn mô hình cũ** (IC gộp cùng phiên 0,087 ở cả hai): chênh lệch nằm trong nhiễu. Vì vậy cải thiện accuracy trên nhãn chưa chứng minh cải thiện giá trị thực tế.

**Giới hạn.** Nhãn do LLM gán; tập kiểm tra 352 bài nên sai số khoảng ±5 điểm; điểm cảm xúc là ở mức bài, không phân biệt từng mã trong cùng bài; chưa tinh chỉnh mô hình ngôn ngữ tiếng Việt (PhoBERT cần GPU); độ chính xác khoảng 70% nên chỉ dùng điểm trung bình trên nhiều bài, đừng kết luận từ một bài.

## 5. Quy tắc khuyến nghị và backtest sơ bộ (N9)

**Quy tắc.** Lập cuối tuần t cho tuần t+1, chỉ dùng thông tin đến hết tuần t (`src/ml/recommend.py`, phiên bản quy tắc 1.0). Điểm tổng = dự báo + đảo chiều + cảm xúc; lệch pha nhân điểm với 0,5.

| Tín hiệu | Điều kiện | Điểm |
|---|---|---|
| Dự báo | Xác suất mua ròng lệch khỏi 0,5 từ 0,10 trở lên (đủ ±1 khi lệch 0,25) | ±1 |
| Đảo chiều dòng tiền | ≥ 4 trong 5 phiên trước cùng bán ròng (tổng âm), rồi ≥ 2 trong 3 phiên gần nhất mua ròng (tổng dương); và ngược lại | ±0,5 |
| Cảm xúc ngành chuyển hướng | Cảm xúc tuần t dương (âm) và cao hơn (thấp hơn) trung bình tối đa 4 tuần trước từ 0,10; cần ≥ 5 bài | ±0,5 |
| Lệch pha | Cảm xúc ≥ +0,15 nhưng dòng tiền chuẩn hóa ≤ -0,5, hoặc ngược lại | điểm × 0,5, gắn cảnh báo |

Hành động: điểm ≥ 0,5 tăng tỷ trọng, ≤ -0,5 giảm, còn lại giữ. Độ chắc chắn: **cao** nếu |điểm| ≥ 1,25 và không lệch pha; **trung bình** nếu ≥ 0,75; còn lại thấp. Các ngưỡng đặt trước khi xem backtest và **không tinh chỉnh theo backtest**. Phân bố trong 201 tuần: giữ 43%, giảm 33%, tăng 24%; độ chắc chắn thấp 71%, trung bình 23%, cao 6%.

**Khuyến nghị có phân biệt được chiều dòng tiền khối ngoại tuần sau không** (3.781 ngành-tuần ngoài mẫu từ 2023, tỷ lệ tuần sau khối ngoại mua ròng; mức chung 42,4%):

| Khuyến nghị | Số ngành-tuần | Tuần sau khối ngoại mua ròng |
|---|---|---|
| Tăng, độ chắc chắn cao | 69 | **69,6%** |
| Tăng, trung bình | 333 | 61,3% |
| Tăng, thấp | 504 | 54,6% |
| Giữ | 1.613 | 41,4% |
| Giảm, thấp | 553 | 38,9% |
| Giảm, trung bình | 552 | 28,1% |
| Giảm, độ chắc chắn cao | 157 | **24,2%** |

Độ chắc chắn sắp xếp đúng thứ tự. Lưu ý quan trọng: một phần sức phân biệt đến từ quán tính dòng tiền (mô hình dự báo cũng chủ yếu dựa vào quán tính và chưa vượt cơ sở có ý nghĩa), nên không khẳng định quy tắc thêm giá trị ngoài quán tính.

**Backtest** (mua theo khuyến nghị, so với mua đều 19 ngành và VN-Index; walk-forward ngoài mẫu; giữ một tuần; phí giả định 0,2% mỗi lượt mua hoặc bán; lợi suất ngành đầu tư được; 147 tuần 2024-2026). *Danh mục lệch*: trọng số đều, ×1,5 ngành tăng, ×0,5 ngành giảm. *Chỉ mua ngành tăng*: mua đều các ngành khuyến nghị tăng.

| 2024-2026 | Lợi suất tích lũy | Sharpe | Sụt giảm tối đa | Vòng quay/tuần |
|---|---|---|---|---|
| VN-Index | +40,6% | 0,78 | -14,9% | - |
| Mua đều 19 ngành | +6,8% | 0,22 | -29,5% | 0 |
| Danh mục lệch, chưa trừ phí | +7,3% | 0,23 | -26,5% | 0,35 |
| Danh mục lệch, sau phí | **-3,1%** | 0,03 | -29,5% | 0,35 |
| Chỉ mua ngành tăng, chưa trừ phí | +18,9% | 0,41 | -22,9% | 1,44 |
| Chỉ mua ngành tăng, sau phí | **-22,2%** | -0,35 | -35,7% | 1,44 |

Danh mục lệch thua mua đều 0,07 điểm/tuần sau phí (khoảng tin cậy 95% [-0,12; -0,02]), thắng mua đều 35% số tuần. Chưa trừ phí, danh mục lệch ngang mua đều; phần chênh lệch hầu hết do phí vì khuyến nghị đổi mỗi tuần. Lợi suất vượt trung bình của ngành "tăng" so với ngành "giảm" ở tuần sau không có ý nghĩa thống kê (|t| dưới 1,6).

**Nhận định trung thực.**
1. Khuyến nghị dự báo được **chiều dòng tiền khối ngoại** (đúng điều quy tắc nhắm tới) nhưng **không** chuyển thành lợi suất ngành vượt trội, nhất quán với kết quả dự báo (mục 2).
2. VN-Index vượt mọi danh mục ngành trong giai đoạn kiểm tra (+40,6% so với +6,8% của mua đều 19 ngành). Hai bên khác cấu thành: ngành là rổ trọng số theo giá trị giao dịch tuần trước, còn VN-Index trọng số theo vốn hóa; chưa phân tích nguyên nhân chênh lệch, nên chỉ nên đọc VN-Index như mốc tham chiếu.
3. Backtest chỉ ngành, chưa gồm chọn mã; chưa tính thuế chuyển nhượng; phí là giả định đơn giản; giai đoạn kiểm tra 3 năm có một xu hướng thị trường nên kết quả rất nhạy.
4. Nên trình bày khuyến nghị như **công cụ theo dõi dòng tiền**, không như tín hiệu sinh lời.

## 6. API mô hình (`/ml/*`, nội bộ, khóa dịch vụ)

- `POST /ml/predict`: dự báo của mô hình dự báo mới nhất trong `dw` cho tuần chỉ định (404 nếu không có).
- `POST /ml/cluster`: nhãn cụm từ `dw.dim_stock` (mã không có: `unknown`).
- `POST /ml/sentiment`: chấm văn bản; trả điểm thật khi tiến trình backend nạp được mô hình (`data/ml_cache/sentiment_ensemble.joblib`, tạo bởi `python -m ml.sentiment`) và có thư viện học máy; **image backend Docker hiện chưa có torch nên trả dữ liệu mẫu `stub: true`**. Phương án nếu cần trong Docker: dựng riêng dịch vụ mô hình, hoặc chạy backend ngoài Docker.

## 7. Giới hạn chung và việc còn lại

- Nhãn cảm xúc do LLM gán; cần so với nhãn chuẩn của TV5 (390 bài) ở giai đoạn 2.
- Chưa có dự báo trực tiếp cho tuần 30/11 (xem mục 2); chưa có CPI và dòng vốn ETF.
- Mô hình học máy chưa nằm trong bộ chạy ETL và n8n (chạy bằng lệnh); embedding mới cần cập nhật định kỳ (`--embed-only` chỉ tính bài mới).
- Khuyến nghị chưa chọn mã, chưa tính thuế; đưa ra như công cụ theo dõi, kèm lưu ý đầu tư.
