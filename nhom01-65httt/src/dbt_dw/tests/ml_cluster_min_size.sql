{{ config(severity='warn') }}
{#- Cụm học được (không tính nhãn quy tắc) không nhỏ hơn 1% số mã được phân cụm. -#}
with learned as (
    select cluster_label, count(*) as n
    from {{ ref('dim_stock') }}
    where security_type = 'STOCK'
      and cluster_label not in ('thanh_khoan_thap', 'it_khoi_ngoai', 'chua_du_du_lieu')
    group by cluster_label
)
select * from learned where n < 0.01 * (select sum(n) from learned)
