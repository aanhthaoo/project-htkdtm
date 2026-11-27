{#- Chỉ số vĩ mô và quốc tế. Grain: 1 chỉ số x 1 kỳ (hiện là ngày; chỉ số tháng/tuần nhập tay thêm sau).
    published_date_key: ngày công bố, dùng khi ghép với dòng tiền để tránh nhìn trước tương lai. -#}
{{ config(
    materialized='incremental',
    unique_key=['indicator_key', 'date_key'],
    incremental_strategy='delete+insert'
) }}

with with_change as (
    select
        indicator_key,
        trade_date,
        value,
        (value / nullif(lag(value) over (partition by indicator_key order by trade_date), 0) - 1) * 100 as pct_change_prev
    from {{ ref('stg_macro_daily') }}
)
select
    {{ date_key('trade_date') }} as date_key,
    trade_date,
    indicator_key,
    value,
    pct_change_prev,
    {{ date_key('trade_date') }} as period_start_date_key,
    {{ date_key('trade_date') }} as period_end_date_key,
    {{ date_key('trade_date') }} as published_date_key,
    'yfinance' as source
from with_change
{% if is_incremental() %}
where trade_date >= (select max(trade_date) from {{ this }}) - {{ var('incremental_lookback_days') }}
{% endif %}
