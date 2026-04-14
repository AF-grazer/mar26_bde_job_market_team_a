/*  garde la traçabilité multi-sources */
select
    md5(job_id || '|' || normalized_offer_id) as job_source_id,
    job_id,
    normalized_offer_id,
    source_system,
    source_offer_id,
    source_url,
    match_rule,
    match_score,
    is_primary_source,
    matched_at
from {{ ref('int_job_offer_matches') }}
