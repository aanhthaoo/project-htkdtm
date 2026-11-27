{#- Dòng tiền. Grain: 1 mã x 1 ngày giao dịch x 1 nhóm nhà đầu tư.
    Chỉ gồm ngày khối ngoại "đủ" (stg_day_quality.is_foreign_complete). Không có dòng nghĩa là bằng 0.
    Đơn vị: tỷ đồng và cổ phiếu. Nạp tăng dần như fact_daily_price. -#}
{{ config(
    materialized='incremental',
    unique_key=['date_key', 'stock_key', 'investor_type_key'],
    incremental_strategy='delete+insert',
    indexes=[{'columns': ['trade_date']}, {'columns': ['stock_key']}]
) }}

select
    {{ date_key('f.trade_date') }} as date_key,
    f.trade_date,
    d.stock_key,
    it.investor_type_key,
    f.buy_value_bn,
    f.sell_value_bn,
    f.buy_value_bn - f.sell_value_bn as net_value_bn,
    f.buy_volume,
    f.sell_volume,
    f.buy_volume - f.sell_volume as net_volume,
    f.includes_prop,
    f.is_clipped
from {{ ref('stg_flow_daily') }} f
join {{ ref('dim_stock') }} d on d.symbol = f.symbol
join {{ ref('dim_investor_type') }} it on it.code = f.investor_type
{% if is_incremental() %}
where f.trade_date >= (select max(trade_date) from {{ this }}) - {{ var('incremental_lookback_days') }}
{% endif %}
