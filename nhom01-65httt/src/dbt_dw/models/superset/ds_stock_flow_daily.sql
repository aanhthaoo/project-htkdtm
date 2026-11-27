{#- Dataset Superset: dòng tiền theo mã x ngày x nhóm nhà đầu tư (top mã gom/xả, drill xuống từng mã). -#}
{{ config(materialized='view') }}

select
    f.trade_date,
    t.week_start_date,
    d.symbol,
    d.name_vi,
    d.exchange,
    coalesce(d.cap_group, 'unknown') as cap_group,
    d.is_vn30,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    it.code as investor_type,
    it.name_vi as investor_type_name,
    f.buy_value_bn,
    f.sell_value_bn,
    f.net_value_bn,
    f.net_volume
from {{ ref('fact_money_flow') }} f
join {{ ref('dim_time') }} t on t.date_key = f.date_key
join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
where d.security_type = 'STOCK'
