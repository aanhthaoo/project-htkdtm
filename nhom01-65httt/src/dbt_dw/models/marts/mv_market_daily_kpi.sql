{#- Tổng hợp sẵn: KPI toàn thị trường theo ngày (nguồn của dashboard Tổng quan). -#}
{{ config(
    materialized='materialized_view',
    indexes=[{'columns': ['trade_date']}]
) }}

with flow as (
    select
        f.trade_date,
        sum(f.buy_value_bn) filter (where it.code = 'FOREIGN') as foreign_buy_bn,
        sum(f.sell_value_bn) filter (where it.code = 'FOREIGN') as foreign_sell_bn,
        sum(f.net_value_bn) filter (where it.code = 'FOREIGN') as foreign_net_bn,
        sum(f.net_value_bn) filter (where it.code = 'PROP') as prop_net_bn,
        sum(f.net_value_bn) filter (where it.code = 'OTHER_DOMESTIC') as other_net_bn
    from {{ ref('fact_money_flow') }} f
    join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
    join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
    where d.security_type = 'STOCK'
    group by f.trade_date
),
px as (
    select
        p.trade_date,
        sum(p.total_value_bn) filter (where d.security_type = 'STOCK') as stock_value_bn,
        count(*) filter (where d.security_type = 'STOCK' and p.has_trading) as n_traded_stocks,
        max(p.close_price) filter (where d.security_type = 'INDEX') as vnindex_close,
        max(p.pct_change) filter (where d.security_type = 'INDEX') as vnindex_pct_change
    from {{ ref('fact_daily_price') }} p
    join {{ ref('dim_stock') }} d on d.stock_key = p.stock_key
    group by p.trade_date
)
select
    px.trade_date,
    px.stock_value_bn,
    px.n_traded_stocks,
    px.vnindex_close,
    px.vnindex_pct_change,
    flow.foreign_buy_bn,
    flow.foreign_sell_bn,
    flow.foreign_net_bn,
    flow.prop_net_bn,
    flow.other_net_bn
from px
left join flow on flow.trade_date = px.trade_date
