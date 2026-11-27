{#- Dataset Superset: chỉ số vĩ mô và quốc tế THEO NGÀY (chỉ số tháng nhập tay nằm ở fact_macro_indicator với source = 'manual_csv' và có published_date; không đưa vào đây để mô hình không dùng số liệu trước ngày công bố). -#}
{{ config(materialized='view') }}

select
    m.trade_date,
    i.code as indicator_code,
    i.name_vi as indicator_name,
    i.unit,
    i.scope,
    m.value,
    m.pct_change_prev
from {{ ref('fact_macro_indicator') }} m
join {{ ref('dim_indicator') }} i on i.indicator_key = m.indicator_key
where i.frequency = 'daily'
