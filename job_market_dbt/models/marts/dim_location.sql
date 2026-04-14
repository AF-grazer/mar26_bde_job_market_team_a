select
    location_id,
    max(coalesce(city_raw, city_norm)) as city,
    max(region_norm) as region,
    max(country_norm) as country,
    max(postal_code) as postal_code
from {{ ref('int_primary_job_offers') }}
group by 1
