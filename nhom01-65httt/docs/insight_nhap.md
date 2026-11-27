# Insight nháp (giai đoạn 1, nhóm chưa chốt)

Trạng thái: **bản nháp** của TV1 để nhóm thảo luận; số liệu sẽ cập nhật ở giai đoạn 3 (có CPI, ETF, nhãn cảm xúc chuẩn). Mọi con số lấy từ `python -m ml.insights` (truy vấn `dw.ds_flow_daily`, `dw.mv_market_daily_kpi`, `dw.dim_model.metrics`), dữ liệu đến 25/11/2026; năm 2026 chưa đủ năm. Đơn vị: tỷ đồng; "nghìn tỷ" = 1.000 tỷ. Đây là mô tả dữ liệu, không phải khuyến nghị đầu tư.

## 1. Khối ngoại bán ròng ngày càng mạnh từ 2023

Mua/bán ròng cả thị trường của khối ngoại theo năm: 2022 **+26,0 nghìn tỷ**; 2023 −17,2; 2024 −78,4; **2025 −134,4**; 2026 (đến 25/11) **−127,1**. Mức bán ròng 2025 gấp khoảng 1,7 lần 2024 và gấp 7,8 lần 2023.
*Nguồn:* `ml.insights` → `foreign_net_by_year_market_bn`.
*Cách dùng:* dashboard Tổng quan thị trường (xu hướng dòng tiền theo năm); câu chuyện mở đầu báo cáo.

## 2. Dòng ra tập trung vào hai ngành: Bất động sản và Ngân hàng

Bán ròng của khối ngoại theo ngành ICB cấp 2: 2025 Bất động sản **−44,6 nghìn tỷ**, Ngân hàng **−32,3**, Dịch vụ tài chính −13,9; 2026 Bất động sản **−48,7**, Ngân hàng **−48,1**, Công nghệ thông tin −19,0. Hai ngành đầu chiếm **57%** tổng bán ròng cả thị trường năm 2025 và **76%** năm 2026.
*Nguồn:* `ml.insights` → `sector_extremes`; tỷ trọng = (BĐS + Ngân hàng) / tổng thị trường (134,4 và 127,1 nghìn tỷ; tổng các ngành khớp tổng thị trường).
*Cách dùng:* dashboard Luân chuyển ngành (xếp hạng ngành theo dòng tiền ròng); câu hỏi cho báo cáo: vì sao hai ngành vốn hóa lớn bị bán nhiều nhất.

## 3. Luân chuyển: vài ngành đổi chiều dòng tiền khối ngoại giữa các năm

Bán ròng chung nhưng có ngành được mua: **Tài nguyên cơ bản** đổi từ −5,3 nghìn tỷ (2025) sang **+7,8** (2026), thành ngành được mua ròng nhiều nhất năm 2026. **Bán lẻ** mua ròng ba năm liền (+0,8; +0,7; +3,7 nghìn tỷ), **Bảo hiểm** đổi chiều mỗi năm (−0,06 → +2,8 → −0,3 → +0,4). Năm 2023→2024, nhiều ngành đổi từ mua ròng sang bán ròng cùng lúc (Tài nguyên cơ bản từ +5,0 xuống −6,4; Dịch vụ tài chính từ +1,7 xuống −5,1; Công nghệ thông tin từ +0,2 xuống −7,0).
*Nguồn:* `ml.insights` → `sector_flips_between_years`, `sector_extremes`.
*Cách dùng:* heatmap ngành × năm (hoặc ngành × tháng); phần "luân chuyển ngành" của báo cáo.

## 4. Dòng tiền ngành có quán tính; mô hình dự báo được giá trị nhưng chưa vượt quán tính về chiều

Tuần sau cùng chiều tuần này trong **62,6%** ngành-tuần (3.819 dự báo ngoài mẫu từ 2023); mô hình XGBoost đúng **63,4%**, chênh lệch +1,1 điểm (2024+) với khoảng tin cậy 95% [-0,4; +2,6], chưa có ý nghĩa thống kê. Nhưng dự báo **giá trị** ròng giảm sai số từ 255 xuống 200 tỷ đồng (-22%), có ý nghĩa (khoảng tin cậy [-85; -50] tỷ). Thêm giá, vĩ mô, đặc trưng lịch, room ngoại hay cảm xúc không cải thiện.
*Nguồn:* `dim_model.metrics` của mô hình dự báo (`bootstrap`, `regression`, `ablation`); `docs/ml_ket_qua.md` mục 2.
*Cách dùng:* trang Dự báo và khuyến nghị (độ chính xác theo tuần so với mô hình cơ sở); thông điệp trung thực khi bảo vệ: nêu giới hạn.

## 5. Tin tức phản ánh giá cùng phiên nhưng không dự báo được giá

Mỗi phiên, xếp hạng mã theo điểm cảm xúc tin có tương quan hạng **+0,08** với lợi suất vượt VN-Index cùng phiên (gộp 0,087, khoảng tin cậy 95% [0,055; 0,119], 5.216 mã-phiên có tin). Từ phiên kế tiếp tương quan còn 0,02 và **không** khác 0 (khoảng tin cậy [-0,015; 0,057]); tổng 3 phiên kế tiếp 0,02, không có ý nghĩa. Nghĩa là tin cậy được dùng để *giải thích* biến động cùng ngày hơn là để dự báo.
*Nguồn:* `python -m ml.sentiment_validity` (`docs/ml_thi_nghiem/cam_xuc_kiem_chung_mo_hinh_moi.json`).
*Cách dùng:* dashboard Dòng tiền và tâm lý (tin và giá cùng phiên); lưu ý khi dùng điểm cảm xúc làm tín hiệu.

## Bổ sung: khuyến nghị theo dõi dòng tiền

Khuyến nghị "tăng, độ chắc chắn cao" được tuần sau khối ngoại mua ròng trong **69,6%** trường hợp (69 ngành-tuần) so với **24,2%** với "giảm, độ chắc chắn cao" (157 ngành-tuần) và 42,4% mức chung, nhưng không tạo lợi suất ngành vượt mua đều sau phí (danh mục lệch −3,1% so với +6,8% của mua đều, 2024-2026). Chi tiết ở `docs/ml_ket_qua.md` mục 5.

## Việc để giai đoạn 3

- Cập nhật số khi có CPI, dòng vốn ETF và nhãn cảm xúc chuẩn của TV5.
- Kiểm tra insight 2 và 3 với dữ liệu tháng (không chỉ năm) và với nhóm vốn hóa; chưa phân tích nguyên nhân (giá, định giá, room, sự kiện).
- Insight chưa chốt: nhóm cần chọn 3 đến 5 phát hiện đưa vào báo cáo và slide.
