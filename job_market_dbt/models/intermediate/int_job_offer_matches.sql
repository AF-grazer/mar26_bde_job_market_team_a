/* rapproche les offres apres normalisation et garde la priorite France Travail */
with base as (
    select *
    from {{ ref('int_job_offers_normalized') }}
),

/* combien de lignes et combien de sources avec meme cle de matching */
exact_stats as (
    select
        fingerprint_exact,
        count(*) as exact_row_count,
        count(distinct source_system) as exact_source_count
    from base
    where fingerprint_exact is not null
    group by 1
),

soft_stats as (
    select
        fingerprint_soft,
        count(*) as soft_row_count,
        count(distinct source_system) as soft_source_count
    from base
    where fingerprint_soft is not null
    group by 1
),

/*
canonical_match_key :
=> si fingerprint_exact apparait plusieurs fois, on prend lui
=> sinon si fingerprint_soft apparait plusieurs fois, on prend lui
=> sinon on garde normalized_offer_id et chaque ligne reste seule
*/
enriched as (
    select
        base.*,
        exact_stats.exact_row_count,
        exact_stats.exact_source_count,
        soft_stats.soft_row_count,
        soft_stats.soft_source_count,
        case
            when base.fingerprint_exact is not null and coalesce(exact_stats.exact_row_count, 0) > 1
                then base.fingerprint_exact
            when base.fingerprint_soft is not null and coalesce(soft_stats.soft_row_count, 0) > 1
                then base.fingerprint_soft
            else base.normalized_offer_id
        end as canonical_match_key
    from base
    left join exact_stats
        on base.fingerprint_exact = exact_stats.fingerprint_exact
    left join soft_stats
        on base.fingerprint_soft = soft_stats.fingerprint_soft
),

/*
match_rule:
    fingerprint_exact_cross_source
    fingerprint_exact
    fingerprint_soft_cross_source
    fingerprint_soft
    single_source
match_score: plus c'est exact, plus le score est haut
=> ordre de priorite :
    france_travail
    published_at_norm la plus recente
    ingested_at la plus recente
    raw_offer_id en dernier
*/
scored as (
    select
        md5(canonical_match_key) as job_id,
        normalized_offer_id,
        raw_offer_id,
        source_system,
        source_offer_id,
        source_url,
        ingested_at,
        published_at_norm,
        case
            when fingerprint_exact is not null and coalesce(exact_row_count, 0) > 1 and coalesce(exact_source_count, 0) > 1
                then 'fingerprint_exact_cross_source'
            when fingerprint_exact is not null and coalesce(exact_row_count, 0) > 1
                then 'fingerprint_exact'
            when fingerprint_soft is not null and coalesce(soft_row_count, 0) > 1 and coalesce(soft_source_count, 0) > 1
                then 'fingerprint_soft_cross_source'
            when fingerprint_soft is not null and coalesce(soft_row_count, 0) > 1
                then 'fingerprint_soft'
            else 'single_source'
        end as match_rule,
        case
            when fingerprint_exact is not null and coalesce(exact_row_count, 0) > 1 and coalesce(exact_source_count, 0) > 1
                then 1.00
            when fingerprint_exact is not null and coalesce(exact_row_count, 0) > 1
                then 0.95
            when fingerprint_soft is not null and coalesce(soft_row_count, 0) > 1 and coalesce(soft_source_count, 0) > 1
                then 0.85
            when fingerprint_soft is not null and coalesce(soft_row_count, 0) > 1
                then 0.80
            else 0.50
        end as match_score,
        row_number() over (
            partition by canonical_match_key
            order by
                case when source_system = 'france_travail' then 1 else 2 end,
                published_at_norm desc nulls last,
                ingested_at desc,
                raw_offer_id desc
        ) as source_rank
    from enriched
)

select
    job_id,
    normalized_offer_id,
    raw_offer_id,
    source_system,
    source_offer_id,
    source_url,
    match_rule,
    match_score,
    source_rank = 1 as is_primary_source,
    current_timestamp as matched_at
from scored
