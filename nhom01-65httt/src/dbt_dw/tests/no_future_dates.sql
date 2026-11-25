{#- Không có dữ liệu giao dịch ở tương lai. -#}
select 'price' as fact, trade_date from {{ ref('fact_daily_price') }} where trade_date > current_date
union all
select 'flow', trade_date from {{ ref('fact_money_flow') }} where trade_date > current_date
