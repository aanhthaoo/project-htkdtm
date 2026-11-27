{#- Chỉ số vĩ mô và quốc tế. Grain: 1 chỉ số x 1 kỳ (hiện là ngày; chỉ số tháng/tuần nhập tay thêm sau).
    published_date_key: ngày công bố, dùng khi ghép với dòng tiền để tránh nhìn trước tương lai. -#}
{{ config(
    materialized='incremental',
    unique_key=['indicator_key', 'date_key'],
    incremental_strategy='delete+insert',
    pre_hook="{% if is_incremental() %}delete from {{ this }} where source = 'manual_csv'{% endif %}"
) }}

with daily as (
    select
        indicator_key,
        trade_date as period_start,
        trade_date as period_end,
        trade_date as published_date,
        value,
        'yfinance' as source
    from {{ ref('stg_macro_daily') }}
),
monthly as (  -- số liệu tháng nhập tay: ít dòng nên luôn tính lại toàn bộ (kể cả số công bố muộn của kỳ cũ)
    select indicator_key, period_start, period_end, published_date, value, 'manual_csv' as source
    from {{ ref('stg_macro_manual') }}
),
unioned as (
    select * from daily
    union all
    select * from monthly
),
with_change as (
    select
        *,
        (value / nullif(lag(value) over (partition by indicator_key order by period_end), 0) - 1) * 100 as pct_change_prev
    from unioned
)
select
    {{ date_key('period_end') }} as date_key,
    period_end as trade_date,
    indicator_key,
    value,
    pct_change_prev,
    {{ date_key('period_start') }} as period_start_date_key,
    {{ date_key('period_end') }} as period_end_date_key,
    {{ date_key('published_date') }} as published_date_key,
    source
from with_change
{% if is_incremental() %}
-- thay đổi so với kỳ trước tính trên toàn chuỗi rồi mới lọc; chuỗi ngày chỉ nạp lại vài ngày gần nhất, chuỗi tháng luôn nạp lại
where source <> 'yfinance'
   or period_end >= (select max(trade_date) from {{ this }} where source = 'yfinance') - {{ var('incremental_lookback_days') }}
{% endif %}
