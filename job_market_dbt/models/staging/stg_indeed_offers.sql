with source as (
    select *
    from {{ source('landing', 'raw_indeed_offers') }}
),

renamed as (
    select
        raw_offer_id,
        source_system,
        source_offer_id,
        coalesce(source_url, raw_payload ->> 'job_url') as source_url,
        source_file_name,
        source_file_path,
        raw_hash,
        ingested_at,
        raw_payload,
        raw_payload ->> 'title' as title_raw,
        raw_payload ->> 'description' as description_raw,
        raw_payload ->> 'company' as company_raw,
        raw_payload ->> 'location' as city_raw,
        null::text as postal_code_raw,
        null::text as commune_code_raw,
        raw_payload ->> 'contract_type' as contract_type_raw,
        null::text as contract_nature_raw,
        raw_payload ->> 'salary' as salary_raw,
        case
            when coalesce(raw_payload ->> 'published_at', '') ~ '^\d{4}-\d{2}-\d{2}'
                then (raw_payload ->> 'published_at')::timestamptz
            else null
        end as published_at,
        null::timestamptz as updated_at,
        raw_payload ->> 'working_time' as working_time_raw,
        null::text as experience_raw,
        null::text as rome_code,
        raw_payload ->> 'rome_family' as rome_family_raw,
        raw_payload ->> 'title' as job_type_raw,
        raw_payload ->> 'sector' as industry_raw,
        raw_payload ->> 'search_query' as search_query,
        raw_payload ->> 'search_location' as search_location
    from source
)

select *
from renamed
