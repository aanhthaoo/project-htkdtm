-- CUBE: mọi tổ hợp tổng hợp giữa ngành cấp 2 và nhóm nhà đầu tư, tháng gần nhất có dữ liệu.
-- NULL ở cột nào nghĩa là gộp mọi giá trị của cột đó (grouping() cho biết cột nào đã gộp).
select
    s.icb_l2_name_vi,
    it.code as investor_type,
    grouping(s.icb_l2_name_vi) as g_sector,
    grouping(it.code) as g_investor,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join dw.dim_time t on t.date_key = f.date_key
join dw.dim_stock d on d.stock_key = f.stock_key
join dw.dim_sector s on s.sector_key = d.sector_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where t.month_start_date = (select max(month_start_date) from dw.dim_time where date <= (select max(trade_date) from dw.fact_money_flow))
  and d.security_type = 'STOCK'
group by cube (s.icb_l2_name_vi, it.code)
order by g_sector, g_investor, s.icb_l2_name_vi, it.code;
