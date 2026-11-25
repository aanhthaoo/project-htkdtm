select
    source_key::bigint as source_key,
    publisher,
    source_type,
    section,
    feed_timezone,
    note
from {{ ref('seed_source') }}
