from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.connectors.france_travail import FranceTravailClient
from src.data.connectors.indeed import IndeedSeleniumScraper

DEFAULT_TARGETS_FILE = "references/collection_targets.yml"


def run_france_travail() -> None:
    client = FranceTravailClient()
    targets = client.load_targets_from_file(DEFAULT_TARGETS_FILE)
    payload = client.collect_offers_from_targets(targets=targets)
    path = client.save_raw(payload)
    print(f"[France Travail] sauvegarde dans {path}")


def run_indeed() -> None:
    scraper = IndeedSeleniumScraper()
    searches = scraper.load_searches_from_targets_file(DEFAULT_TARGETS_FILE)
    jobs = scraper.collect_jobs_from_queries(searches)
    path = scraper.save_raw_json(jobs)
    print(f"[Indeed] {len(jobs)} offres extraites dans {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect raw job offers.")
    parser.add_argument(
        "--source",
        choices=["france_travail", "indeed", "all"],
        default="all",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.source in {"all", "france_travail"}:
        run_france_travail()

    if args.source in {"all", "indeed"}:
        run_indeed()


if __name__ == "__main__":
    main()
