{#- Dataset Superset: dòng tiền ngành ICB cấp 2 x tuần x nhóm nhà đầu tư, kèm tỷ trọng.
    turnover_share_pct = (mua + bán) của ngành / (mua + bán) của toàn thị trường cùng tuần, cùng nhóm NĐT. -#}
{{ config(materialized='view') }}

select
    week_start_date,
    icb_l1_code,
    icb_l2_code,
    icb_l2_name_vi,
    investor_type,
    buy_value_bn,
    sell_value_bn,
    net_value_bn,
    buy_value_bn + sell_value_bn as turnover_bn,
    100.0 * (buy_value_bn + sell_value_bn)
        / nullif(sum(buy_value_bn + sell_value_bn) over (partition by week_start_date, investor_type), 0)
        as turnover_share_pct,
    n_stocks,
    n_days
from {{ ref('mv_sector_weekly_flow') }}
