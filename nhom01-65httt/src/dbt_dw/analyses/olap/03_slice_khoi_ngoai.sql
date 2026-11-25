-- SLICE: chỉ xem giao dịch của khối ngoại (cố định chiều nhóm nhà đầu tư), theo ngành cấp 2 và tuần, 8 tuần gần nhất.
select
    t.week_start_date,
    s.icb_l2_name_vi,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join dw.dim_time t on t.date_key = f.date_key
join dw.dim_stock d on d.stock_key = f.stock_key
join dw.dim_sector s on s.sector_key = d.sector_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where it.code = 'FOREIGN'
  and t.week_start_date >= (select max(week_start_date) from dw.dim_time where date <= (select max(trade_date) from dw.fact_money_flow)) - 49
group by t.week_start_date, s.icb_l2_name_vi
order by t.week_start_date, net_value_bn desc;
