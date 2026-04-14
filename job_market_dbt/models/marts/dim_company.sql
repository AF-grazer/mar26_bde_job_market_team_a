with base as (
    select
        company_id,
        company_raw as name,
        company_norm as name_normalized,
        company_size_raw,
        country_norm as country
    from {{ ref('int_primary_job_offers') }}
),

parsed as (
    select
        company_id,
        name,
        name_normalized,
        case
            when lower(coalesce(company_size_raw, '')) ~ '([0-9]+)\s*[^0-9]+\s*([0-9]+)'
                then (regexp_match(lower(company_size_raw), '([0-9]+)\s*[^0-9]+\s*([0-9]+)'))[1]::integer
            when lower(coalesce(company_size_raw, '')) ~ 'moins de\s*([0-9]+)'
                then 0
            when lower(coalesce(company_size_raw, '')) ~ 'plus de\s*([0-9]+)'
                then (regexp_match(lower(company_size_raw), 'plus de\s*([0-9]+)'))[1]::integer
            else null
        end as size_min,
        case
            when lower(coalesce(company_size_raw, '')) ~ '([0-9]+)\s*[^0-9]+\s*([0-9]+)'
                then (regexp_match(lower(company_size_raw), '([0-9]+)\s*[^0-9]+\s*([0-9]+)'))[2]::integer
            when lower(coalesce(company_size_raw, '')) ~ 'moins de\s*([0-9]+)'
                then greatest((regexp_match(lower(company_size_raw), 'moins de\s*([0-9]+)'))[1]::integer - 1, 0)
            else null
        end as size_max,
        country
    from base
)

select
    company_id,
    max(name) as name,
    max(name_normalized) as name_normalized,
    min(size_min) as size_min,
    max(size_max) as size_max,
    max(country) as country
from parsed
group by 1
