{#- Tổng hợp sẵn: dòng tiền ngành ICB cấp 2 x tuần x nhóm nhà đầu tư (nguồn của dashboard Luân chuyển ngành).
    Materialized view PostgreSQL; dbt làm mới mỗi lần chạy. -#}
{{ config(
    materialized='materialized_view',
    indexes=[{'columns': ['week_start_date']}, {'columns': ['icb_l2_code']}]
) }}

select
    t.week_start_date,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    s.icb_l1_code,
    it.code as investor_type,
    sum(f.buy_value_bn) as buy_value_bn,
    sum(f.sell_value_bn) as sell_value_bn,
    sum(f.net_value_bn) as net_value_bn,
    count(distinct f.stock_key) as n_stocks,
    count(distinct f.trade_date) as n_days
from {{ ref('fact_money_flow') }} f
join {{ ref('dim_time') }} t on t.date_key = f.date_key
join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
where d.security_type = 'STOCK'
group by 1, 2, 3, 4, 5
