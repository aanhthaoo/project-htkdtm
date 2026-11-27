{#- Dataset Superset: bài viết liên quan chứng khoán nhắc tới từng mã, theo phiên giao dịch (mỗi bài x mã một dòng). -#}
{{ config(materialized='view') }}

select
    a.session_date,
    a.publisher,
    a.article_key,
    d.symbol,
    d.exchange,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    b.n_mentions,
    b.in_title
from {{ ref('bridge_article_entity') }} b
join {{ ref('dim_article') }} a on a.article_key = b.article_key
join {{ ref('dim_stock') }} d on d.stock_key = b.stock_key
join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
where b.entity_type = 'STOCK'
  and a.is_market_related and not a.is_duplicate and a.session_date is not null
