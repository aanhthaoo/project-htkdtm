{#- Cảnh báo: tỷ lệ ngày giao dịch có khối ngoại thiếu (nguồn VNDirect thiếu một số ngày) vượt 2%.
    Không tính các ngày chưa được nạp (chưa có giá). -#}
{{ config(severity='warn') }}
select rate
from (
    select count(*) filter (where not is_foreign_complete)::numeric / nullif(count(*), 0) as rate
    from {{ ref('stg_day_quality') }}
    where n_priced > 0
) t
where rate > 0.02
