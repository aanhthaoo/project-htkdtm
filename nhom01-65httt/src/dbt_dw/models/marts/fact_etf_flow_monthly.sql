{#- Dòng vốn ròng vào quỹ ETF theo tháng (số liệu nhập tay, TV4). Grain: 1 quỹ x 1 tháng. -#}
select
    {{ date_key('month_start_date') }} as month_start_date_key,
    month_start_date,
    etf_name,
    net_flow_bn,
    source
from {{ ref('stg_etf_monthly') }}
