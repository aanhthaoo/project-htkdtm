{#- Nhãn cụm hành vi dòng tiền của cổ phiếu, do mô hình phân cụm (N8) ghi vào.
    Bảng này KHÔNG bao giờ bị dbt xóa nạp lại (incremental + full_refresh: false)
    để dim_stock luôn kết nối được nhãn mới nhất mà không phải chạy lại mô hình. -#}
{{ config(materialized='incremental', unique_key=['symbol', 'model_key'], full_refresh=false) }}

select
    null::varchar as symbol,
    null::bigint as model_key,
    null::varchar as cluster_label,
    null::numeric as silhouette,
    null::timestamptz as assigned_at
where false
