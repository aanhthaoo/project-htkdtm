{#- Chiều thời gian: mỗi ngày dương lịch từ 01/09/2020 đến hết năm sau.
    session_on_or_after: phiên giao dịch đầu tiên từ ngày đó trở đi (dùng gán tin chỉ có ngày đăng).
    next_trading_date: phiên giao dịch đầu tiên SAU ngày đó (dùng gán tin đăng sau 15h). -#}
{{ config(materialized='table') }}

with spine as (
    select d::date as d
    from generate_series(
        '2020-09-01'::date,
        (date_trunc('year', current_date) + interval '2 years' - interval '1 day')::date,
        interval '1 day'
    ) as d
),
cal as (
    select trade_date from {{ ref('stg_calendar') }}
),
last_trading as (
    select max(trade_date) as d from cal
)
select
    {{ date_key('s.d') }} as date_key,
    s.d as date,
    extract(isodow from s.d)::int as day_of_week,
    (array['Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy', 'Chủ nhật'])[extract(isodow from s.d)::int] as day_name_vi,
    date_trunc('week', s.d)::date as week_start_date,
    {{ date_key("date_trunc('week', s.d)::date") }} as week_key,
    extract(isoyear from s.d)::int as iso_year,
    extract(week from s.d)::int as iso_week,
    date_trunc('month', s.d)::date as month_start_date,
    extract(month from s.d)::int as month,
    extract(quarter from s.d)::int as quarter,
    extract(year from s.d)::int as year,
    extract(isodow from s.d) in (6, 7) as is_weekend,
    exists (select 1 from cal c where c.trade_date = s.d) as is_trading_day,
    (
        extract(isodow from s.d) < 6
        and s.d <= (select d from last_trading)
        and not exists (select 1 from cal c where c.trade_date = s.d)
    ) as is_holiday,
    (select min(c.trade_date) from cal c where c.trade_date >= s.d) as session_on_or_after,
    (select min(c.trade_date) from cal c where c.trade_date > s.d) as next_trading_date,
    (select max(c.trade_date) from cal c where c.trade_date < s.d) as prev_trading_date
from spine s
