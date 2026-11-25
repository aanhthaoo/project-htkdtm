{#- Chiều ngành: mỗi dòng một phân ngành ICB cấp 4, kèm tên và mã các cấp 1 đến 3.
    Hai loại dòng bổ sung:
      - "<cấp 2>_NA": mã chỉ biết ICB cấp 2 (chưa có cấp 4 từ Vietcap iQ)
      - "UNCLASSIFIED": mã chưa có phân ngành (ví dụ chỉ số VN-Index)
    analysis_group: nhóm dùng khi dự báo; mặc định bằng cấp 2, ngành quá ít mã thanh khoản sẽ gộp ở N8. -#}
{{ config(materialized='table') }}

with icb as (
    select * from {{ ref('icb') }}
),
l4 as (select * from icb where level = 4),
l3 as (select * from icb where level = 3),
l2 as (select * from icb where level = 2),
l1 as (select * from icb where level = 1),
full_rows as (
    select
        l4.icb_code as icb_l4_code, l4.name_en as icb_l4_name,
        l3.icb_code as icb_l3_code, l3.name_en as icb_l3_name,
        l2.icb_code as icb_l2_code, l2.name_en as icb_l2_name_en, l2.name_vi as icb_l2_name_vi,
        l1.icb_code as icb_l1_code, l1.name_en as icb_l1_name_en, l1.name_vi as icb_l1_name_vi,
        l4.icb_code as sector_code
    from l4
    join l3 on l3.icb_code = l4.parent_code
    join l2 on l2.icb_code = l3.parent_code
    join l1 on l1.icb_code = l2.parent_code
),
na_rows as (
    select
        null::varchar as icb_l4_code, '(Chưa có phân ngành cấp 4)' as icb_l4_name,
        null::varchar as icb_l3_code, '(Chưa có nhóm ngành cấp 3)' as icb_l3_name,
        l2.icb_code as icb_l2_code, l2.name_en as icb_l2_name_en, l2.name_vi as icb_l2_name_vi,
        l1.icb_code as icb_l1_code, l1.name_en as icb_l1_name_en, l1.name_vi as icb_l1_name_vi,
        l2.icb_code || '_NA' as sector_code
    from l2
    join l1 on l1.icb_code = l2.parent_code
),
unclassified as (
    select
        null::varchar, '(Chưa phân loại)', null::varchar, '(Chưa phân loại)',
        null::varchar, 'Unclassified', 'Chưa phân loại',
        null::varchar, 'Unclassified', 'Chưa phân loại',
        'UNCLASSIFIED'
),
all_rows as (
    select * from full_rows
    union all select * from na_rows
    union all select * from unclassified
)
select
    {{ surrogate_key('sector_code') }} as sector_key,
    sector_code,
    icb_l1_code, icb_l1_name_en, icb_l1_name_vi,
    icb_l2_code, icb_l2_name_en, icb_l2_name_vi,
    icb_l3_code, icb_l3_name,
    icb_l4_code, icb_l4_name,
    coalesce(icb_l2_code, 'UNCLASSIFIED') as analysis_group
from all_rows
