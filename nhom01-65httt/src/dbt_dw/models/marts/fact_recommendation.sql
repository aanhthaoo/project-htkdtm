{#- Khuyến nghị tăng/giảm tỷ trọng ngành theo tuần, do quy tắc N9 (ml.recommend) ghi vào. Grain: 1 ngành x 1 tuần áp dụng x 1 lần chạy quy tắc.
    Giữ cấu trúc ở đây; KHÔNG xóa nạp lại (incremental + full_refresh: false). `signals` là danh sách mã tín hiệu ngăn cách bằng dấu phẩy. -#}
{{ config(
    materialized='incremental',
    unique_key=['sector_key', 'week_start_date_key', 'model_key'],
    full_refresh=false
) }}

select
    null::bigint as sector_key,
    null::int as week_start_date_key,
    null::bigint as model_key,
    null::varchar as action,
    null::varchar as confidence,
    null::double precision as score,
    null::varchar as signals,
    null::varchar as reason,
    null::double precision as prob_inflow,
    null::timestamptz as made_at
where false
