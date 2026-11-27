{#- Giá hằng ngày đã chuẩn hóa: giá về đồng, giá trị về tỷ đồng; chỉ giữ ngày giao dịch và 3 sàn chính. -#}
select
    p.code as symbol,
    p.trade_date,
    p.floor as exchange,
    p.open * 1000 as open_price,
    p.high * 1000 as high_price,
    p.low * 1000 as low_price,
    p.close * 1000 as close_price,
    p.ad_close * 1000 as adj_close_price,
    p.basic_price * 1000 as ref_price,
    p.pct_change,
    p.nm_volume as matched_volume,
    p.nm_value / 1e9 as matched_value_bn,
    p.pt_volume as putthrough_volume,
    p.pt_value / 1e9 as putthrough_value_bn,
    (p.nm_value + p.pt_value) / 1e9 as total_value_bn,
    (p.nm_volume + p.pt_volume) as total_volume,
    (p.nm_value + p.pt_value) > 0 as has_trading,
    abs(p.pct_change) > {{ var('flag_abs_pct_change_over') }} as is_outlier_pct,
    p.fetched_at
from {{ source('raw', 'vnd_stock_prices') }} p
join {{ ref('stg_calendar') }} cal on cal.trade_date = p.trade_date
where p.floor in ('HOSE', 'HNX', 'UPCOM')
