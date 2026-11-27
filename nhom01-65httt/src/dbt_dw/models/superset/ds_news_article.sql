{#- Dataset Superset: bài viết theo phiên giao dịch, đã loại bài trùng và bài chưa gán được phiên.
    Cảm xúc sẽ thêm ở N8 (fact_news_sentiment). -#}
{{ config(materialized='view') }}

select
    a.article_key,
    a.session_date,
    a.publisher,
    a.source_type,
    a.category,
    a.title,
    a.url,
    a.is_market_related,
    a.relevance_reason,
    a.n_stock_mentions,
    a.content_chars
from {{ ref('dim_article') }} a
where not a.is_duplicate and a.session_date is not null
