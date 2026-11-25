select
    investor_type_key::bigint as investor_type_key,
    code,
    name_vi,
    name_en,
    is_derived
from {{ ref('seed_investor_type') }}
