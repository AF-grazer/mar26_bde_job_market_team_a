from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import requests

from src.settings import settings


class FranceTravailClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.user_agent,
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

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["access_token"]

    def search_offers(self, params: dict) -> dict:
        token = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
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