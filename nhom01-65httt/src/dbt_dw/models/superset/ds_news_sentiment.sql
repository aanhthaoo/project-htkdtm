{#- Dataset Superset: cảm xúc tin tức theo phiên giao dịch (mỗi bài x mã hoặc ngành được nhắc một dòng).
    Điểm = P(tích cực) - P(tiêu cực) trong [-1, 1]. Cảm xúc ở mức bài: mọi mã/ngành của cùng một bài có cùng điểm. -#}
{{ config(materialized='view') }}

select
    f.session_date_key,
    t.date as session_date,
    t.week_start_date,
    f.entity_type,
    f.entity_code,
    d.symbol,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    a.publisher,
    f.article_key,
    f.sentiment_label,
    f.sentiment_score,
    f.confidence
from {{ ref('fact_news_sentiment') }} f
join {{ ref('dim_time') }} t on t.date_key = f.session_date_key
join {{ ref('dim_article') }} a on a.article_key = f.article_key
left join {{ ref('dim_stock') }} d on d.stock_key = f.stock_key
left join lateral (
    select icb_l2_code, icb_l2_name_vi from {{ ref('dim_sector') }}
    where icb_l2_code = f.icb_l2_code and sector_code = f.icb_l2_code || '_NA' limit 1
) s on true
