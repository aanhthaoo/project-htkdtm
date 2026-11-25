-- ROLL-UP: dòng tiền ròng khối ngoại theo năm -> tháng -> tuần (một truy vấn cho cả ba mức và tổng toàn kỳ).
-- Dòng có tuần NULL là tổng tháng; tháng NULL là tổng năm; năm NULL là tổng toàn kỳ.
select
    t.year,
    t.month,
    t.week_start_date,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join dw.dim_time t on t.date_key = f.date_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where it.code = 'FOREIGN'
group by rollup (t.year, t.month, t.week_start_date)
order by t.year, t.month, t.week_start_date;
