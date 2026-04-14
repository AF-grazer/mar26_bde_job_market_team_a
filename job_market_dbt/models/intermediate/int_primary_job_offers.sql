/* une ligne par offre canonique en gardant la source primaire */
with primary_matches as (
    select *
    from {{ ref('int_job_offer_matches') }}
    where is_primary_source
),

base as (
    select
        matches.job_id,
        matches.match_rule,
        matches.match_score,
        normalized.normalized_offer_id,
        normalized.raw_offer_id,
        normalized.source_system,
        normalized.source_offer_id,
        normalized.source_url,
        normalized.source_file_name,
        normalized.source_file_path,
        normalized.raw_hash,
        normalized.ingested_at,
        normalized.raw_payload,
        normalized.title_raw,
        normalized.title_norm,
        normalized.description_raw,
        normalized.description_norm,
        normalized.company_raw,
        normalized.company_norm,
        normalized.city_raw,
        normalized.city_norm,
        normalized.region_norm,
        normalized.country_norm,
        normalized.postal_code,
        normalized.contract_type_raw,
        normalized.contract_type_norm,
        normalized.remote_norm,
        normalized.salary_raw,
        normalized.published_at_norm,
        normalized.updated_at,
        normalized.working_time_raw,
        normalized.experience_raw,
        normalized.rome_code,
        normalized.rome_family_raw,
        normalized.job_type_raw,
        normalized.industry_raw,
        normalized.created_at,
        normalized.raw_payload ->> 'trancheEffectifEtab' as company_size_raw,
        array_to_string(
            array(
                select trim(value)
                from jsonb_array_elements_text(
                    coalesce(normalized.raw_payload -> 'contexteTravail' -> 'horaires', '[]'::jsonb)
                ) as value
            ),
            ' | '
        ) as schedule_context_raw,
        (
            select formation ->> 'niveauLibelle'
            from jsonb_array_elements(coalesce(normalized.raw_payload -> 'formations', '[]'::jsonb)) as formation
            order by case when formation ->> 'exigence' = 'E' then 1 else 2 end
            limit 1
        ) as education_title,
        (
            select coalesce(formation ->> 'domaineLibelle', formation ->> 'domaine')
            from jsonb_array_elements(coalesce(normalized.raw_payload -> 'formations', '[]'::jsonb)) as formation
            order by case when formation ->> 'exigence' = 'E' then 1 else 2 end
            limit 1
        ) as education_field
    from primary_matches as matches
    inner join {{ ref('int_job_offers_normalized') }} as normalized
        on matches.normalized_offer_id = normalized.normalized_offer_id
),

derived as (
    select
        base.*,
        {{ normalize_match_text('industry_raw') }} as industry_norm,
        case
            when lower(coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) ~ '([0-9]+(?:[.,][0-9]+)?)\s*h'
                then replace(
                    (
                        regexp_match(
                            lower(coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')),
                            '([0-9]+(?:[.,][0-9]+)?)\s*h'
                        )
                    )[1],
                    ',',
                    '.'
                )::numeric
            else null
        end as weekly_hours,
        case
            when lower(coalesce(contract_type_raw, '') || ' ' || coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) like '%temps plein%'
                or lower(coalesce(contract_type_raw, '') || ' ' || coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) like '%full time%'
                then true
            when lower(coalesce(contract_type_raw, '') || ' ' || coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) like '%temps partiel%'
                or lower(coalesce(contract_type_raw, '') || ' ' || coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) like '%part time%'
                then false
            when lower(coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')) ~ '([0-9]+(?:[.,][0-9]+)?)\s*h'
                then replace(
                    (
                        regexp_match(
                            lower(coalesce(working_time_raw, '') || ' ' || coalesce(schedule_context_raw, '')),
                            '([0-9]+(?:[.,][0-9]+)?)\s*h'
                        )
                    )[1],
                    ',',
                    '.'
                )::numeric >= 35
            else null
        end as full_time,
        case
            when raw_payload ? 'entrepriseAdaptee'
                then (raw_payload ->> 'entrepriseAdaptee')::boolean
            when raw_payload ? 'employeurHandiEngage'
                then (raw_payload ->> 'employeurHandiEngage')::boolean
            when lower(coalesce(description_raw, '')) like '%rqth%'
                or lower(coalesce(description_raw, '')) like '%travailleur handicape%'
                then true
            else null
        end as handicap_friendly,
        case
            when jsonb_typeof(coalesce(raw_payload -> 'permis', '[]'::jsonb)) = 'array'
                and jsonb_array_length(coalesce(raw_payload -> 'permis', '[]'::jsonb)) > 0
                then true
            when lower(coalesce(description_raw, '')) like '%permis b%'
                then true
            else false
        end as driving_license,
        case
            when salary_raw is not null then 'EUR'
            else null
        end as salary_currency,
        case
            when lower(coalesce(salary_raw, '')) ~ '\b(an|annuel|year)\b' then 'year'
            when lower(coalesce(salary_raw, '')) ~ '\b(mois|mensuel|month)\b' then 'month'
            when lower(coalesce(salary_raw, '')) ~ '\b(semaine|week)\b' then 'week'
            when lower(coalesce(salary_raw, '')) ~ '(/h|\bheure\b|\bhoraire\b)' then 'hour'
            else null
        end as salary_frequency_norm,
        regexp_match(coalesce(salary_raw, ''), '([0-9][0-9\s,\.]*)\D+([0-9][0-9\s,\.]*)') as salary_range_match,
        regexp_match(coalesce(salary_raw, ''), '([0-9][0-9\s,\.]*)') as salary_single_match,
        regexp_match(lower(coalesce(experience_raw, '')), '([0-9]+(?:[.,][0-9]+)?)') as experience_match
    from base
),

parsed_values as (
    select
        job_id,
        match_rule,
        match_score,
        normalized_offer_id,
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
        title_norm,
        description_raw,
        description_norm,
        company_raw,
        company_norm,
        city_raw,
        city_norm,
        region_norm,
        country_norm,
        postal_code,
        contract_type_raw,
        contract_type_norm,
        remote_norm,
        working_time_raw,
        schedule_context_raw,
        weekly_hours,
        full_time,
        salary_raw,
        case
            when salary_range_match is not null
                then regexp_replace(replace(replace(salary_range_match[1], ' ', ''), ',', '.'), '[^0-9.]', '', 'g')::numeric
            when salary_single_match is not null
                then regexp_replace(replace(replace(salary_single_match[1], ' ', ''), ',', '.'), '[^0-9.]', '', 'g')::numeric
            else null
        end as salary_min_norm,
        case
            when salary_range_match is not null
                then regexp_replace(replace(replace(salary_range_match[2], ' ', ''), ',', '.'), '[^0-9.]', '', 'g')::numeric
            when salary_single_match is not null
                then regexp_replace(replace(replace(salary_single_match[1], ' ', ''), ',', '.'), '[^0-9.]', '', 'g')::numeric
            else null
        end as salary_max_norm,
        salary_frequency_norm,
        salary_currency,
        published_at_norm as published_at,
        updated_at,
        experience_raw,
        case
            when experience_match is not null
                then replace(experience_match[1], ',', '.')::numeric
            else null
        end as experience_years,
        handicap_friendly,
        driving_license,
        rome_code,
        rome_family_raw,
        job_type_raw,
        industry_raw,
        industry_norm,
        company_size_raw,
        education_title,
        education_field,
        created_at
    from derived
),

final as (
    select
        job_id,
        match_rule,
        match_score,
        normalized_offer_id,
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
        title_norm,
        description_raw,
        description_norm,
        company_raw,
        company_norm,
        city_raw,
        city_norm,
        region_norm,
        country_norm,
        postal_code,
        contract_type_raw,
        contract_type_norm,
        remote_norm,
        working_time_raw,
        weekly_hours,
        full_time,
        salary_raw,
        salary_min_norm,
        salary_max_norm,
        salary_frequency_norm,
        salary_currency,
        published_at,
        updated_at,
        experience_raw,
        experience_years,
        handicap_friendly,
        driving_license,
        rome_code,
        rome_family_raw,
        job_type_raw,
        industry_raw,
        industry_norm,
        company_size_raw,
        education_title,
        education_field,
        case
            when coalesce(education_title, education_field) is not null
                then md5(coalesce(education_title, '') || '|' || coalesce(education_field, ''))
            else null
        end as education_id,
        md5(coalesce(company_norm, '') || '|' || coalesce(company_raw, '')) as company_id,
        md5(
            coalesce(city_norm, '')
            || '|'
            || coalesce(postal_code, '')
            || '|'
            || coalesce(region_norm, '')
            || '|'
            || coalesce(country_norm, '')
        ) as location_id,
        md5(
            coalesce(contract_type_norm, '')
            || '|'
            || coalesce(remote_norm, '')
            || '|'
            || coalesce(weekly_hours::text, '')
            || '|'
            || coalesce(full_time::text, '')
        ) as contract_type_id,
        md5(
            coalesce(title_norm, '')
            || '|'
            || coalesce(rome_code, '')
            || '|'
            || coalesce(rome_family_raw, '')
        ) as job_type_id,
        case
            when industry_norm is not null then md5(industry_norm)
            else null
        end as industry_id,
        case
            when salary_min_norm is not null
                or salary_max_norm is not null
                or salary_frequency_norm is not null
                or salary_currency is not null
                then md5(
                    coalesce(salary_min_norm::text, '')
                    || '|'
                    || coalesce(salary_max_norm::text, '')
                    || '|'
                    || coalesce(salary_frequency_norm, '')
                    || '|'
                    || coalesce(salary_currency, '')
                )
            else null
        end as salary_id,
        created_at
    from parsed_values
)

select *
from final
