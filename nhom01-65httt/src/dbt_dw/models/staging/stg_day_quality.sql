{#- Chất lượng theo ngày giao dịch: số mã có giá, có giao dịch, có khối ngoại hoạt động, số dòng tự doanh.
    is_foreign_complete quyết định ngày nào được đưa vào dòng tiền
    (xem docs/ke_hoach_thu_thap_hang_ngay.md). -#}
with price as (
    select trade_date, count(*) as n_priced, count(*) filter (where has_trading) as n_traded
    from {{ ref('stg_price_daily') }}
    group by trade_date
),
foreign_ as (
    select trade_date, count(*) filter (where buy_val + sell_val > 0) as n_foreign_active
    from {{ source('raw', 'vnd_foreigns') }}
    group by trade_date
),
prop as (
    select trade_date, count(*) as n_prop_rows
    from {{ source('raw', 'vnd_proprietary') }}
    group by trade_date
)
select
    c.trade_date,
    coalesce(p.n_priced, 0) as n_priced,
    coalesce(p.n_traded, 0) as n_traded,
    coalesce(f.n_foreign_active, 0) as n_foreign_active,
    coalesce(r.n_prop_rows, 0) as n_prop_rows,
    coalesce(f.n_foreign_active, 0) >= {{ var('min_foreign_active_stocks') }} as is_foreign_complete,
    (c.trade_date >= '{{ var("prop_history_start") }}'::date) as is_prop_expected,
    (
        c.trade_date >= '{{ var("prop_history_start") }}'::date
        and coalesce(r.n_prop_rows, 0) = 0
    ) as is_prop_missing
from {{ ref('stg_calendar') }} c
left join price p on p.trade_date = c.trade_date
left join foreign_ f on f.trade_date = c.trade_date
left join prop r on r.trade_date = c.trade_date
