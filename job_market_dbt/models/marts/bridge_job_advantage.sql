with base as (
    select
        job_id,
        raw_payload
    from {{ ref('int_primary_job_offers') }}
),

raw_advantage_rows as (
    select
        job_id,
        value as raw_advantage_name
    from base
    cross join lateral jsonb_array_elements_text(
        coalesce(raw_payload -> 'contexteTravail' -> 'horaires', '[]'::jsonb)
    ) as value
),

advantage_rows as (
    select
        job_id,
        trim(split_value) as advantage_name
    from raw_advantage_rows
    cross join lateral regexp_split_to_table(raw_advantage_name, E'\\n+') as split_value
)

select distinct
    md5(job_id || '|' || advantage_name) as job_advantage_id,
    job_id,
    md5(advantage_name) as advantage_id
from advantage_rows
where nullif(advantage_name, '') is not null
  and lower(advantage_name) !~ '(^|\s)temps partiel'
  and lower(advantage_name) !~ '(^|\s)temps plein'
  and lower(advantage_name) !~ '([0-9]+(?:[.,][0-9]+)?)\s*h'
  and lower(advantage_name) !~ '([0-9]+(?:[.,][0-9]+)?)h\/semaine'
