select
    contract_type_id,
    max(contract_type_norm) as contract_type,
    max(full_time::int)::boolean as full_time,
    max(remote_norm) as remote,
    max(weekly_hours) as weekly_hours
from {{ ref('int_primary_job_offers') }}
group by 1
