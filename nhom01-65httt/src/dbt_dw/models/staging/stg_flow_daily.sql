{#- Dòng tiền theo mã, ngày, nhóm nhà đầu tư (đơn vị tỷ đồng). Chỉ gồm ngày khối ngoại "đủ".
    - FOREIGN, PROP: lấy từ VNDirect (gồm giao dịch thỏa thuận); chỉ lưu dòng có giao dịch (không có dòng = 0).
    - OTHER_DOMESTIC: tổng giá trị giao dịch (khớp lệnh + thỏa thuận) - khối ngoại - tự doanh,
      tính cho mọi mã có giao dịch. Mỗi giao dịch có một bên mua và một bên bán nên
      tổng mua = tổng bán = tổng giá trị giao dịch.
    - includes_prop: trước ngày có dữ liệu tự doanh (17/05/2022) nhóm này gộp cả tự doanh.
    - is_clipped: phần dư âm (nguồn lệch nhỏ) được đưa về 0 và gắn cờ. -#}
with good_days as (
    select trade_date from {{ ref('stg_day_quality') }} where is_foreign_complete
),
px as (
    select p.symbol, p.trade_date, p.total_value_bn, p.total_volume
    from {{ ref('stg_price_daily') }} p
    join good_days g on g.trade_date = p.trade_date
    where p.has_trading
),
f as (
    select
        code as symbol, trade_date,
        buy_val / 1e9 as buy_value_bn, sell_val / 1e9 as sell_value_bn,
        buy_vol as buy_volume, sell_vol as sell_volume
    from {{ source('raw', 'vnd_foreigns') }}
    where buy_val + sell_val > 0
),
r as (
    select
        code as symbol, trade_date,
        buying_val / 1e9 as buy_value_bn, selling_val / 1e9 as sell_value_bn,
        buying_vol as buy_volume, selling_vol as sell_volume
    from {{ source('raw', 'vnd_proprietary') }}
    where buying_val + selling_val > 0
),
foreign_rows as (
    select f.symbol, f.trade_date, 'FOREIGN' as investor_type,
           f.buy_value_bn, f.sell_value_bn, f.buy_volume, f.sell_volume,
           false as includes_prop, false as is_clipped
    from f
    join good_days g on g.trade_date = f.trade_date
    join {{ ref('stg_stock_master') }} m on m.symbol = f.symbol
),
prop_rows as (
    select r.symbol, r.trade_date, 'PROP' as investor_type,
           r.buy_value_bn, r.sell_value_bn, r.buy_volume, r.sell_volume,
           false as includes_prop, false as is_clipped
    from r
    join good_days g on g.trade_date = r.trade_date
    join {{ ref('stg_stock_master') }} m on m.symbol = r.symbol
),
other_raw as (
    select
        px.symbol, px.trade_date,
        px.total_value_bn - coalesce(f.buy_value_bn, 0) - coalesce(r.buy_value_bn, 0) as buy_value_bn,
        px.total_value_bn - coalesce(f.sell_value_bn, 0) - coalesce(r.sell_value_bn, 0) as sell_value_bn,
        px.total_volume - coalesce(f.buy_volume, 0) - coalesce(r.buy_volume, 0) as buy_volume,
        px.total_volume - coalesce(f.sell_volume, 0) - coalesce(r.sell_volume, 0) as sell_volume,
        (px.trade_date < '{{ var("prop_history_start") }}'::date) as includes_prop
    from px
    left join f on f.symbol = px.symbol and f.trade_date = px.trade_date
    left join r on r.symbol = px.symbol and r.trade_date = px.trade_date
    join {{ ref('stg_stock_master') }} m on m.symbol = px.symbol
),
other_rows as (
    select
        symbol, trade_date, 'OTHER_DOMESTIC' as investor_type,
        greatest(buy_value_bn, 0) as buy_value_bn, greatest(sell_value_bn, 0) as sell_value_bn,
        greatest(buy_volume, 0) as buy_volume, greatest(sell_volume, 0) as sell_volume,
        includes_prop,
        (buy_value_bn < 0 or sell_value_bn < 0 or buy_volume < 0 or sell_volume < 0) as is_clipped
    from other_raw
)
select * from foreign_rows
union all select * from prop_rows
union all select * from other_rows
