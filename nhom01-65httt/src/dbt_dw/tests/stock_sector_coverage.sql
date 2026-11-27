{#- Cảnh báo: quá 5% cổ phiếu đang niêm yết chưa có ngành (ngoài VN-Index). -#}
{{ config(severity='warn') }}
select rate
from (
    select count(*) filter (where s.sector_code = 'UNCLASSIFIED')::numeric / nullif(count(*), 0) as rate
    from {{ ref('dim_stock') }} d
    join {{ ref('dim_sector') }} s on s.sector_key = d.sector_key
    where d.security_type = 'STOCK' and d.is_active
) t
where rate > 0.05
