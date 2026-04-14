select distinct
    industry_id,
    industry_raw as industry_name
from {{ ref('int_primary_job_offers') }}
where industry_id is not null
