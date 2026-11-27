{#- Mọi bài đã gán mã/ngành (bài liên quan, không trùng, đã gán phiên) phải có dòng cảm xúc cho từng mã/ngành được nhắc. -#}
select b.article_key, b.entity_type, b.entity_code
from {{ ref('bridge_article_entity') }} b
join {{ ref('dim_article') }} a on a.article_key = b.article_key
left join {{ ref('fact_news_sentiment') }} f
  on f.article_key = b.article_key and f.entity_type = b.entity_type and f.entity_code = b.entity_code
where a.is_market_related and not a.is_duplicate and a.session_date is not null
  and f.article_key is null
