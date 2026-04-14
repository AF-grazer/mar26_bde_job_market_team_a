from __future__ import annotations

from pathlib import Path

import yaml


def load_collection_targets(yaml_path: str) -> list[dict]:
    path = Path(yaml_path)
    content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return content.get("targets", [])


def build_indeed_searches(targets: list[dict]) -> list[dict]:
    searches: list[dict] = []

    for target in targets:
        for search in target.get("indeed_searches", []):
            searches.append(
                {
                    "sector_slug": target.get("sector_slug"),
                    "sector_label": target.get("sector_label"),
                    "rome_family": target.get("rome_family"),
                    "rome_codes": target.get("rome_codes", []),
                    "regions": target.get("regions", []),
                    "departements": target.get("departements", []),
                    "query": search.get("query", ""),
                    "location": search.get("location", ""),
                }
            )

    return searches


def build_france_travail_targets(targets: list[dict]) -> list[dict]:
    france_travail_targets: list[dict] = []

    for target in targets:
        france_travail_targets.append(
            {
                "sector_slug": target.get("sector_slug"),
                "sector_label": target.get("sector_label"),
                "rome_family": target.get("rome_family"),
                "rome_codes": target.get("rome_codes", []),
                "regions": target.get("regions", []),
                "departements": target.get("departements", []),
            }
        )

    return france_travail_targets
