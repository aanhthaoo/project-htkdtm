-- GROUPING SETS: chọn chính xác các mức tổng hợp cần: (tuần), (tuần, nhóm nhà đầu tư), (nhóm nhà đầu tư), toàn kỳ.
select
    t.week_start_date,
    it.code as investor_type,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join dw.dim_time t on t.date_key = f.date_key
join dw.dim_stock d on d.stock_key = f.stock_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where d.security_type = 'STOCK'
group by grouping sets ((t.week_start_date), (t.week_start_date, it.code), (it.code), ())
order by t.week_start_date, it.code;
