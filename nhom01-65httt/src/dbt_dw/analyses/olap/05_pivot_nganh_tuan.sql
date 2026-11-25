-- PIVOT: ngành (hàng) x tuần (cột), dòng tiền ròng khối ngoại, 6 tuần gần nhất. Đổi chỗ hàng và cột chỉ cần đổi cách nhóm.
with weeks as (
    select distinct week_start_date
    from dw.dim_time
    where date <= (select max(trade_date) from dw.fact_money_flow) and is_trading_day
    order by week_start_date desc
    limit 6
),
base as (
    select s.icb_l2_name_vi, t.week_start_date, sum(f.net_value_bn) as net_value_bn
    from dw.fact_money_flow f
    join dw.dim_time t on t.date_key = f.date_key
    join weeks w on w.week_start_date = t.week_start_date
    join dw.dim_stock d on d.stock_key = f.stock_key
    join dw.dim_sector s on s.sector_key = d.sector_key
    join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
    where it.code = 'FOREIGN'
    group by s.icb_l2_name_vi, t.week_start_date
),
ordered as (select week_start_date, dense_rank() over (order by week_start_date desc) as rk from weeks)
select
    b.icb_l2_name_vi,
    sum(b.net_value_bn) filter (where o.rk = 6) as w_minus_5,
    sum(b.net_value_bn) filter (where o.rk = 5) as w_minus_4,
    sum(b.net_value_bn) filter (where o.rk = 4) as w_minus_3,
    sum(b.net_value_bn) filter (where o.rk = 3) as w_minus_2,
    sum(b.net_value_bn) filter (where o.rk = 2) as w_minus_1,
    sum(b.net_value_bn) filter (where o.rk = 1) as w_latest,
    sum(b.net_value_bn) as total
from base b
join ordered o on o.week_start_date = b.week_start_date
group by b.icb_l2_name_vi
order by total;
