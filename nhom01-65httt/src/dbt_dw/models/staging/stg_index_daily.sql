{#- VN-Index (CafeF): điểm chỉ số và giá trị giao dịch (tỷ đồng). -#}
select
    symbol,
    trade_date,
    open_k as open_price,
    greatest(open_k, high_k, low_k, close_k) as high_price,
    least(open_k, high_k, low_k, close_k) as low_price,
    close_k as close_price,
    -- Nguồn có dòng sai (VN-Index 08/06/2026: cao < thấp < ... < đóng cửa): sửa về biên của 4 giá và gắn cờ
    (high_k < greatest(open_k, low_k, close_k) or low_k > least(open_k, high_k, close_k)) as is_price_repaired,
    close_k as adj_close_price,
    matched_volume,
    matched_value_bn,
    putthrough_volume,
    putthrough_value_bn,
    coalesce(matched_value_bn, 0) + coalesce(putthrough_value_bn, 0) as total_value_bn,
    fetched_at
from {{ source('raw', 'cafef_price') }}
where symbol = 'VNINDEX'
