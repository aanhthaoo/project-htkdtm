{#- Cảm xúc tin tức. Grain: 1 bài x 1 mã hoặc 1 ngành được nhắc. Do mô hình cảm xúc (N8) ghi vào.
    Giữ cấu trúc ở đây; KHÔNG bao giờ xóa nạp lại (incremental + full_refresh: false). -#}
{{ config(
    materialized='incremental',
    unique_key=['article_key', 'entity_type', 'entity_code', 'model_key'],
    full_refresh=false
) }}

select
    null::bigint as article_key,
    null::int as session_date_key,
    null::varchar as entity_type,
    null::varchar as entity_code,
    null::bigint as stock_key,
    null::varchar as icb_l2_code,
    null::double precision as sentiment_score,
    null::varchar as sentiment_label,
    null::double precision as confidence,
    null::bigint as model_key,
    null::timestamptz as scored_at
where false
