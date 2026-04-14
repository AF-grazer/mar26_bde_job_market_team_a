PYTHON := .venv/Scripts/python.exe
PIP := $(PYTHON) -m pip
DBT := .venv/Scripts/dbt.exe
DBT_FLAGS := --project-dir job_market_dbt --profiles-dir job_market_dbt
LOADER := src/data/normalizers/load_raw_to_postgres.py
COLLECTOR := src/data/make_dataset.py

.PHONY: help install collect-france-travail collect-indeed postgres-up postgres-down postgres-reset load-raw dbt-run dbt-test pipeline

help:
	@echo Available targets:
	@echo   install
	@echo   collect-france-travail
	@echo   collect-indeed
	@echo   postgres-up
	@echo   postgres-down
	@echo   postgres-reset
	@echo   load-raw
	@echo   dbt-run
	@echo   dbt-test
	@echo   pipeline

install:
	$(PIP) install -r requirements.txt

collect-france-travail:
	$(PYTHON) $(COLLECTOR) --source france_travail

collect-indeed:
	$(PYTHON) $(COLLECTOR) --source indeed

postgres-up:
	docker compose up -d postgres

postgres-down:
	docker compose down

postgres-reset:
	docker compose down -v
	docker compose up -d postgres

load-raw:
	$(PYTHON) $(LOADER) --source all

dbt-run:
	$(DBT) run $(DBT_FLAGS)

dbt-test:
	$(DBT) test $(DBT_FLAGS)

pipeline: collect-france-travail collect-indeed load-raw dbt-run dbt-test
