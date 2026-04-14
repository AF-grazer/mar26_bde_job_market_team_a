select distinct
    education_id,
    education_title as title,
    education_field
from {{ ref('int_primary_job_offers') }}
where education_id is not null
