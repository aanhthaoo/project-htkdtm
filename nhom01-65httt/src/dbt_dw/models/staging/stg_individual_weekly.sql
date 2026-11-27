{#- Mua/bán của nhà đầu tư cá nhân trong nước theo tuần (nhập tay từ báo cáo tuần), tỷ đồng. -#}
select
    week_start_date,
    buy_value_bn,
    sell_value_bn,
    buy_value_bn - sell_value_bn as net_value_bn,
    source
from {{ source('raw', 'manual_individual_weekly') }}
