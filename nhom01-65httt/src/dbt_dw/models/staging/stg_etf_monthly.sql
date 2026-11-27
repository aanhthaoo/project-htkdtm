{#- Dòng vốn ròng vào quỹ ETF theo tháng (nhập tay), tỷ đồng. -#}
select month_start_date, etf_name, net_flow_bn, source
from {{ source('raw', 'manual_etf_monthly') }}
