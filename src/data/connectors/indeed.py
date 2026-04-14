from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
import time
import random
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from src.data.connectors.collection_targets import build_indeed_searches, load_collection_targets

load_dotenv()


@dataclass(frozen=True)
class IndeedSettings:
    indeed_base_url: str = os.getenv("INDEED_BASE_URL", "https://fr.indeed.com")
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    selenium_headless: bool = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"


class IndeedSeleniumScraper:
    def __init__(self, headless: bool | None = None) -> None:
        if headless is None:
            self.settings = IndeedSettings()
        else:
            self.settings = IndeedSettings(selenium_headless=headless)

        self._driver_dir = Path(tempfile.mkdtemp(prefix="job_market_indeed_"))
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]

    def _build_driver(self) -> webdriver.Chrome:
        options = ChromeOptions()
        options.add_argument(f"--user-agent={random.choice(self.user_agents)}")
        options.add_argument("--window-size=1400,1200")
        options.add_argument("--disable-gpu")

        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument(f"--user-data-dir={self._driver_dir / 'chrome-profile'}")

        if self.settings.selenium_headless:
            options.add_argument("--headless=new")

        return webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )

    def build_search_url(self, query: str, location: str = "", start: int = 0) -> str:
        params = {
            "q": query,
            "l": location,
            "start": start,
        }
        return f"{self.settings.indeed_base_url}/jobs?{urlencode(params)}"

    def fetch_search_page_html(self, query: str, location: str = "", start: int = 0) -> str:
        url = self.build_search_url(query=query, location=location, start=start)
        driver = None
        
        try:
            driver = self._build_driver()
            driver.get(url)
            wait = WebDriverWait(driver, self.settings.request_timeout)

            try:
                wait.until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "a.jcs-JobTitle, h2.jobTitle a, a[data-jk], a[href*='jk=']")
                    )
                )
            except TimeoutException:
                pass

            return driver.page_source

        except Exception as e:
            print(f"Erreur lors du fetch: {e}")
            raise

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"Erreur lors de quit(): {e}")

    def parse_search_page(self, html: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        jobs: List[dict] = []

        title_links = soup.select(
            "a.jcs-JobTitle, "
            "h2.jobTitle a, "
            "a[data-jk], "
            "a[href*='jk='], "
            "a[href*='/rc/clk'], "
            "a[href*='/viewjob']"
        )

        print(f"Nombre de liens candidats trouvés : {len(title_links)}")

        seen: Set[str] = set()

        for link in title_links:
            href = link.get("href")
            source_job_id = self._extract_job_id(href, link)
            job_url = self._build_canonical_job_url(href)

            title = self._clean_text(link.get_text(" ", strip=True))
            if not title:
                title = self._clean_text(link.get("aria-label"))

            if not title:
                continue

            dedupe_key = source_job_id or job_url or title
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            card = self._find_job_card(link)

            company = None
            location = None
            salary = None
            contract_type = None
            working_time = None
            published_at = None
            snippet = None
            card_attributes: List[str] = []
            benefits: List[str] = []

            if card is not None:
                company = self._get_first_text(
                    card,
                    [
                        "span[data-testid='company-name']",
                        "div[data-testid='company-name']",
                        "span.companyName",
                        "[data-testid='company-name']",
                    ],
                )

                location = self._get_first_text(
                    card,
                    [
                        "div[data-testid='text-location']",
                        "span[data-testid='text-location']",
                        "div.companyLocation",
                        ".companyLocation",
                    ],
                )

                salary = self._get_first_text(
                    card,
                    [
                        "li.salary-snippet-container",
                        "div[data-testid='attribute_snippet_testid']",
                        ".salary-snippet-container",
                        "span.salary-snippet",
                    ],
                )

                card_attributes = self._get_all_texts(
                    card,
                    [
                        "li[data-testid='attribute_snippet_testid']",
                        "li.salary-snippet-container",
                        "ul.metadataContainer li",
                    ],
                )

                classified_attributes = self._classify_card_attributes(card_attributes)
                salary = salary or classified_attributes["salary"]
                contract_type = classified_attributes["contract_type"]
                working_time = classified_attributes["working_time"]
                benefits = classified_attributes["benefits"]

                published_at = self._get_first_text(
                    card,
                    [
                        "span[data-testid='myJobsStateDate']",
                        ".date",
                    ],
                )

                snippet = self._get_first_text(
                    card,
                    [
                        "div[data-testid='belowJobSnippet']",
                        "div[data-testid='text-snippet']",
                        ".job-snippet",
                    ],
                )

            jobs.append(
                {
                    "source": "indeed",
                    "source_job_id": source_job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "contract_type": contract_type,
                    "working_time": working_time,
                    "salary": salary,
                    "published_at": published_at,
                    "job_url": job_url,
                    "description": snippet,
                    "benefits": benefits,
                    "raw_payload": {
                        "href": href,
                        "card_attributes": card_attributes,
                        "benefits": benefits,
                        "company": company,
                        "location": location,
                        "salary": salary,
                        "contract_type": contract_type,
                        "working_time": working_time,
                        "published_at": published_at,
                        "description_snippet": snippet,
                    },
                }
            )

        return self._deduplicate_jobs(jobs)

    def load_searches_from_targets_file(self, yaml_path: str) -> List[dict]:
        return build_indeed_searches(load_collection_targets(yaml_path))

    def collect_jobs_from_queries(self, searches: List[dict]) -> List[dict]:
        all_jobs: List[dict] = []

        for search in searches:
            delay = random.uniform(2, 5)
            time.sleep(delay)
            html = self.fetch_search_page_html(
                query=search["query"],
                location=search.get("location", ""),
                start=0,
            )
            jobs = self.parse_search_page(html)

            for job in jobs:
                job["sector"] = search.get("sector_slug")
                job["sector_label"] = search.get("sector_label")
                job["rome_family"] = search.get("rome_family")
                job["rome_codes"] = search.get("rome_codes", [])
                job["regions"] = search.get("regions", [])
                job["departements"] = search.get("departements", [])
                job["search_query"] = search["query"]
                job["search_location"] = search.get("location", "")

            all_jobs.extend(jobs)
            print(
                f"{search['query']} / {search.get('location', '')} "
                f"/ {search.get('sector_slug', '')} -> {len(jobs)} offres"
            )

        return self._deduplicate_jobs(all_jobs)

    def collect_jobs_from_targets_file(self, yaml_path: str) -> List[dict]:
        searches = self.load_searches_from_targets_file(yaml_path)
        return self.collect_jobs_from_queries(searches)

    def _find_job_card(self, element):
        selectors = [
            "div.job_seen_beacon",
            "div.cardOutline",
            "div[data-jk]",
            "li",
            "td.resultContent",
            "div.slider_container",
            "div[data-testid='slider_item']",
        ]

        for selector in selectors:
            parent = element.find_parent(selector)
            if parent is not None:
                return parent

        return None

    def _build_canonical_job_url(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None

        source_job_id = self._extract_job_id(href, None)
        if source_job_id:
            return f"{self.settings.indeed_base_url}/viewjob?jk={source_job_id}"

        return urljoin(self.settings.indeed_base_url, href)

    def _extract_job_id(self, href: Optional[str], element) -> Optional[str]:
        if element is not None and element.get("data-jk"):
            return element.get("data-jk")

        if not href:
            return None

        parsed = urlparse(href)
        query_params = parse_qs(parsed.query)

        if "jk" in query_params and query_params["jk"]:
            return query_params["jk"][0]

        return None

    @staticmethod
    def _clean_text(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    def _get_first_text(self, element, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            found = element.select_one(selector)
            if found:
                text = self._clean_text(found.get_text(" ", strip=True))
                if text:
                    return text
        return None

    def _get_all_texts(self, element, selectors: List[str]) -> List[str]:
        values: List[str] = []
        seen: Set[str] = set()

        for selector in selectors:
            for found in element.select(selector):
                text = self._clean_text(found.get_text(" ", strip=True))
                if text and text not in seen:
                    seen.add(text)
                    values.append(text)

        return values

    def _classify_card_attributes(self, attributes: List[str]) -> dict:
        salary: Optional[str] = None
        contract_type: Optional[str] = None
        working_time_values: List[str] = []
        benefits: List[str] = []

        for attribute in attributes:
            normalized = attribute.lower()

            if salary is None and self._looks_like_salary(normalized):
                salary = attribute
                continue

            if contract_type is None and self._looks_like_contract_type(normalized):
                contract_type = self._normalize_contract_type(attribute)
                continue

            if self._looks_like_working_time(normalized):
                normalized_working_time = self._normalize_working_time(attribute)
                if normalized_working_time:
                    working_time_values.append(normalized_working_time)
                continue

            if self._looks_like_non_benefit_metadata(normalized):
                continue

            benefits.append(attribute)

        working_time = " | ".join(dict.fromkeys(working_time_values)) or None

        return {
            "salary": salary,
            "contract_type": contract_type,
            "working_time": working_time,
            "benefits": list(dict.fromkeys(benefits)),
        }

    @staticmethod
    def _looks_like_salary(value: str) -> bool:
        return "€" in value or "eur" in value or "par an" in value or "par jour" in value or "par mois" in value or "par heure" in value

    @staticmethod
    def _looks_like_contract_type(value: str) -> bool:
        contract_tokens = [
            "cdi",
            "cdd",
            "stage",
            "alternance",
            "contrat d'apprentissage",
            "contrat de professionnalisation",
            "freelance",
            "intérim",
            "interim",
            "indépendant",
            "independant",
            "franchise",
            "profession libérale",
            "profession liberale",
        ]
        return any(token in value for token in contract_tokens)

    @staticmethod
    def _looks_like_working_time(value: str) -> bool:
        return (
            "temps plein" in value
            or "temps partiel" in value
            or "35h" in value
            or "39h" in value
            or "24h" in value
            or "30h" in value
            or "par semaine" in value
            or "h/semaine" in value
        )

    @staticmethod
    def _looks_like_non_benefit_metadata(value: str) -> bool:
        noise_tokens = [
            "candidature simplifiée",
            "candidature simplifiee",
            "annonce",
            "urgent",
            "nouveau",
            "répond souvent",
            "repond souvent",
            "employeur actif",
        ]
        return any(token in value for token in noise_tokens)

    @staticmethod
    def _normalize_contract_type(value: str) -> str:
        normalized = value.lower()

        if "contrat d'apprentissage" in normalized:
            return "Contrat d'apprentissage"
        if "contrat de professionnalisation" in normalized:
            return "Contrat de professionnalisation"
        if "alternance" in normalized:
            return "Alternance"
        if "stage" in normalized:
            return "Stage"
        if "cdi" in normalized:
            return "CDI"
        if "cdd" in normalized:
            return "CDD"
        if "interim" in normalized or "intérim" in normalized:
            return "Intérim"
        if "freelance" in normalized:
            return "Freelance"

        return value

    @staticmethod
    def _normalize_working_time(value: str) -> Optional[str]:
        normalized = value.lower()

        if "temps plein" in normalized:
            return "Temps plein"
        if "temps partiel" in normalized:
            return "Temps partiel"

        cleaned = " ".join(value.split())
        return cleaned or None

    @staticmethod
    def _deduplicate_jobs(jobs: List[dict]) -> List[dict]:
        unique_jobs: List[dict] = []
        seen: Set[str] = set()

        for job in jobs:
            dedupe_key = job.get("source_job_id") or job.get("job_url")
            if not dedupe_key or dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            unique_jobs.append(job)

        return unique_jobs

    @staticmethod
    def save_raw_json(payload: List[dict], filename_prefix: str = "indeed_jobs") -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/raw/indeed")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{filename_prefix}_{timestamp}.json"
        output_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_file
