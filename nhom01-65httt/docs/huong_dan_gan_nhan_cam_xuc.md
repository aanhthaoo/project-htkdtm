# Hướng dẫn gán và kiểm tra nhãn cảm xúc (TV5, giai đoạn 2)

**Mục đích.** Mô hình cảm xúc hiện được huấn luyện bằng nhãn do Claude gán (chưa phải nhãn của con người). Tập 390 bài ở `data/samples/sentiment_validation_sample.csv` để **người** gán nhãn, rồi đo mô hình trên đó. Tập này **không** nằm trong nhãn huấn luyện (đã kiểm tra: 0 bài trùng), nên kết quả là kiểm tra độc lập.

Nếu máy chưa có tệp (thư mục `data/` không nằm trong git): chạy `python -m etl.news.samples` từ `src/` để xuất lại, hoặc giải nén gói seed (xem README mục seed).

## 1. Gán nhãn

Mở tệp bằng Excel hoặc Google Sheets (UTF-8), điền cột **`label_human`** cho **từng dòng** bằng đúng một trong ba giá trị `positive`, `neutral`, `negative`. Cột `note` dùng để ghi chú bài khó. **Không sửa các cột khác.**

Góc nhìn: một nhà đầu tư cổ phiếu Việt Nam đọc bài này; nhãn thể hiện tin **tốt hay xấu cho giá cổ phiếu, ngành hoặc thị trường** mà bài nói tới (mã, ngành ở cột `entities` nếu có; cột này có thể sai hoặc trống, khi đó xét doanh nghiệp, ngành hoặc thị trường nêu trong bài).

| Nhãn | Khi nào |
|------|---------|
| `positive` | Tin tốt: lợi nhuận, doanh thu tăng; chia cổ tức, thưởng cổ phiếu; đơn hàng lớn, mở rộng, nâng hạng; khối ngoại mua ròng; thị trường hoặc cổ phiếu tăng điểm; chính sách hỗ trợ, nới tín dụng; vĩ mô thuận lợi. |
| `negative` | Tin xấu: lỗ, nợ xấu, sụt giảm mạnh; bán tháo, khối ngoại bán ròng mạnh, giảm điểm; vi phạm, xử phạt, khởi tố, thanh tra; hủy niêm yết, cảnh báo, kiểm soát; chính sách bất lợi; lạm phát, lãi suất tăng gây bất lợi; cảnh báo rủi ro, mất giá. |
| `neutral` | Không rõ tác động hoặc tốt xấu cân bằng; tin không liên quan đến chứng khoán và doanh nghiệp (tai nạn, thời tiết, văn hóa...) trừ khi có tác động rõ ràng; thông báo hành chính thuần túy (bổ nhiệm, họp cổ đông không có số liệu). |

Quy tắc phụ: chỉ đánh giá giọng điệu và tác động **mà bài nêu**, không dựa vào hiểu biết về diễn biến sau đó; bài bị cắt cụt thì đánh giá theo phần có; không cố cân bằng số lượng nhãn; lưỡng lự giữa `neutral` và nhãn kia thì chọn `neutral` nếu tác động không rõ.

Nên **hai người cùng gán độc lập** (mỗi người một bản sao của tệp) rồi đo độ nhất quán (bước 2); chỗ khác nhau thì thảo luận để chốt một nhãn cuối trong tệp chính.

## 2. Kiểm tra nhãn và đo mô hình

Từ thư mục `src/`:

```bash
python -m ml.sentiment_check                         # kiểm tra tệp, rồi so với mô hình (cần PostgreSQL có dw)
python -m ml.sentiment_check <tệp>.csv --no-db       # chỉ kiểm tra tệp (không cần cơ sở dữ liệu)
python -m ml.sentiment_check <tệp>.csv --json ket_qua.json
```

Lệnh báo từng dòng chưa điền hoặc sai nhãn (và chưa đo cho đến khi sửa xong). Khi tệp hợp lệ, nó in phân bố nhãn, độ nhất quán giữa hai lượt gán (nếu cột `label_llm` được điền) và **người so với mô hình**: accuracy, F1, Cohen kappa và ma trận nhầm (hàng là người). Bài nào không nhắc mã hay ngành nào thì mô hình không có điểm nên bị loại khỏi phép so.

Đo độ nhất quán giữa hai người: đưa nhãn của người thứ hai vào cột `label_llm` của bản tệp thứ nhất (cột này chỉ là "lượt gán thứ hai") rồi chạy lệnh trên.

## 3. Đọc kết quả

- Accuracy của mô hình trên nhãn LLM khoảng 70% (352 bài kiểm tra theo thời gian). Trên nhãn người có thể thấp hơn nếu LLM và người hiểu khác nhau. Con số trên **nhãn người** mới là chỉ số nên đưa vào báo cáo cuối.
- Cohen kappa giữa hai người dưới 0,6 nghĩa là định nghĩa nhãn còn chưa rõ: cần họp thống nhất trước khi dùng nhãn để huấn luyện lại.
- Nếu kết quả trên nhãn người khác hẳn nhãn LLM, ưu tiên huấn luyện lại bằng nhãn người (thêm tệp vào `src/ml/labels/`, xem hằng `LABEL_FILES` trong `src/ml/sentiment.py`).
