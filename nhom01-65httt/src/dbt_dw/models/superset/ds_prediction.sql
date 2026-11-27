{#- Dataset Superset: dự báo chiều dòng tiền khối ngoại của ngành theo tuần, kèm giá trị thực tế (dự báo ngoài mẫu walk-forward).
    Chỉ mô hình dự báo mới nhất. hit = dự báo đúng chiều. -#}
{{ config(materialized='view') }}

with latest as (
    select model_key from {{ ref('dim_model') }} where task = 'forecast' order by trained_at desc limit 1
)
select
    t.date as target_week_start,
    s.icb_l2_code,
    s.icb_l2_name_vi,
    p.predicted_class,
    p.prob_inflow,
    p.predicted_net_value_bn,
    p.actual_class,
    p.actual_net_value_bn,
    (p.predicted_class = p.actual_class)::int as hit,
    p.made_at
from {{ ref('fact_prediction') }} p
join latest using (model_key)
join {{ ref('dim_time') }} t on t.date_key = p.target_week_start_date_key
join {{ ref('dim_sector') }} s on s.sector_key = p.sector_key
