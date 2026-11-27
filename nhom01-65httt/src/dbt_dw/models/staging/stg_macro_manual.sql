{#- Vĩ mô theo tháng nhập tay (CSV). Kỳ là tháng của period_end; published_date là ngày công bố (dùng để không nhìn trước tương lai). -#}
select
    i.indicator_key,
    m.indicator_code,
    date_trunc('month', m.period_end)::date as period_start,
    m.period_end,
    m.value,
    m.published_date,
    m.source
from {{ source('raw', 'manual_macro_monthly') }} m
join {{ ref('seed_indicator') }} i on i.code = m.indicator_code
