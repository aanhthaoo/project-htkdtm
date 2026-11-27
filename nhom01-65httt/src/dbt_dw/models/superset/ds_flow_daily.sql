{#- Dataset Superset: dòng tiền theo ngày x ngành ICB cấp 2 x sàn x nhóm vốn hóa x nhóm nhà đầu tư.
    Đây là dataset cho các bộ lọc dùng chung (thời gian, sàn, ngành, nhóm NĐT, nhóm vốn hóa). Chỉ cổ phiếu, không gồm chỉ số. -#}
{{ config(
    materialized='materialized_view',
    indexes=[{'columns': ['trade_date']}, {'columns': ['icb_l2_code']}, {'columns': ['investor_type']}]
) }}

select
    f.trade_date,
    t.week_start_date,
    t.month_start_date,
    t.year,
    s.icb_l1_name_vi,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    d.exchange,
    coalesce(d.cap_group, 'unknown') as cap_group,
    it.code as investor_type,
    it.name_vi as investor_type_name,
    sum(f.buy_value_bn) as buy_value_bn,
    sum(f.sell_value_bn) as sell_value_bn,
    sum(f.net_value_bn) as net_value_bn,
    count(distinct f.stock_key) as n_stocks
from {{ ref('fact_money_flow') }} f
join {{ ref('dim_time') }} t on t.date_key = f.date_key
join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
where d.security_type = 'STOCK'
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
