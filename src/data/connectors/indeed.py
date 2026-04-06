from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()


@dataclass(frozen=True)
class IndeedSettings:
    indeed_base_url: str = os.getenv("INDEED_BASE_URL", "https://fr.indeed.com")
    user_agent: str = os.getenv("USER_AGENT", "Mozilla/5.0")
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    selenium_headless: bool = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"


class IndeedSeleniumScraper:
    def __init__(self) -> None:
        self.settings = IndeedSettings()

    def _build_driver(self) -> webdriver.Chrome:
        options = ChromeOptions()
        options.add_argument(f"--user-agent={self.settings.user_agent}")
        options.add_argument("--window-size=1400,1200")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        if self.settings.selenium_headless:
            options.add_argument("--headless=new")

        return webdriver.Chrome(service=ChromeService(), options=options)

    def build_search_url(self, query: str, location: str = "", start: int = 0) -> str:
        params = {
            "q": query,
            "l": location,
            "start": start,
        }
        return f"{self.settings.indeed_base_url}/jobs?{urlencode(params)}"

    def fetch_search_page_html(self, query: str, location: str = "", start: int = 0) -> str:
        url = self.build_search_url(query=query, location=location, start=start)
        driver = self._build_driver()

        try:
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
        finally:
            driver.quit()

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
            published_at = None
            snippet = None

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
                        "div[data-testid='attribute_snippet_testid']",
                        ".salary-snippet-container",
                        "span.salary-snippet",
                    ],
                )

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
                    "contract_type": None,
                    "salary": salary,
                    "published_at": published_at,
                    "job_url": job_url,
                    "description": snippet,
                    "raw_payload": {
                        "href": href,
                    },
                }
            )

        return self._deduplicate_jobs(jobs)

    def load_searches_from_yaml(self, yaml_path: str) -> List[dict]:
        path = Path(yaml_path)
        content = yaml.safe_load(path.read_text(encoding="utf-8"))

        searches: List[dict] = []

        for sector_block in content.get("sectors", []):
            sector = sector_block.get("sector")
            rome_family = sector_block.get("rome_family")

            for search in sector_block.get("searches", []):
                searches.append(
                    {
                        "sector": sector,
                        "rome_family": rome_family,
                        "query": search.get("query", ""),
                        "location": search.get("location", ""),
                    }
                )

        return searches

    def collect_jobs_from_queries(self, searches: List[dict]) -> List[dict]:
        all_jobs: List[dict] = []

        for search in searches:
            html = self.fetch_search_page_html(
                query=search["query"],
                location=search.get("location", ""),
                start=0,
            )
            jobs = self.parse_search_page(html)

            for job in jobs:
                job["sector"] = search.get("sector")
                job["rome_family"] = search.get("rome_family")
                job["search_query"] = search["query"]
                job["search_location"] = search.get("location", "")

            all_jobs.extend(jobs)
            print(
                f"{search['query']} / {search.get('location', '')} "
                f"/ {search.get('sector', '')} -> {len(jobs)} offres"
            )

        return self._deduplicate_jobs(all_jobs)

    def collect_jobs_from_yaml(self, yaml_path: str) -> List[dict]:
        searches = self.load_searches_from_yaml(yaml_path)
        return self.collect_jobs_from_queries(searches)

    def _absolute_url(self, href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        return urljoin(self.settings.indeed_base_url, href)

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