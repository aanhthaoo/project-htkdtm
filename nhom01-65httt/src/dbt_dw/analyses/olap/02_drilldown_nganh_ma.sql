-- DRILL-DOWN: toàn thị trường -> ngành cấp 1 -> ngành cấp 2 -> mã, dòng tiền ròng khối ngoại trong 4 tuần giao dịch gần nhất.
with recent as (
    select date_key
    from dw.dim_time
    where is_trading_day and date <= (select max(trade_date) from dw.fact_money_flow)
    order by date desc
    limit 20
)
select
    s.icb_l1_name_vi,
    s.icb_l2_name_vi,
    d.symbol,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join recent r on r.date_key = f.date_key
join dw.dim_stock d on d.stock_key = f.stock_key
join dw.dim_sector s on s.sector_key = d.sector_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where it.code = 'FOREIGN' and d.security_type = 'STOCK'
group by rollup (s.icb_l1_name_vi, s.icb_l2_name_vi, d.symbol)
order by s.icb_l1_name_vi, s.icb_l2_name_vi, net_value_bn desc;
