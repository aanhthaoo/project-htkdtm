{#- Với mã-ngày không bị làm tròn về 0: tổng mua (và tổng bán) của 3 nhóm = tổng giá trị giao dịch.
    Kiểm tra tính nhất quán của cách tính nhóm "trong nước khác". -#}
with agg as (
    select
        f.date_key, f.stock_key,
        sum(f.buy_value_bn) as buy_total,
        sum(f.sell_value_bn) as sell_total,
        bool_or(f.is_clipped) as any_clipped
    from {{ ref('fact_money_flow') }} f
    group by f.date_key, f.stock_key
)
select a.date_key, a.stock_key, a.buy_total, a.sell_total, p.total_value_bn
from agg a
join {{ ref('fact_daily_price') }} p on p.date_key = a.date_key and p.stock_key = a.stock_key
where not a.any_clipped
  and p.has_trading
  and (abs(a.buy_total - p.total_value_bn) > 0.001 or abs(a.sell_total - p.total_value_bn) > 0.001)
