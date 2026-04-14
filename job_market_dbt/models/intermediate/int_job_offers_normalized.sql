/* garde une ligne par offre source avec des normalisations dediees au matching */
with unioned as (
    select
        raw_offer_id,
        source_system,
        source_offer_id,
        source_url,
        source_file_name,
        source_file_path,
        raw_hash,
        ingested_at,
        raw_payload,
        title_raw,
        description_raw,
        company_raw,
        city_raw,
        postal_code_raw,
        contract_type_raw,
        contract_nature_raw,
        salary_raw,
        published_at,
        updated_at,
        working_time_raw,
        experience_raw,
        rome_code,
        rome_family_raw,
        job_type_raw,
        industry_raw
    from {{ ref('stg_france_travail_offers') }}

    union all

    select
        raw_offer_id,
        source_system,
        source_offer_id,
        source_url,
        source_file_name,
        source_file_path,
        raw_hash,
        ingested_at,
        raw_payload,
        title_raw,
        description_raw,
        company_raw,
        city_raw,
        postal_code_raw,
        contract_type_raw,
        contract_nature_raw,
        salary_raw,
        published_at,
        updated_at,
        working_time_raw,
        experience_raw,
        rome_code,
        rome_family_raw,
        job_type_raw,
        industry_raw
    from {{ ref('stg_indeed_offers') }}
),

prepared as (
    select
        md5(source_system || '|' || raw_offer_id::text) as normalized_offer_id,
        raw_offer_id,
        source_system,
        case when source_system = 'france_travail' then 1 else 2 end as source_priority,
        source_offer_id,
        source_url,
        source_file_name,
        source_file_path,
        raw_hash,
        ingested_at,
        raw_payload,
        title_raw,
        {{ normalize_match_text('title_raw') }} as title_norm,
        {{ normalize_title_match('title_raw') }} as title_match_norm,
        company_raw,
        {{ normalize_match_text('company_raw') }} as company_norm,
        {{ normalize_company_match('company_raw') }} as company_match_norm,
        city_raw,
        {{ normalize_match_text('city_raw') }} as city_norm,
        {{ normalize_city_match('city_raw') }} as city_match_norm,
        null::text as region_norm,
        'france' as country_norm,
        postal_code_raw as postal_code,
        contract_type_raw,
        {{ normalize_match_text('contract_type_raw') }} as contract_type_norm,
        case
            when lower(coalesce(city_raw, '') || ' ' || coalesce(description_raw, '')) like '%teletravail%' then 'teletravail'
            when lower(coalesce(city_raw, '') || ' ' || coalesce(description_raw, '')) like '%remote%' then 'remote'
            else 'non_precise'
        end as remote_norm,
        salary_raw,
        null::numeric as salary_min_norm,
        null::numeric as salary_max_norm,
        null::text as salary_frequency_norm,
        published_at as published_at_norm,
        updated_at,
        description_raw,
        {{ normalize_match_text('description_raw') }} as description_norm,
        working_time_raw,
        experience_raw,
        rome_code,
        rome_family_raw,
        job_type_raw,
        industry_raw,
        current_timestamp as created_at
    from unioned
),
/* 
=> construit 3 niveaux de fingerprint :
- fingerprint_exact : title + company + city + date
- fingerprint_soft: title + company + city
- fingerprint_title_city: title + city
*/
final as (
    select
        *,
        case
            when title_match_norm is not null
                and company_match_norm is not null
                and city_match_norm is not null
                and published_at_norm is not null
                then md5(
                    title_match_norm
                    || '|'
                    || company_match_norm
                    || '|'
                    || city_match_norm
                    || '|'
                    || to_char(published_at_norm::date, 'YYYY-MM-DD')
                )
            else null
        end as fingerprint_exact,
        case
            when title_match_norm is not null
                and company_match_norm is not null
                and city_match_norm is not null
                then md5(
                    title_match_norm
                    || '|'
                    || company_match_norm
                    || '|'
                    || city_match_norm
                )
            else null
        end as fingerprint_soft,
        case
            when title_match_norm is not null
                and city_match_norm is not null
                then md5(title_match_norm || '|' || city_match_norm)
            else null
        end as fingerprint_title_city
    from prepared
)

select *
from final
