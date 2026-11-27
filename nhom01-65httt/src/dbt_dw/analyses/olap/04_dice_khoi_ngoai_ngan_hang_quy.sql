-- DICE: khối ngoại x ngành Ngân hàng (ICB cấp 2 = 8300) x quý 3/2025, theo mã.
select
    d.symbol,
    sum(f.buy_value_bn) as buy_value_bn,
    sum(f.sell_value_bn) as sell_value_bn,
    sum(f.net_value_bn) as net_value_bn
from dw.fact_money_flow f
join dw.dim_time t on t.date_key = f.date_key
join dw.dim_stock d on d.stock_key = f.stock_key
join dw.dim_sector s on s.sector_key = d.sector_key
join dw.dim_investor_type it on it.investor_type_key = f.investor_type_key
where it.code = 'FOREIGN'
  and s.icb_l2_code = '8300'
  and t.year = 2025 and t.quarter = 3
group by d.symbol
order by net_value_bn desc;
