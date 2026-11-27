{#- Điểm trong [-1, 1]; độ tin cậy trong [1/3, 1]; nhãn khớp dấu điểm (nhãn tích cực thì điểm > 0, tiêu cực thì điểm < 0).
    Trả về các dòng vi phạm. -#}
select *
from {{ ref('fact_news_sentiment') }}
where sentiment_score < -1 or sentiment_score > 1
   or confidence < 1.0 / 3 - 1e-9 or confidence > 1
   or (sentiment_label = 'positive' and sentiment_score <= 0)
   or (sentiment_label = 'negative' and sentiment_score >= 0)
