{#- Giá trị ròng phải bằng mua trừ bán (dung sai làm tròn). -#}
select date_key, stock_key, investor_type_key, buy_value_bn, sell_value_bn, net_value_bn
from {{ ref('fact_money_flow') }}
where abs(net_value_bn - (buy_value_bn - sell_value_bn)) > 0.000001
