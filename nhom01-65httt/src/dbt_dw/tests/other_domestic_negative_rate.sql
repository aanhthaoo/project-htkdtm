{#- Tỷ lệ dòng "trong nước khác" phải làm tròn về 0 vì âm không được vượt ngưỡng (0,5%).
    Vượt ngưỡng nghĩa là cách tính tổng giá trị giao dịch có vấn đề. -#}
select rate
from (
    select
        count(*) filter (where f.is_clipped)::numeric / nullif(count(*), 0) as rate
    from {{ ref('fact_money_flow') }} f
    join {{ ref('dim_investor_type') }} it on it.investor_type_key = f.investor_type_key
    where it.code = 'OTHER_DOMESTIC'
) t
where rate > 0.005
