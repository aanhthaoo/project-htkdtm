{#- Giá cao nhất không được thấp hơn giá thấp nhất. -#}
select date_key, stock_key, high_price, low_price
from {{ ref('fact_daily_price') }}
where high_price < low_price
