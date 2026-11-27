{#- Dataset Superset: giá và dòng tiền theo mã x ngày (mỗi mã mỗi ngày một dòng; khối ngoại, tự doanh, trong nước khác là cột riêng). -#}
{{ config(
    materialized='materialized_view',
    indexes=[{'columns': ['symbol', 'trade_date']}, {'columns': ['trade_date']}]
) }}

with flow as (
    select
        f.stock_key,
        f.trade_date,
        sum(f.net_value_bn) filter (where it.code = 'FOREIGN') as foreign_net_bn,
        sum(f.buy_value_bn) filter (where it.code = 'FOREIGN') as foreign_buy_bn,
        sum(f.sell_value_bn) filter (where it.code = 'FOREIGN') as foreign_sell_bn,
        sum(f.net_value_bn) filter (where it.code = 'PROP') as prop_net_bn,
        sum(f.net_value_bn) filter (where it.code = 'OTHER_DOMESTIC') as other_net_bn
    from {{ ref('fact_money_flow') }} f
    join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
    group by 1, 2
)
select
    p.trade_date,
    d.symbol,
    d.name_vi,
    d.exchange,
    coalesce(d.cap_group, 'unknown') as cap_group,
    d.is_vn30,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    p.close_price,
    p.adj_close_price,
    p.pct_change,
    p.total_value_bn,
    p.matched_volume,
    flow.foreign_net_bn,
    flow.foreign_buy_bn,
    flow.foreign_sell_bn,
    flow.prop_net_bn,
    flow.other_net_bn
from {{ ref('fact_daily_price') }} p
join {{ ref('dim_stock') }} d on d.stock_key = p.stock_key
join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
left join flow on flow.stock_key = p.stock_key and flow.trade_date = p.trade_date
where d.security_type = 'STOCK' and p.has_trading
