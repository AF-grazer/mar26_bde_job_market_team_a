select
    job_type_id,
    max(coalesce(job_type_raw, title_raw)) as title,
    max(coalesce(rome_family_raw, industry_raw)) as category,
    max(rome_code) as rome_code,
    max(rome_family_raw) as rome_family
from {{ ref('int_primary_job_offers') }}
group by 1
