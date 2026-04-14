create schema if not exists landing;

create table if not exists landing.raw_france_travail_offers (
    raw_offer_id bigserial primary key,
    source_system text not null,
    source_offer_id text,
    source_url text,
    source_file_name text not null,
    source_file_path text not null,
    raw_hash text not null,
    ingested_at timestamptz not null default current_timestamp,
    raw_payload jsonb not null
);

alter table landing.raw_france_travail_offers
    add column if not exists source_url text;

drop index if exists landing.uq_raw_france_travail_offers_raw_hash;

create index if not exists ix_raw_france_travail_offers_raw_hash
    on landing.raw_france_travail_offers (raw_hash);

create index if not exists ix_raw_france_travail_offers_source_offer_id
    on landing.raw_france_travail_offers (source_offer_id);

create table if not exists landing.raw_indeed_offers (
    raw_offer_id bigserial primary key,
    source_system text not null,
    source_offer_id text,
    source_url text,
    source_file_name text not null,
    source_file_path text not null,
    raw_hash text not null,
    ingested_at timestamptz not null default current_timestamp,
    raw_payload jsonb not null
);

alter table landing.raw_indeed_offers
    add column if not exists source_url text;

drop index if exists landing.uq_raw_indeed_offers_raw_hash;

create index if not exists ix_raw_indeed_offers_raw_hash
    on landing.raw_indeed_offers (raw_hash);

create index if not exists ix_raw_indeed_offers_source_offer_id
    on landing.raw_indeed_offers (source_offer_id);
