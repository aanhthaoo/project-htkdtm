{#- Cảnh báo: số phiên mà VNDirect và VN-Index CafeF không thống nhất (trong khoảng đã nạp giá) vượt 5.
    Hiện biết 2 phiên VN-Index CafeF thiếu (17/05/2024 và 03/02/2025). -#}
{{ config(severity='warn') }}
select disagreements
from (
    select count(*) as disagreements
    from {{ ref('stg_calendar') }}
    where in_vndirect <> in_vnindex
      and trade_date <= (select max(trade_date) from {{ ref('stg_price_daily') }})
) t
where disagreements > 5
