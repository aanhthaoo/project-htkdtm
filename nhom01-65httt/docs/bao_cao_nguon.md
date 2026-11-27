# Báo cáo kiểm chứng nguồn dữ liệu (N2)

Ngày kiểm chứng: 24–25/11/2026. Script thăm dò: [src/ingestion/probes/](../src/ingestion/probes/). Phản hồi mẫu: [tests/fixtures/](../tests/fixtures/). Đánh giá tổng hợp theo đề cương: [danh_gia_nguon_du_lieu.md](danh_gia_nguon_du_lieu.md). Thiết kế kho: [thiet_ke_kho.md](thiet_ke_kho.md).

Cách đọc: "Đã xác nhận" là đã gọi thật và thấy dữ liệu. "Chưa xác nhận" ghi rõ thiếu gì.

> **Cập nhật so với bản đầu:** bản đầu kết luận dữ liệu khối ngoại chỉ đủ từ 2022, tự doanh theo mã rất ngắn, ngành chỉ có cấp 2, không có vốn hóa, và việc thu thập tốn nhiều ngày. Các kết luận đó đúng với **API CafeF và danh sách mã của Vietcap**, nhưng sai ở mức hệ thống vì còn hai nguồn khác chưa thử: **API VNDirect** và **API công ty của Vietcap iQ**. Cả hai đã được kiểm chứng và thay đổi phần lớn các kết luận (xem mục 3, 4).

## 0. Thay đổi nguồn dữ liệu so với đề cương

Đối chiếu với mục 5 của đề cương (Nguồn dữ liệu và phương pháp thu thập).

### 0.1. Nguồn được thêm mới

| Nguồn | Dùng để làm gì | Lý do thêm |
|-------|----------------|------------|
| **VNDirect finfo API** (`api-finfo.vndirect.com.vn`) | Giá, khối ngoại, tự doanh, danh sách mã | **Trở thành nguồn chính.** Giá và khối ngoại đủ từ 09/2020, tự doanh từ 05/2022, một lần gọi lấy được cả thị trường một tháng |
| **Vietcap iQ – thông tin công ty** (`iq.vietcap.com.vn/.../company/{mã}`) | ICB cấp 2 và cấp 4, vốn hóa, số cổ phiếu, ngày niêm yết | Đề cương chỉ nêu API danh sách mã của Vietcap, thiếu phần này |

### 0.2. Nguồn đổi vai trò hoặc cách dùng

| Nguồn | Đề cương ghi | Thực tế |
|-------|--------------|---------|
| **API CafeF** (giá, khối ngoại, tự doanh) | Nguồn chính | **Chuyển thành nguồn phụ** để đối chiếu. Địa chỉ đã đổi từ `s.cafef.vn/Ajax/...` sang `cafef.vn/du-lieu/ajax/...`. Trang tối đa 30 dòng, mỗi lần gọi tối đa 1 năm, hay trả rỗng, khối ngoại chỉ tính khớp lệnh. Vẫn là **nguồn duy nhất cho VN-Index** |
| **API Vietcap** (danh sách mã) | Danh sách mã, sàn, ICB | Dùng thêm nhóm chỉ số `getByGroup` (VN30, VN100, VNMidCap, VNSmallCap, HNX30) |
| **Tin nhanh Chứng khoán** | Crawl theo chuyên mục hoặc theo mã bài | Chỉ **RSS** (`/rss/home.rss`, nguồn mới). Phân trang chuyên mục không hoạt động; crawl theo ID dùng được nhưng tốn 20–120 giờ nên không khuyến nghị |

### 0.3. Giữ nguyên

| Nguồn | Ghi chú |
|-------|---------|
| EconVNNews (Hugging Face) | Đã xác nhận; chỉ có ngày đăng, không có giờ. Tên tệp VnExpress có hậu tố `_clean` |
| RSS VnEconomy, Vietstock, VnExpress | Đã xác nhận; VnEconomy dùng múi giờ GMT |
| CafeF phân trang chuyên mục | Đã xác nhận; địa chỉ `trang-N.html`, sâu tới khoảng trang 500 |
| yfinance (7 chuỗi quốc tế) | Đã xác nhận; không có VN-Index |

### 0.4. Chưa xác minh hoặc nhập tay

| Nguồn | Tình trạng |
|-------|-----------|
| Cục Thống kê (CPI, sản xuất công nghiệp, xuất nhập khẩu) | Vào được `www.nso.gov.vn`; chưa bóc số liệu; nhập tay CSV |
| Dòng vốn ETF (bài tuần VnEconomy) | Chưa thử lấy |
| Nhà đầu tư cá nhân (thống kê FiinTrade trong bài tuần) | Chưa thử lấy |
| Bài tổng hợp phiên (VnEconomy, Vietstock) để đối chiếu chéo | Chỉ thấy qua RSS vài ngày gần nhất; lịch sử lưu trữ chưa thử |

Lưu ý: đề cương dùng VN-Index nhiều (dashboard, backtest) nhưng không nêu nguồn lấy. Nguồn đó là CafeF (`Symbol=VNINDEX`), vì yfinance và VNDirect đều không có.

## 1. Tóm tắt

| Nguồn | Vai trò đề xuất | Kết luận |
|-------|-----------------|----------|
| **VNDirect finfo API** (`api-finfo.vndirect.com.vn`) | **Nguồn chính** cho giá, khối ngoại, tự doanh | Một lần gọi trả cả lịch sử hoặc cả thị trường một tháng. Khối ngoại và giá đủ từ 01/09/2020; tự doanh từ 17/05/2022 |
| CafeF API (giá, khối ngoại, tự doanh) | Nguồn phụ, đối chiếu, và **nguồn duy nhất cho VN-Index** | Dùng được nhưng chậm, bất ổn, chỉ 30 dòng mỗi trang; khối ngoại chỉ gồm khớp lệnh |
| Vietcap `getAll` và nhóm chỉ số | Danh sách mã, sàn, nhóm VN30, VN100, VNMidCap, VNSmallCap, HNX30 | Đạt |
| **Vietcap iQ công ty** | **ICB cấp 2 và cấp 4, vốn hóa, số cổ phiếu, ngày niêm yết** | Đạt, mỗi mã một lần gọi |
| EconVNNews (Hugging Face) | Tin tức backfill 09/2020 – 09/2024 | Dùng được; chỉ có ngày đăng |
| RSS VnEconomy, Vietstock, VnExpress, Tin nhanh CK | Tin cập nhật liên tục | Dùng được; chỉ giữ 2–6 ngày gần nhất |
| CafeF phân trang chuyên mục | Lấp khoảng tin 10/2024 – nay | Dùng được, khoảng 410 trang |
| Tin nhanh CK theo mã bài | Backfill tin | Khả thi nhưng tốn kém, không khuyến nghị |
| yfinance | 7 chuỗi quốc tế | Đạt |
| Cục Thống kê | Chỉ số vĩ mô trong nước | Nhập tay CSV |

## 2. VNDirect finfo API (nguồn chính, đã xác nhận)

### 2.1. Endpoint

Địa chỉ cơ sở: `https://api-finfo.vndirect.com.vn/v4/` (tên miền `finfo-api...` không kết nối được). Công khai, không cần khóa. Cú pháp lọc: `?q=<trường>:<giá trị>~<trường>:gte:<ngày>~<trường>:lte:<ngày>&size=<n>&sort=<trường>:asc`.

| Dữ liệu | Endpoint | Trường ngày | Trường chính |
|---------|----------|-------------|--------------|
| Giá | `stock_prices` | `date` | `open`, `high`, `low`, `close`, `average` (nghìn đồng); `adOpen`...`adClose` (giá điều chỉnh); `basicPrice`, `ceilingPrice`, `floorPrice`; `nmVolume`, `nmValue` (khớp lệnh); `ptVolume`, `ptValue` (thỏa thuận); `pctChange`; `floor`; `type` |
| Khối ngoại | `foreigns` | `tradingDate` | `buyVal`, `sellVal`, `netVal`, `buyVol`, `sellVol`, `netVol`, `totalRoom`, `currentRoom`, `floor`, `type` |
| Tự doanh | `proprietary_trading` | `date` | `buyingVal`, `sellingVal`, `netVal`, `buyingVol`, `sellingVol`, `netVol`, kèm tỷ lệ so với thị trường; `floor`, `type` |
| Danh sách mã | `stocks?q=type:STOCK~status:listed` | – | 1.519 mã đang niêm yết |

Đơn vị: giá tính **nghìn đồng**; mọi giá trị tiền (`nmValue`, `ptValue`, `buyVal`, `sellVal`, `netVal`, `buyingVal`...) tính **đồng**. Có sẵn cột ròng cho cả khối ngoại và tự doanh (CafeF không có cột ròng tự doanh).

### 2.2. Cách lấy dữ liệu (đã xác nhận)

| Cách gọi | Kết quả đã đo |
|----------|----------------|
| Một mã, toàn bộ lịch sử (`code:VNM~date:gte:2020-09-01`, `size=5000`) | 1.554 dòng trong một lần gọi, 2,3–2,7 giây |
| Mọi mã trong một ngày (`date:2026-11-23`, bỏ điều kiện `code`) | 1.562 dòng giá, 2.678 dòng khối ngoại, 545 dòng tự doanh; 2,4–2,7 giây |
| Mọi mã trong một tuần (khối ngoại) | 15.872 dòng, một lần gọi |
| Mọi mã trong một tháng (`size=100000`) | Khối ngoại 52.471 dòng (4,0 giây), giá 36.240 dòng (5,7 giây), tự doanh 6.709 dòng |
| Lọc cổ phiếu | Kết quả gồm nhiều loại chứng khoán (`type`: STOCK, ETF, CW, FU, BOND, INDEX...). Chỉ giữ `type = STOCK` (33.450 dòng trong tháng 10/2026) |

Hệ quả: backfill toàn thị trường 09/2020 – nay chỉ cần khoảng 74 khoảng tháng × 3 endpoint ≈ 220 lần gọi (đo thực tế khoảng 1,5–2 giờ khi chạy song song với các luồng khác), thay vì hàng trăm nghìn lần gọi theo từng mã ở CafeF. Cập nhật hằng ngày chỉ cần vài lần gọi.

### 2.3. Độ phủ lịch sử (đã xác nhận trên 8 mã mẫu và 2 mã đã hủy niêm yết)

| Mã (sàn) | Giá | Khối ngoại | Tự doanh |
|----------|-----|------------|----------|
| VNM, VCB, HPG (HOSE) | 1.554 dòng, 01/09/2020 – 23/11/2026 | 1.554 dòng, cùng khoảng | 1.107 dòng, từ 17/05/2022 (đủ mọi ngày giao dịch) |
| SHS, PVS (HNX) | 1.554 dòng | 1.554 dòng | SHS 338 dòng, PVS 712 dòng, từ 23/05/2022 |
| BSR (UPCoM) | 1.546 dòng | 1.546 dòng | 593 dòng, từ 20/05/2022 |
| ACV (UPCoM) | 1.554 dòng | 1.554 dòng | 295 dòng, từ 26/05/2022 đến 06/07/2026 |
| QLT (đã hủy niêm yết 12/2022) | 582 dòng đến 26/12/2022 | 582 dòng | 0 dòng |
| NGC (đã hủy niêm yết 10/2026) | 1.532 dòng đến 30/10/2026 | 1.532 dòng | 6 dòng |

Nhận xét:
- **Khối ngoại và giá đầy đủ từ 01/09/2020** cho cả HOSE, HNX, UPCoM và cả mã đã hủy niêm yết. Điều này loại bỏ vấn đề dữ liệu khối ngoại thiếu và bất thường năm 2020 ở CafeF.
- **Tự doanh theo mã chỉ có từ giữa 05/2022**, đồng đều giữa ba sàn (17–26/05/2022). Trước mốc đó cả VNDirect và CafeF đều không có.
- Mã lớn có dòng tự doanh mọi ngày; mã nhỏ chỉ có dòng ở những ngày có giao dịch tự doanh (SHS 338 dòng trong khoảng 1.150 ngày). Cách hiểu hợp lý: ngày không có dòng nghĩa là tự doanh không giao dịch (bằng 0). Đây là suy luận từ mẫu, cần kiểm tra thêm ở N3 trên nhiều mã.
- Mã đã hủy niêm yết còn dữ liệu đến ngày hủy, nên có thể tránh thiên lệch người sống sót.

### 2.4. Hành vi cần xử lý

| Hiện tượng | Xử lý |
|------------|-------|
| **Ngày mới nhất chưa đầy đủ**: ngày 23/11/2026 trả 1.519 dòng cổ phiếu nhưng cả 1.519 dòng đều có giá trị khối ngoại bằng 0 (các ngày trước có 283–426 mã có giao dịch). VNDirect cập nhật khối ngoại trễ | Mỗi lần cập nhật lấy lại ít nhất 3 ngày gần nhất; chỉ nạp ngày khi số mã có giao dịch khối ngoại vượt ngưỡng; ngày không đạt thì đánh dấu "chưa công bố" |
| Hàng `type = INDEX` trong kết quả có giá trị lệch hẳn với số của mã | Chỉ dùng `type = STOCK` |
| `VNINDEX` không có trong `stock_prices` (0 dòng) | Lấy VN-Index từ CafeF |
| Có dòng `type = None` trong tự doanh | Bỏ qua |
| Là API không chính thức | Lưu thô vào `raw` ngay khi lấy; CafeF làm nguồn dự phòng |

### 2.5. Khối ngoại của VNDirect khác CafeF ở giao dịch thỏa thuận (đã xác nhận)

So sánh VNM từ 04/01 đến 10/01/2024 ([test](../tests/unit/test_source_fixtures.py)):

| Ngày | Mua CafeF | Mua VNDirect | Bán CafeF | Bán VNDirect | Giá trị thỏa thuận (CafeF giá) |
|------|-----------|--------------|-----------|--------------|-------------------------------|
| 04/01 | 11,87 tỷ | 11,88 tỷ | 33,09 tỷ | 33,10 tỷ | 0 |
| 05/01 | 9,84 tỷ | 24,26 tỷ | 19,43 tỷ | 40,00 tỷ | 20,57 tỷ |
| 08/01 | 8,85 tỷ | 8,85 tỷ | 43,82 tỷ | 43,82 tỷ | 0 |
| 09/01 | 7,08 tỷ | 13,19 tỷ | 86,40 tỷ | 86,40 tỷ | 8,09 tỷ |
| 10/01 | 16,20 tỷ | 16,20 tỷ | 67,49 tỷ | 67,49 tỷ | 0 |

Ngày không có thỏa thuận thì hai nguồn khớp (sai khác dưới 0,1%). Ngày có thỏa thuận, chênh lệch mỗi chiều không vượt giá trị thỏa thuận và gần bằng nó (05/01: bán chênh 20,57 tỷ, đúng bằng thỏa thuận). Suy luận: **VNDirect gồm cả giao dịch thỏa thuận, CafeF chỉ khớp lệnh.** Đây là suy luận từ hai ngày, chưa có nguồn thứ ba để xác nhận.

Lưu ý: số liệu VNM ngày 10/01/2024 mà bạn đối chiếu trên trang CafeF khớp vì ngày đó không có thỏa thuận; ngày 05/01/2024 mới phân biệt được hai nguồn.

Hệ quả: dùng VNDirect làm nguồn chính vì tổng hợp dòng tiền cần gồm cả thỏa thuận (nhóm "nhà đầu tư trong nước khác" tính bằng tổng giá trị giao dịch gồm thỏa thuận trừ khối ngoại trừ tự doanh). CafeF dùng để kiểm tra chéo trên các ngày không có thỏa thuận.

## 3. CafeF API (nguồn phụ, đã xác nhận)

### 3.1. Endpoint

Địa chỉ cũ trong đề cương (`s.cafef.vn/Ajax/PageNew/DataHistory/*.ashx`) trả 301 và chuyển về địa chỉ mới:

| Dữ liệu | URL |
|---------|-----|
| Giá | `https://cafef.vn/du-lieu/ajax/pagenew/datahistory/pricehistory.ashx` |
| Khối ngoại | `https://cafef.vn/du-lieu/ajax/pagenew/datahistory/gdkhoingoai.ashx` |
| Tự doanh | `https://cafef.vn/du-lieu/ajax/pagenew/datahistory/gdtudoanh.ashx` |

Tham số: `Symbol`, `StartDate`, `EndDate`, `PageIndex`, `PageSize`. Gửi `Referer: https://cafef.vn/` và `User-Agent` hợp lệ.

### 3.2. Hành vi đã quan sát

| Hạng mục | Kết quả |
|----------|---------|
| Ngày trong **tham số** | `MM/DD/YYYY` |
| Ngày trong **phản hồi** | `DD/MM/YYYY` (khác chiều với tham số) |
| Kích thước trang | Tối đa 30 dòng; khối ngoại với `PageSize` lớn hơn 30 trả `TotalCount` nhưng danh sách rỗng |
| Khoảng ngày | Tối đa một năm mỗi lần gọi |
| Thứ tự | Mới nhất trước |
| Độ ổn định | Lần gọi đầu có khi trả `TotalCount = 0` rồi lần sau có dữ liệu; endpoint giá có lúc mất 25–43 giây rồi trả rỗng; có ô thử 3 lần vẫn rỗng |
| VN-Index | `Symbol=VNINDEX` ở endpoint giá có dữ liệu |

### 3.3. Đơn vị

Giá nghìn đồng; `GiaTriKhopLenh`, `GtThoaThuan` **tỷ đồng**; khối ngoại và tự doanh **đồng**; `ThayDoi` là chuỗi `"-0,60 (-0,88%)"`; tự doanh viết hoa không đồng nhất (`KLcpMua`, `KlcpBan`) và không có cột ròng.

### 3.4. Độ phủ

Mẫu 3 mã (VNM, SHS, BSR) theo số dòng mỗi năm của khối ngoại: 2022 trở đi đầy đủ (242–250 dòng), 2021 thiếu với mã nhỏ (từ 01/03/2021), 2020 thưa hoặc bất thường (VNM trả 1.702 dòng, gấp khoảng 7 lần số ngày giao dịch). Tự doanh: VNM từ 01/11/2022, SHS từ 29/09/2025, BSR từ 17/01/2025. VCB và HPG cũng bắt đầu từ 11/2022. **Độ phủ của CafeF kém hơn VNDirect nên chỉ dùng làm nguồn phụ.** Bất thường năm 2020 của CafeF không còn là vấn đề vì dữ liệu năm 2020 lấy từ VNDirect.

## 4. Vietcap

### 4.1. Danh sách mã – `getAll` (đã xác nhận)

`https://trading.vietcap.com.vn/api/price/symbols/getAll` (luôn nén gzip). 3.876 bản ghi; cổ phiếu đang niêm yết: 412 HSX, 299 HNX, 808 UPCoM (tổng 1.519, khớp danh sách của VNDirect); 239 cổ phiếu đã hủy niêm yết. Có `icbCode2` (19 siêu ngành, 19 cổ phiếu thiếu), `board`, tên công ty. Loại khác cần lọc: chứng quyền (1.792), trái phiếu, phái sinh, ETF.

### 4.2. Nhóm chỉ số – `getByGroup` (đã xác nhận)

`.../api/price/symbols/getByGroup?group=<tên>`: VN30 (30 mã), VN100 (100), VNMidCap (70), VNSmallCap (211), HNX30 (30), HOSE (436), HNX (299), UPCOM (808). Các tên VNALL, VNX50, VNDIAMOND, VNFINLEAD trả rỗng. Là danh sách hiện tại, không có lịch sử thành viên.

### 4.3. Thông tin công ty – Vietcap iQ (đã xác nhận)

`https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{symbol}`, mỗi mã một lần gọi (khoảng 2,1 giây), công khai.

| Trường | Ý nghĩa | Ví dụ VNM |
|--------|---------|-----------|
| `icbCodeLv2` | ICB cấp 2 (siêu ngành) | 3500 |
| `icbCodeLv4` | ICB cấp 4 (phân ngành) | 3577 |
| `sector` | Tên tiếng Anh của cấp 2 | Food & Beverage |
| `marketCap` | Vốn hóa hiện tại (đồng) | 109.304.669.773.500 |
| `issueShare` | Số cổ phiếu lưu hành | 2.089.955.445 |
| `listingDate` | Ngày niêm yết | 19/01/2006 |
| `maximumForeignPercentage`, `foreignerPercentage`, `freeFloatPercentage` | Giới hạn và tỷ lệ sở hữu nước ngoài, free float | 100%, –, 40% |

Đã kiểm tra 7 mã (VNM, VCB, HPG, SHS, PVS, BSR, ACV): mã cấp 4 luôn có hai chữ số đầu trùng cấp 2. ICB cấp 1 (ngành) và cấp 3 (nhóm ngành) suy ra từ tiền tố mã cấp 4 theo cấu trúc ICB: cấp 1 = chữ số đầu + `000`, cấp 3 = ba chữ số đầu + `0` (ví dụ 3577 → 3570 → 3500 → 3000; 8355 → 8350 → 8300 → 8000). **Tên** tiếng Việt và tiếng Anh của cấp 1, 3, 4 không có trong phản hồi nên phải lập bảng tên từ tài liệu ICB (seed, cần đối chiếu). Vốn hóa và ngành là ảnh chụp hiện tại, không có lịch sử.

## 5. Tin tức

### 5.1. EconVNNews (đã xác nhận)

Hugging Face `khoalnd/EconVNNews`, giấy phép MIT. Bốn tệp JSON, 01/09/2020 – 30/09/2024: CafeF 1.044 MB, VnExpress 297 MB, VietnamNet 149 MB, CafeBiz 81 MB. Trường: `title`, `url`, `content`, `published_date`, `author`, `category`, `source`. **`published_date` chỉ có ngày, không có giờ.** Đã nạp vào `raw.news_backfill`: **307.767 bài** (CafeF 198.834; VnExpress 66.658; VietnamNet 27.944; CafeBiz 14.331), từ 01/09/2020 đến 30/09/2024; chỉ khoảng 137 bài có nội dung dưới 100 ký tự. Chưa lọc bài liên quan chứng khoán. Nên đọc dạng luồng (ví dụ `ijson`). Với backfill, quy tắc 15h không áp dụng được; dùng ngày đăng để gán phiên (nếu là ngày giao dịch thì phiên cùng ngày, ngược lại phiên kế tiếp).

### 5.2. RSS (đã xác nhận)

| Nguồn | URL | Số bài | Khoảng thời gian | Múi giờ |
|-------|-----|--------|------------------|---------|
| VnEconomy | `vneconomy.vn/chung-khoan.rss` | 50 | ≈ 6 ngày | **GMT** |
| Vietstock | `vietstock.vn/830/chung-khoan/co-phieu.rss` | 20 | ≈ 5 ngày | +0700 |
| Vietstock | `vietstock.vn/144/chung-khoan.rss` | 30 | ≈ 3 ngày | +0700 |
| VnExpress | `vnexpress.net/rss/kinh-doanh.rss` | 60 | ≈ 4 ngày | +0700 |
| Tin nhanh CK | `tinnhanhchungkhoan.vn/rss/home.rss` | 50 | ≈ 2 ngày | +07:00 |

RSS không backfill được; phải đọc thường xuyên. Toàn văn lấy được bằng `requests` và BeautifulSoup (VnEconomy nén gzip bắt buộc; Tin nhanh CK có lúc khai báo gzip nhưng gửi dữ liệu thường, client phải xử lý cả hai). Phải chuẩn hóa múi giờ của VnEconomy. Có bài tổng hợp phiên chứa số liệu ròng (VnEconomy, Vietstock "Theo dấu dòng tiền cá mập"), bóc bằng biểu thức chính quy.

### 5.3. CafeF phân trang chuyên mục (đã xác nhận)

`https://cafef.vn/chung-khoan/trang-N.html` (dạng `.chn` trả 404), 20 bài mỗi trang. Trang 1 ≈ 19–24/11/2026; trang 100 ≈ 03/2026; 250 ≈ 07/2025; 350 ≈ 01/2025; 500 ≈ 10/2023; từ trang 600 rỗng. Khoảng 10/2024 – nay ≈ trang 1–410 ≈ 8.000 bài. Thời điểm đăng đọc được từ mã bài trong URL (chính xác tới giây). Ước tính 3,5–5 giờ cho khoảng 8.400 request.

### 5.4. Tin nhanh Chứng khoán (đã thử, [probe_tnck.py](../src/ingestion/probes/probe_tnck.py))

| Cách lấy | Kết quả |
|----------|---------|
| RSS `/rss/home.rss` | Dùng được, 50 bài (≈ 2 ngày), có toàn văn khi vào bài |
| Phân trang chuyên mục (`/chung-khoan/?page=N`) | **Không phân trang**: mọi N trả cùng một tập bài |
| Truy cập bài bằng mã số (`/x-post<ID>.html`, slug tùy ý) | **Dùng được**: trả đúng bài của ID. ID tăng dần: 250000 ≈ 09/2020, 270000 ≈ 05/2021, 300000 ≈ 06/2022, 330000 ≈ 09/2023, 345000 ≈ 05/2024, 360000 ≈ 12/2024, 402000 ≈ 11/2026 |
| Thời gian đăng, chuyên mục | Thẻ meta `article:published_time` (có giờ, +0700) và `article:section` |
| Nội dung | Toàn văn 2.000–4.000 ký tự/bài; **gồm cả tin ngoài chứng khoán** (pháp lý, xã hội) nên phải lọc theo chuyên mục |

Hệ quả: backfill theo ID khả thi về kỹ thuật nhưng tốn kém: từ 10/2024 (ID ≈ 354.000) đến nay ≈ 48.000 request (ước tính 20–40 giờ), toàn bộ từ 09/2020 ≈ 152.000 request (60–120 giờ), kèm phần lớn bài không liên quan. **Khuyến nghị: chỉ dùng RSS để cập nhật liên tục, không backfill.** `robots.txt` cấm `/api/` và `/search/`.

### 5.5. robots.txt

| Trang | Quy định cho bot chung | Cách xử lý |
|-------|------------------------|------------|
| cafef.vn | `Allow: /` | Giãn cách 1,5–2 giây |
| vneconomy.vn | Không có quy tắc cho `*` (một số bot AI có `Crawl-delay: 1`) | Giãn cách ≥ 2 giây |
| vietstock.vn | Cấm `/manager`, `/export`, `/cache`, `*.js`, `*.css` | Chỉ RSS và trang bài |
| vnexpress.net | `Allow: /` | Giãn cách 1,5–2 giây |
| tinnhanhchungkhoan.vn | Cấm `/api/`, `/search/`, `/tim-kiem/` | Tránh các đường dẫn đó |

## 6. yfinance (đã xác nhận)

01/09/2020 – 23/11/2026, không có giá đóng rỗng: USD/VND `VND=X` (1.620 dòng), DXY `DX-Y.NYB` (1.567), S&P 500 `^GSPC` (1.565), dầu WTI `CL=F` (1.567), dầu Brent `BZ=F` (1.568), vàng `GC=F` (1.568), lợi suất trái phiếu Mỹ 10 năm `^TNX` (1.565). Lịch nghỉ khác Việt Nam nên phải đồng bộ về lịch giao dịch VN. Yahoo không có VN-Index.

## 7. Cục Thống kê (một phần)

`https://www.nso.gov.vn/` truy cập được (tên miền không có `www` từng không phân giải). Chưa bóc số liệu. Đề xuất nhập tay CSV hằng tháng (CPI, sản xuất công nghiệp, xuất nhập khẩu): `indicator_code`, `period`, `value`, `published_date`, `source_url`.

## 8. Việc cần làm thủ công

1. Đối chiếu một ngày **có giao dịch thỏa thuận** để biết số nào khớp với thông lệ thị trường (mục 2.5). Hướng dẫn ở phần trả lời kèm theo.
2. Xác nhận các quyết định ở mục 9.

## 9. Quyết định cần xác nhận

**Trạng thái (25/11/2026):** cả 6 quyết định đã được chấp nhận theo đề xuất (quyết định 4 sau khi được giải thích backfill là gì, xem cuối mục này).

| # | Quyết định | Lý do |
|---|-----------|-------|
| 1 | VNDirect là nguồn chính cho giá, khối ngoại, tự doanh; CafeF là nguồn phụ và nguồn VN-Index | Đủ lịch sử từ 09/2020, tốc độ gấp hàng nghìn lần |
| 2 | Giữ nguyên ngành ICB cấp 1 đến cấp 4 như đề cương | Lấy được cấp 4 từ Vietcap iQ; cấp 1 và 3 suy ra từ mã |
| 3 | Giữ "nhóm vốn hóa" như đề cương | Lấy được vốn hóa từ Vietcap iQ (hiện tại) |
| 4 | Tin nhanh Chứng khoán chỉ dùng RSS, không backfill | Backfill tốn 20–120 giờ và lẫn tin không liên quan |
| 5 | Tự doanh theo mã chỉ có từ 17/05/2022; phần trước đó dùng bài tổng hợp phiên ở mức thị trường hoặc ngành, và dự báo chính chỉ dùng khối ngoại | Cả hai nguồn đều không có dữ liệu trước mốc này |
| 6 | Sửa đề cương: "dữ liệu giao dịch từ 09/2020" đúng cho giá và khối ngoại; thêm lưu ý tự doanh theo mã từ 05/2022 | Khớp thực tế nguồn |

**Backfill là gì và ý nghĩa với hệ thống (quyết định 4).** Backfill là thu thập bù dữ liệu lịch sử, đối lập với thu thập hằng ngày chỉ lấy phần mới. Hệ thống cần cả hai: lịch sử để huấn luyện mô hình cảm xúc và dự báo, dữ liệu hằng ngày để dashboard và khuyến nghị luôn mới.
- Các nguồn khác đã backfill được: VNDirect từ 09/2020, EconVNNews 09/2020 – 09/2024, CafeF tin từ 10/2024.
- Tin nhanh Chứng khoán (TNCK) chỉ có RSS, vốn chỉ trả vài chục bài gần nhất. Muốn có lịch sử phải đoán mã số bài rồi tải từng bài (khoảng 48.000 lần gọi cho giai đoạn 10/2024 – nay, 20–40 giờ; toàn bộ từ 09/2020 khoảng 152.000 lần, 60–120 giờ), phần lớn là tin không liên quan, lại chạm điều khoản `robots.txt`.
- Hệ quả của quyết định 4: nguồn TNCK chỉ có tin từ ngày bắt đầu chạy RSS trở đi (tích lũy dần theo ngày). Không ảnh hưởng huấn luyện vì lịch sử tin đã có từ CafeF và EconVNNews (310.000 bài, 09/2020 – nay). TNCK chỉ bổ sung tin mới và là một nguồn đối chiếu thêm.
