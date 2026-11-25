{#- Mô hình học máy (N8 ghi vào). Không bao giờ xóa nạp lại. -#}
{{ config(materialized='incremental', unique_key='model_key', full_refresh=false) }}

select
    null::bigint as model_key,
    null::varchar as name,
    null::varchar as task,
    null::varchar as version,
    null::timestamptz as trained_at,
    null::varchar as train_range,
    null::jsonb as metrics
where false
