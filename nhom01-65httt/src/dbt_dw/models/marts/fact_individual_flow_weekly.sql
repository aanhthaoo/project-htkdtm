{#- Mua/bán ròng của nhà đầu tư cá nhân trong nước toàn thị trường theo tuần (số liệu nhập tay, TV4). Grain: 1 tuần. -#}
select
    {{ date_key('week_start_date') }} as week_start_date_key,
    week_start_date,
    buy_value_bn,
    sell_value_bn,
    net_value_bn,
    source
from {{ ref('stg_individual_weekly') }}
