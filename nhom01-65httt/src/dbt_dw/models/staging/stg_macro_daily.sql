{#- Chỉ số quốc tế hằng ngày (yfinance), giữ đúng ngày của nguồn (chưa điền ngày nghỉ). -#}
select
    i.indicator_key,
    y.ticker,
    y.trade_date,
    y.close as value
from {{ source('raw', 'yf_prices') }} y
join {{ ref('seed_indicator') }} i on i.source_code = y.ticker
where y.close is not null
