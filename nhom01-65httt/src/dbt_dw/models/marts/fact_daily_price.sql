{#- Giá hằng ngày. Grain: 1 mã (hoặc VN-Index) x 1 ngày giao dịch.
    Giá cổ phiếu tính bằng đồng; VN-Index tính bằng điểm (dim_stock.security_type = 'INDEX').
    Nạp tăng dần: lấy lại `incremental_lookback_days` ngày gần nhất (nguồn cập nhật trễ). -#}
{{ config(
    materialized='incremental',
    unique_key=['date_key', 'stock_key'],
    incremental_strategy='delete+insert',
    indexes=[{'columns': ['trade_date']}, {'columns': ['stock_key']}]
) }}

with stock_rows as (
    select
        p.trade_date,
        d.stock_key,
        p.open_price, p.high_price, p.low_price, p.close_price, p.adj_close_price, p.ref_price,
        p.pct_change,
        p.matched_volume, p.matched_value_bn,
        p.putthrough_volume, p.putthrough_value_bn,
        p.total_value_bn,
        p.has_trading,
        p.is_outlier_pct,
        false as is_price_repaired
    from {{ ref('stg_price_daily') }} p
    join {{ ref('dim_stock') }} d on d.symbol = p.symbol
),
index_rows as (
    select
        i.trade_date,
        d.stock_key,
        i.open_price, i.high_price, i.low_price, i.close_price, i.adj_close_price,
        lag(i.close_price) over (order by i.trade_date) as ref_price,
        (i.close_price / nullif(lag(i.close_price) over (order by i.trade_date), 0) - 1) * 100 as pct_change,
        i.matched_volume, i.matched_value_bn,
        i.putthrough_volume, i.putthrough_value_bn,
        i.total_value_bn,
        true as has_trading,
        false as is_outlier_pct,
        i.is_price_repaired
    from {{ ref('stg_index_daily') }} i
    join {{ ref('dim_stock') }} d on d.symbol = i.symbol
),
unioned as (
    select * from stock_rows union all select * from index_rows
)
select
    {{ date_key('trade_date') }} as date_key,
    trade_date,
    stock_key,
    open_price, high_price, low_price, close_price, adj_close_price, ref_price,
    pct_change,
    matched_volume, matched_value_bn, putthrough_volume, putthrough_value_bn, total_value_bn,
    has_trading,
    is_outlier_pct,
    is_price_repaired
from unioned
{% if is_incremental() %}
where trade_date >= (select max(trade_date) from {{ this }}) - {{ var('incremental_lookback_days') }}
{% endif %}
