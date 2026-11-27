{#- Dự báo dòng tiền ngành, do mô hình (N8) ghi vào. Grain: 1 ngành x 1 tuần mục tiêu x 1 mô hình x 1 chân trời.
    Giữ cấu trúc ở đây; KHÔNG bao giờ xóa nạp lại (incremental + full_refresh: false) để không mất dự báo cũ. -#}
{{ config(
    materialized='incremental',
    unique_key=['sector_key', 'target_week_start_date_key', 'model_key', 'horizon_weeks', 'made_at'],
    full_refresh=false
) }}

select
    null::bigint as sector_key,
    null::int as target_week_start_date_key,
    null::bigint as model_key,
    null::int as horizon_weeks,
    null::varchar as predicted_class,
    null::double precision as prob_inflow,
    null::double precision as predicted_net_value_bn,
    null::double precision as actual_net_value_bn,
    null::varchar as actual_class,
    null::timestamptz as made_at
where false
