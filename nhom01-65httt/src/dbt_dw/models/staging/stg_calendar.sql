{#- Lịch giao dịch: ngày có >= N mã khớp lệnh ở VNDirect HOẶC có dữ liệu VN-Index ở CafeF.
    Dùng hợp của hai nguồn vì mỗi nguồn từng thiếu một số phiên thật
    (VN-Index CafeF thiếu 17/05/2024 và 03/02/2025). -#}
with vnd as (
    select trade_date
    from {{ source('raw', 'vnd_stock_prices') }}
    where nm_value > 0 and floor in ('HOSE', 'HNX', 'UPCOM')
    group by trade_date
    having count(*) >= {{ var('min_traded_stocks_for_trading_day') }}
),
idx as (
    select trade_date from {{ source('raw', 'cafef_price') }} where symbol = 'VNINDEX'
),
days as (
    select trade_date from vnd union select trade_date from idx
)
select
    d.trade_date,
    (v.trade_date is not null) as in_vndirect,
    (i.trade_date is not null) as in_vnindex,
    lag(d.trade_date) over (order by d.trade_date) as prev_trading_date,
    lead(d.trade_date) over (order by d.trade_date) as next_trading_date
from days d
left join vnd v on v.trade_date = d.trade_date
left join idx i on i.trade_date = d.trade_date
