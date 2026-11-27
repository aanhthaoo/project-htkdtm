# Tệp CSV mẫu để nhập dữ liệu thủ công (TV4)

Giữ nguyên dòng tiêu đề và đơn vị; mã hóa UTF-8; ngày dạng `YYYY-MM-DD`; số dùng dấu chấm thập phân. Các dòng trong tệp mẫu chỉ minh họa, phải thay bằng số liệu thật kèm nguồn.

| Tệp | Nội dung | Cột bắt buộc |
|-----|----------|--------------|
| `macro_monthly.csv` | Chỉ số vĩ mô theo tháng (CPI, sản xuất công nghiệp, xuất khẩu, nhập khẩu) | `period_end`, `indicator_code`, `value`, `unit`, `source`, `published_date` |
| `individual_investors_weekly.csv` | Mua/bán của nhà đầu tư cá nhân trong nước theo tuần (từ báo cáo tuần), đơn vị tỷ đồng | `week_start_date` (thứ Hai), `buy_value_bn`, `sell_value_bn`, `source` |
| `etf_flows_monthly.csv` | Dòng vốn ròng vào các quỹ ETF theo tháng, đơn vị tỷ đồng | `month_start_date` (ngày 1), `etf_name`, `net_flow_bn`, `source` |

`indicator_code` hợp lệ cho vĩ mô: `CPI_YOY`, `IIP_YOY`, `EXPORT_USD_BN`, `IMPORT_USD_BN`. Cột `published_date` là ngày số liệu được công bố (dùng để tránh nhìn trước dữ liệu khi huấn luyện mô hình).

## Cách nạp (từ thư mục `src/`)

```bash
python -m ingestion.cli load-csv macro      <tệp>.csv --dry-run   # chỉ kiểm tra, chưa ghi
python -m ingestion.cli load-csv macro      <tệp>.csv             # ghi vào raw.manual_macro_monthly
python -m ingestion.cli load-csv individual <tệp>.csv             # raw.manual_individual_weekly
python -m ingestion.cli load-csv etf        <tệp>.csv             # raw.manual_etf_monthly
python dbt_dw/run.py run --select "stg_macro_manual+ stg_individual_weekly+ stg_etf_monthly+"   # đưa vào dw
python dbt_dw/run.py test --select "fact_macro_indicator fact_individual_flow_weekly fact_etf_flow_monthly manual_macro_published_after_period"
```

Kết quả trong `dw`: `fact_macro_indicator` (nguồn `manual_csv`, có `published_date_key`), `fact_individual_flow_weekly`, `fact_etf_flow_monthly`. Chỉ số tháng **không** nằm trong `ds_macro_daily` (dataset theo ngày) để mô hình không dùng số liệu trước ngày công bố; GĐ3 sẽ ghép theo `published_date`.

Quy tắc kiểm tra (có dòng sai thì **không ghi gì** và in lý do từng dòng; mỗi lần nạp ghi một dòng vào `dw.dq_log`, `layer = 'raw'`, `source = 'manual_csv'`):
- đúng tiêu đề cột, số và ngày hợp lệ, không trùng khóa trong cùng tệp;
- vĩ mô: `period_end` là ngày cuối tháng, đã kết thúc, `published_date` không sớm hơn `period_end` và không ở tương lai;
- tuần: `week_start_date` là thứ Hai và tuần đã kết thúc; tháng: `month_start_date` là ngày 1 và tháng đã kết thúc; số tiền mua/bán không âm;
- dòng có ghi chú chứa "Mẫu minh họa" bị từ chối (tệp mẫu chỉ để xem định dạng). Muốn thử bằng tệp mẫu thì thêm `--allow-sample`, rồi nhớ xóa dữ liệu mẫu khỏi `raw.manual_*` và chạy lại dbt (dòng vĩ mô tháng trong dw tự đồng bộ với raw ở lần chạy dbt kế tiếp).
- Nạp lại cùng khóa thì ghi đè (sửa số liệu: sửa CSV rồi nạp lại).
