{#- Cảnh báo: ngày giao dịch gần đây (60 phiên) có ít hơn 90% số mã niêm yết có giá. -#}
{{ config(severity='warn') }}
with listed as (select count(*) as n from {{ ref('dim_stock') }} where security_type = 'STOCK' and is_active),
recent as (
    select trade_date from {{ ref('stg_calendar') }} order by trade_date desc limit 60
)
select q.trade_date, q.n_priced, l.n
from {{ ref('stg_day_quality') }} q
join recent r on r.trade_date = q.trade_date
cross join listed l
where q.n_priced < 0.9 * l.n
