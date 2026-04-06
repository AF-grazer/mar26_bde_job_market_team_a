from src.data.connectors.indeed import IndeedSeleniumScraper
from src.data.connectors.france_travail import FranceTravailClient


def run_france_travail() -> None:
    client = FranceTravailClient()
    payload = client.search_offers(
        params={
            "range": "0-19",
        },
    )

    path = client.save_raw(payload)
    print(f"[France Travail] sauvegardé dans {path}")


def run_indeed() -> None:
    scraper = IndeedSeleniumScraper()

    jobs = scraper.collect_jobs_from_yaml("references/job_queries.yaml")
    path = scraper.save_raw_json(jobs)
    print(f"[Indeed] {len(jobs)} offres extraites dans {path}")

if __name__ == "__main__":
    run_france_travail()
    run_indeed()