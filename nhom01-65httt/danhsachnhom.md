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
| 1 | Trương Thảo Anh | 2351160505 | 65HTTT | Nhóm trưởng | Phụ trách chính: hạ tầng Docker, toàn bộ thu thập dữ liệu và ETL, kho Star Schema, toàn bộ SQL dataset Superset, backend/frontend khung, đăng nhập và phân quyền, n8n lõi, mô hình ML (dự báo, cảm xúc, phân cụm) và API mô hình, bộ mẫu cho nhóm, tích hợp, demo | | |
| 2 | Phạm Hoàng Vũ | 2351160566 | 65HTTT | Thành viên | Chức năng web nâng cao, chatbot, khuyến nghị: trang chi tiết mã cổ phiếu, danh sách theo dõi và cảnh báo, trang quản trị; chatbot LLM + RAG (kể cả 10–15 truy vấn mẫu); quy tắc khuyến nghị hằng tuần, backtest | | |
| 3 | Nguyễn Văn Quang | 2351160542 | 65HTTT | Thành viên | Trang vĩ mô, tin tức, tự động hóa, kiểm thử: sơ đồ (kiến trúc, Star Schema, luồng dữ liệu); workflow n8n (bản tin, cảnh báo, báo lỗi ETL); API tin tức và vĩ mô, thành phần Tin nổi bật, trang Vĩ mô, chân trang lưu ý; kiểm thử (giao diện, Postman); slide | | |
| 4 | Vũ Văn Quảng | 2351160543 | 65HTTT | Thành viên | Dashboard, trang tổng quan và phân tích ngành: định nghĩa KPI, dựng 6 dashboard Superset; API KPI và top mã gom/xả, thành phần Thẻ KPI, trang Tổng quan, trang Phân tích ngành; viết insight và khuyến nghị hành động | | |
| 5 | Phan Thị Sông Thương | 2351160557 | 65HTTT | Thành viên | Trang dự báo, tài khoản, khung chat, báo cáo: kiểm tra nhãn cảm xúc, nhập CSV vĩ mô/nhà đầu tư cá nhân/ETF; API và trang Dự báo & khuyến nghị, trang Tài khoản, giao diện khung chat; tổng hợp báo cáo cuối kỳ | | |

---

## 3. Cấu Trúc Mã Nguồn Trong Thư Mục Nhóm

Mã nguồn của nhóm phải được đặt trong thư mục này theo cấu trúc khuyến nghị:

```text
nhom01-65httt/
├── danhsachnhom.md        # Tệp tin thông tin nhóm này
├── README.md              # (Tùy chọn) Hướng dẫn cài đặt và chạy mã nguồn của riêng nhóm
├── docs/                  # Tài liệu phân tích, thiết kế, báo cáo đồ án
│   ├── De_cuong_BTL__Nhom01.docx
│   └── Bao_cao_tong_quan_TH4_BTL_Nhom01.docx
└── src/                   # Mã nguồn của dự án
    ├── backend/
    ├── frontend/
    └── database/
```

---

## 4. Hướng Dẫn Cài Đặt Và Thực Thi Mã Nguồn

### 4.1. Môi trường yêu cầu
- Hệ điều hành: [Ví dụ: Windows 10/11, Ubuntu 22.04]
- Nền tảng thực thi: [Ví dụ: Node.js >= 18.x, Python >= 3.10, JDK >= 17]
- Cơ sở dữ liệu: [Ví dụ: PostgreSQL 15, MySQL 8.0, MongoDB 6.0]

### 4.2. Các bước cài đặt và khởi chạy
1. Bước 1: Thiết lập cấu hình môi trường (sao chép tệp cấu hình mẫu và điền tham số).
2. Bước 2: Cài đặt các gói phụ thuộc.
3. Bước 3: Khởi chạy ứng dụng.
