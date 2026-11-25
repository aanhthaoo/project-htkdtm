{#- Chiều bài báo (không chứa toàn văn: toàn văn nằm ở stg.news_article cho mô hình và chatbot).
    Website chỉ hiển thị tiêu đề, nhãn cảm xúc, nguồn và đường dẫn về bài gốc.
    Dùng bài: is_market_related AND NOT is_duplicate AND session_date_key IS NOT NULL. -#}
{{ config(materialized='table', indexes=[{'columns': ['session_date_key']}, {'columns': ['article_id'], 'unique': true}]) }}

select
    {{ surrogate_key('a.article_id') }} as article_key,
    a.article_id,
    a.url,
    a.title,
    a.category,
    a.published_at,
    a.published_date,
    a.time_known,
    a.session_date,
    {{ date_key('a.session_date') }} as session_date_key,
    s.source_key,
    a.source as publisher,
    a.source_type,
    a.content_chars,
    a.is_market_related,
    a.relevance_reason,
    a.n_stock_mentions,
    a.is_duplicate,
    a.dup_reason
from {{ source('stg_python', 'news_article') }} a
left join {{ ref('dim_source') }} s on s.publisher = a.source and s.source_type = a.source_type
