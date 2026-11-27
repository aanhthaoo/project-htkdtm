{#- Danh mục mã cổ phiếu: hợp danh sách Vietcap (type = STOCK) và mọi mã xuất hiện trong giá VNDirect.
    Thông tin công ty (ICB cấp 4, vốn hóa, số cổ phiếu) từ Vietcap iQ; nếu chưa có thì dùng ICB cấp 2 từ getAll. -#}
with sym as (
    select symbol, board, organ_name, organ_short_name, icb_code2
    from {{ source('raw', 'vietcap_symbols') }}
    where type = 'STOCK'
),
px as (
    select
        code,
        min(trade_date) as first_trade_date,
        max(trade_date) as last_trade_date,
        (array_agg(floor order by trade_date desc))[1] as last_floor
    from {{ source('raw', 'vnd_stock_prices') }}
    group by code
),
grp as (
    select
        symbol,
        bool_or(group_name = 'VN30') as in_vn30,
        bool_or(group_name = 'VN100') as in_vn100,
        bool_or(group_name = 'VNMidCap') as in_vnmidcap,
        bool_or(group_name = 'VNSmallCap') as in_vnsmallcap,
        bool_or(group_name = 'HNX30') as in_hnx30
    from {{ source('raw', 'vietcap_groups') }}
    group by symbol
),
codes as (
    select symbol as code from sym
    union
    select code from px
)
select
    c.code as symbol,
    coalesce(s.organ_name, s.organ_short_name) as name_vi,
    s.organ_short_name as short_name,
    case
        when s.board = 'HSX' then 'HOSE'
        when s.board in ('HNX', 'UPCOM') then s.board
        else px.last_floor
    end as exchange,
    coalesce(s.board in ('HSX', 'HNX', 'UPCOM'), false) as is_listed,
    coalesce(co.icb_code_lv2, s.icb_code2) as icb_lv2,
    co.icb_code_lv4 as icb_lv4,
    co.listing_date,
    case
        when coalesce(s.board in ('HSX', 'HNX', 'UPCOM'), false) then null
        else px.last_trade_date
    end as delisted_date,
    px.first_trade_date,
    px.last_trade_date,
    co.issue_share as issue_shares,
    co.market_cap / 1e9 as market_cap_bn,
    co.max_foreign_pct,
    coalesce(g.in_vn30, false) as in_vn30,
    coalesce(g.in_vn100, false) as in_vn100,
    coalesce(g.in_vnmidcap, false) as in_vnmidcap,
    coalesce(g.in_vnsmallcap, false) as in_vnsmallcap,
    coalesce(g.in_hnx30, false) as in_hnx30
from codes c
left join sym s on s.symbol = c.code
left join px on px.code = c.code
left join {{ source('raw', 'vietcap_company') }} co on co.symbol = c.code
left join grp g on g.symbol = c.code
-- Bỏ mã không niêm yết và không có giá trong khoảng dữ liệu (ví dụ mã hủy niêm yết trước 09/2020)
where coalesce(s.board in ('HSX', 'HNX', 'UPCOM'), false) or px.code is not null
