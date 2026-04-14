with base as (
    select
        job_id,
        raw_payload
    from {{ ref('int_primary_job_offers') }}
),

skill_rows as (
    select
        job_id,
        trim(skill ->> 'libelle') as skill_name,
        'competence' as skill_category
    from base
    cross join lateral jsonb_array_elements(coalesce(raw_payload -> 'competences', '[]'::jsonb)) as skill

    union all

    select
        job_id,
        trim(skill ->> 'libelle') as skill_name,
        'soft_skill' as skill_category
    from base
    cross join lateral jsonb_array_elements(coalesce(raw_payload -> 'qualitesProfessionnelles', '[]'::jsonb)) as skill

    union all

    select
        job_id,
        trim(coalesce(skill ->> 'libelle', skill ->> 'langueLibelle', skill ->> 'name')) as skill_name,
        'language' as skill_category
    from base
    cross join lateral jsonb_array_elements(coalesce(raw_payload -> 'langues', '[]'::jsonb)) as skill

    union all

    select
        job_id,
        trim(skill ->> 'libelle') as skill_name,
        'license' as skill_category
    from base
    cross join lateral jsonb_array_elements(coalesce(raw_payload -> 'permis', '[]'::jsonb)) as skill
)

select distinct
    md5(job_id || '|' || skill_category || '|' || skill_name) as job_skill_id,
    job_id,
    md5(skill_category || '|' || skill_name) as skill_id
from skill_rows
where nullif(skill_name, '') is not null
