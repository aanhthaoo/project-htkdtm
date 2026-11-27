select
    indicator_key::bigint as indicator_key,
    code,
    name_vi,
    unit,
    frequency,
    scope,
    origin,
    source_code
from {{ ref('seed_indicator') }}
