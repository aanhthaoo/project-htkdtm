{{ config(severity='warn') }}
{#- Phân bố nhãn không lệch cực đoan: mỗi lớp chiếm từ 5% đến 80% số bài. -#}
with by_label as (
    select sentiment_label, count(distinct article_key) as n from {{ ref('fact_news_sentiment') }} group by 1
),
total as (select sum(n) as n from by_label)
select by_label.* from by_label, total
where by_label.n < 0.05 * total.n or by_label.n > 0.80 * total.n
   or (select count(*) from by_label) < 3
