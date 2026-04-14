# Job Market

Petit projet de pipeline data autour des offres d'emploi.

L'idee est simple :

- recuperer des offres depuis France Travail et Indeed
- garder le brut en local
- charger le brut dans PostgreSQL
- transformer les donnees avec dbt
- obtenir une table finale propre pour l'analyse et la suite ML

Pour le dev local, je ne passe pas par Snowflake pour eviter de consommer des credits.

## Ce qu'il y a aujourd'hui

- collecte France Travail via API
- collecte Indeed via Selenium + BeautifulSoup
- stockage du brut dans `data/raw`
- chargement dans PostgreSQL local
- transformations dbt
- dedup inter-source apres normalisation
- conservation de la tracabilite des sources

Schema rapide :

- [docs/job_market_pipeline_flow.png](docs/job_market_pipeline_flow.png)

## Collecte

### France Travail

Le collecteur est ici :

- [src/data/connectors/france_travail.py](src/data/connectors/france_travail.py)

La collecte est pilotee depuis :

- [references/collection_targets.yml](references/collection_targets.yml)

Je passe par `codeROME` + geographie pour avoir quelque chose de plus stable qu'une simple recherche texte.

### Indeed

Le collecteur est ici :

- [src/data/connectors/indeed.py](src/data/connectors/indeed.py)

Pour Indeed, je reste sur des recherches texte, mais elles sont alignees sur le meme referentiel metier que France Travail.

Le script principal de collecte est :

- [src/data/make_dataset.py](src/data/make_dataset.py)

## Stockage

Le brut est garde ici :

- `data/raw/france_travail`
- `data/raw/indeed`

Puis je charge dans PostgreSQL avec :

- [src/data/normalizers/load_raw_to_postgres.py](src/data/normalizers/load_raw_to_postgres.py)

Les tables raw sont :

- `landing.raw_france_travail_offers`
- `landing.raw_indeed_offers`

Important :

- aucune dedup en raw
- une ligne = une offre source
- je garde les infos de source pour pouvoir relier une offre finale a ses sources d'origine

## dbt

Le projet dbt est ici :

- [job_market_dbt](job_market_dbt)

Les modeles principaux :

- `stg_france_travail_offers`
- `stg_indeed_offers`
- `int_job_offers_normalized`
- `int_job_offer_matches`
- `int_primary_job_offers`
- `fct_job_offers`
- `bridge_job_source`

## Dedup

Je ne fusionne pas les sources trop tot.

Le flux est :

1. raw dans `landing`
2. staging pour extraire les champs utiles
3. normalisation des titres / entreprises / villes
4. matching inter-source
5. offre canonique finale

La dedup se fait surtout dans :

- [job_market_dbt/models/intermediate/int_job_offers_normalized.sql](job_market_dbt/models/intermediate/int_job_offers_normalized.sql)
- [job_market_dbt/models/intermediate/int_job_offer_matches.sql](job_market_dbt/models/intermediate/int_job_offer_matches.sql)

Aujourd'hui, je garde surtout deux niveaux utiles :

- `fingerprint_exact`
- `fingerprint_soft`

Si une offre France Travail et une offre Indeed matchent, France Travail est prioritaire comme source primaire.

## Tables finales

La table principale pour l'analyse est :

- `analytics.fct_job_offers`

La table de tracabilite est :

- `analytics.bridge_job_source`

J'ai aussi une couche dimensions / bridges pour preparer la suite :

- `dim_company`
- `dim_location`
- `dim_contract`
- `dim_job_type`
- `dim_industry`
- `dim_salary`
- `dim_education`
- `dim_skill`
- `dim_advantage`
- `bridge_job_skill`
- `bridge_job_advantage`

## Lancer le projet en local

### Installer les dependances

```powershell
python -m pip install -r requirements.txt
```

### Lancer Postgres et pgAdmin

```powershell
docker compose up -d postgres pgadmin
```

### Collecter le brut

```powershell
python src\data\make_dataset.py --source france_travail
python src\data\make_dataset.py --source indeed
```

### Charger dans Postgres

```powershell
python src\data\normalizers\load_raw_to_postgres.py --source all
```

### Lancer dbt

```powershell
dbt run --project-dir job_market_dbt --profiles-dir job_market_dbt
dbt test --project-dir job_market_dbt --profiles-dir job_market_dbt
```

## Variables utiles

Exemple :

- [.env.example](.env.example)

Les plus importantes :

- `FRANCE_TRAVAIL_CLIENT_ID`
- `FRANCE_TRAVAIL_CLIENT_SECRET`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `PGADMIN_DEFAULT_EMAIL`
- `PGADMIN_DEFAULT_PASSWORD`
- `PGADMIN_PORT`
- `SELENIUM_HEADLESS`

