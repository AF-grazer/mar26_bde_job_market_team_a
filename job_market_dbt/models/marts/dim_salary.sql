select distinct
    salary_id,
    salary_frequency_norm as frequency,
    salary_min_norm as salary_min,
    salary_max_norm as salary_max,
    salary_currency as currency
from {{ ref('int_primary_job_offers') }}
where salary_id is not null
