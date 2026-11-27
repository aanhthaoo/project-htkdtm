{#- Chiều cổ phiếu (gồm cả chỉ số VN-Index để dùng chung fact_daily_price).
    - Vốn hóa, số cổ phiếu, ngành là ảnh chụp HIỆN TẠI từ Vietcap iQ, áp dụng cho cả lịch sử.
    - cap_group chia theo ngưỡng vốn hóa trong dbt_project.yml.
    - liquidity_group: tứ phân vị (L1 thấp nhất, L4 cao nhất) của giá trị giao dịch trung bình 60 phiên gần nhất. -#}
{{ config(materialized='table') }}

with last_days as (
    select trade_date
    from {{ ref('stg_calendar') }}
    order by trade_date desc
    limit 60
),
liq as (
    select
        p.symbol,
        avg(p.total_value_bn) as avg_value_bn_60d
    from {{ ref('stg_price_daily') }} p
    join last_days d on d.trade_date = p.trade_date
    group by p.symbol
    having avg(p.total_value_bn) > 0
),
liq_group as (
    select symbol, avg_value_bn_60d, 'L' || ntile(4) over (order by avg_value_bn_60d) as liquidity_group
    from liq
),
latest_cluster as (
    select distinct on (symbol) symbol, cluster_label, model_key as cluster_model_key
    from {{ ref('stock_cluster') }}
    order by symbol, assigned_at desc
),
sector as (
    select sector_key, sector_code from {{ ref('dim_sector') }}
),
stocks as (
    select
        m.symbol,
        {{ surrogate_key('m.symbol') }} as stock_key,
        m.name_vi,
        m.short_name,
        m.exchange,
        'STOCK' as security_type,
        coalesce(
            (select s.sector_key from sector s where s.sector_code = m.icb_lv4),
            (select s.sector_key from sector s where s.sector_code = m.icb_lv2 || '_NA'),
            (select s.sector_key from sector s where s.sector_code = 'UNCLASSIFIED')
        ) as sector_key,
        m.icb_lv2,
        m.icb_lv4,
        m.listing_date,
        m.delisted_date,
        m.first_trade_date,
        m.last_trade_date,
        m.is_listed as is_active,
        m.issue_shares,
        m.market_cap_bn,
        case
            when m.market_cap_bn >= {{ var('cap_large_min_bn') }} then 'large'
            when m.market_cap_bn >= {{ var('cap_mid_min_bn') }} then 'mid'
            when m.market_cap_bn is not null then 'small'
        end as cap_group,
        case
            when m.in_vn30 then 'VN30'
            when m.in_vnmidcap then 'VNMidCap'
            when m.in_vnsmallcap then 'VNSmallCap'
            when m.in_hnx30 then 'HNX30'
        end as index_group,
        m.in_vn30 as is_vn30,
        m.max_foreign_pct
    from {{ ref('stg_stock_master') }} m
),
index_row as (
    select
        'VNINDEX' as symbol,
        {{ surrogate_key("'VNINDEX'") }} as stock_key,
        'VN-Index' as name_vi, 'VN-Index' as short_name, 'HOSE' as exchange,
        'INDEX' as security_type,
        (select s.sector_key from sector s where s.sector_code = 'UNCLASSIFIED') as sector_key,
        null::varchar as icb_lv2, null::varchar as icb_lv4,
        null::date as listing_date, null::date as delisted_date,
        null::date as first_trade_date, null::date as last_trade_date,
        true as is_active, null::double precision as issue_shares, null::double precision as market_cap_bn,
        null::text as cap_group, null::text as index_group, false as is_vn30,
        null::double precision as max_foreign_pct
)
select
    s.*,
    l.liquidity_group,
    l.avg_value_bn_60d,
    c.cluster_label,
    c.cluster_model_key
from (select * from stocks union all select * from index_row) s
left join liq_group l on l.symbol = s.symbol
left join latest_cluster c on c.symbol = s.symbol
