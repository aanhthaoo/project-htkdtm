{#- Cầu nối bài báo - thực thể được nhắc. Grain: 1 bài x 1 mã cổ phiếu hoặc 1 ngành ICB cấp 2.
    entity_type = STOCK: stock_key; entity_type = SECTOR: icb_l2_code.
    Đây là đầu vào của bước tính cảm xúc theo mã/ngành (fact_news_sentiment). -#}
{{ config(materialized='table', indexes=[{'columns': ['article_key']}, {'columns': ['stock_key']}, {'columns': ['icb_l2_code']}]) }}

select
    art.article_key,
    m.entity_type,
    m.entity_code,
    case when m.entity_type = 'STOCK' then d.stock_key end as stock_key,
    case when m.entity_type = 'SECTOR' then m.entity_code end as icb_l2_code,
    sum(m.n_mentions) as n_mentions,
    bool_or(m.in_title) as in_title,
    string_agg(distinct m.method, ',' order by m.method) as methods
from {{ source('stg_python', 'news_mention') }} m
join {{ ref('dim_article') }} art on art.article_id = m.article_id
left join {{ ref('dim_stock') }} d on m.entity_type = 'STOCK' and d.symbol = m.entity_code
where m.entity_type = 'SECTOR' or d.stock_key is not null
group by art.article_key, m.entity_type, m.entity_code, d.stock_key
