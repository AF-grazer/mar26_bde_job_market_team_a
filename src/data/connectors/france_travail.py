from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import requests

from src.data.connectors.collection_targets import (
    build_france_travail_targets,
    load_collection_targets,
)
from src.settings import settings

logger = logging.getLogger(__name__)
MAX_FRANCE_TRAVAIL_PAGE_SIZE = 150


def build_range_param(start: int = 0, page_size: int = MAX_FRANCE_TRAVAIL_PAGE_SIZE) -> str:
    effective_page_size = max(1, min(page_size, MAX_FRANCE_TRAVAIL_PAGE_SIZE))
    end = start + effective_page_size - 1
    return f"{start}-{end}"


class FranceTravailClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self._access_token: str | None = None
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    def get_access_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": settings.france_travail_client_id.strip(),
            "client_secret": settings.france_travail_client_secret.strip(),
            "scope": settings.france_travail_scope.strip(),
        }

        response = self.session.post(
            settings.france_travail_token_url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=settings.request_timeout,
        )

        logger.info("France Travail token response status=%s", response.status_code)

        response.raise_for_status()
        return response.json()["access_token"]

    def search_offers(self, params: dict) -> dict:
        if self._access_token is None:
            self._access_token = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        response = self.session.get(
            f"{settings.france_travail_base_url.rstrip('/')}/offres/search",
            headers=headers,
            params=params,
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def load_targets_from_file(self, yaml_path: str) -> list[dict]:
        return build_france_travail_targets(load_collection_targets(yaml_path))

    def collect_offers_from_targets(
        self,
        targets: list[dict],
        max_pages_per_target: int | None = None,
    ) -> dict:
        requests_metadata: list[dict] = []
        aggregated_offers: list[dict] = []

        for target in targets:
            rome_codes = target.get("rome_codes", [])
            geo_values = target.get("departements") or target.get("regions") or [None]
            geo_param = "departement" if target.get("departements") else "region" if target.get("regions") else None

            for rome_code in rome_codes:
                for geo_value in geo_values:
                    page_index = 0

                    while True:
                        params = {
                            "range": build_range_param(start=page_index * MAX_FRANCE_TRAVAIL_PAGE_SIZE),
                            "codeROME": rome_code,
                        }
                        if geo_param and geo_value:
                            params[geo_param] = geo_value

                        payload = self.search_offers(params)
                        offers = payload.get("resultats", [])

                        requests_metadata.append(
                            {
                                "sector_slug": target.get("sector_slug"),
                                "sector_label": target.get("sector_label"),
                                "rome_family": target.get("rome_family"),
                                "code_rome": rome_code,
                                "geo_param": geo_param,
                                "geo_value": geo_value,
                                "range": params["range"],
                                "offer_count": len(offers),
                            }
                        )

                        for offer in offers:
                            enriched_offer = dict(offer)
                            enriched_offer["_collection_context"] = {
                                "sector_slug": target.get("sector_slug"),
                                "sector_label": target.get("sector_label"),
                                "rome_family": target.get("rome_family"),
                                "code_rome": rome_code,
                                "geo_param": geo_param,
                                "geo_value": geo_value,
                                "range": params["range"],
                            }
                            aggregated_offers.append(enriched_offer)

                        print(
                            f"[France Travail] {target.get('sector_slug')} / {rome_code} / "
                            f"{geo_param or 'all'}={geo_value or 'all'} / {params['range']} -> {len(offers)} offres"
                        )

                        page_index += 1

                        if len(offers) < MAX_FRANCE_TRAVAIL_PAGE_SIZE:
                            break

                        if max_pages_per_target is not None and page_index >= max_pages_per_target:
                            break

        return {
            "collected_at": datetime.utcnow().isoformat(),
            "requests": requests_metadata,
            "resultats": aggregated_offers,
        }

    @staticmethod
    def save_raw(payload: dict, filename_prefix: str = "france_travail") -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("data/raw/france_travail")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{filename_prefix}_{timestamp}.json"
        output_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_file
