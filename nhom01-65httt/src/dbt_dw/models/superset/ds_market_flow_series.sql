{#- Dataset Superset: chuỗi mua/bán ròng toàn thị trường theo ngày x nhóm nhà đầu tư, có lũy kế và cuốn chiếu 20 phiên.
    Chỉ gồm các ngày có dòng tiền; kèm VN-Index để vẽ cùng. -#}
{{ config(materialized='materialized_view', indexes=[{'columns': ['trade_date']}]) }}

with daily as (
    select
        f.trade_date,
        it.code as investor_type,
        it.name_vi as investor_type_name,
        sum(f.buy_value_bn) as buy_value_bn,
        sum(f.sell_value_bn) as sell_value_bn,
        sum(f.net_value_bn) as net_value_bn
    from {{ ref('fact_money_flow') }} f
    join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
    join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
    where d.security_type = 'STOCK'
    group by 1, 2, 3
)
select
    daily.trade_date,
    daily.investor_type,
    daily.investor_type_name,
    daily.buy_value_bn,
    daily.sell_value_bn,
    daily.net_value_bn,
    sum(daily.net_value_bn) over (partition by daily.investor_type order by daily.trade_date) as cum_net_value_bn,
    sum(daily.net_value_bn) over (
        partition by daily.investor_type order by daily.trade_date rows between 19 preceding and current row
    ) as net_value_20d_bn,
    k.vnindex_close
from daily
left join {{ ref('mv_market_daily_kpi') }} k on k.trade_date = daily.trade_date
