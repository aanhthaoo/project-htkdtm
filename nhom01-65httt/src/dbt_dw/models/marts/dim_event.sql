{#- Sự kiện thị trường (FTSE, MSCI, kỳ cơ cấu ETF...), nhập tay bằng CSV (TV4). Không bao giờ xóa nạp lại. -#}
{{ config(materialized='incremental', unique_key='event_key', full_refresh=false) }}

select
    null::bigint as event_key,
    null::varchar as event_type,
    null::varchar as name,
    null::int as announce_date_key,
    null::int as effective_date_key,
    null::varchar as source
where false
