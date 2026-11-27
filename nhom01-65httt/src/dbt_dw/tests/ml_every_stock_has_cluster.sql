{#- Sau khi chạy mô hình phân cụm, mọi cổ phiếu phải có nhãn cụm (mã không đủ dữ liệu nhận nhãn quy tắc). -#}
select symbol
from {{ ref('dim_stock') }}
where security_type = 'STOCK' and cluster_label is null
