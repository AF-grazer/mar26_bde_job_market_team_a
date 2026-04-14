from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from psycopg import connect
from psycopg.types.json import Json

load_dotenv()


DATA_DIR = Path("data/raw")
FRANCE_TRAVAIL_URL = "https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"


def build_connection_string() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "job_market")
    user = os.getenv("POSTGRES_USER", "job_market")
    password = os.getenv("POSTGRES_PASSWORD", "job_market")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def build_raw_hash(payload: dict) -> str:
    raw_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def iter_json_files(source_name: str) -> Iterable[Path]:
    source_dir = DATA_DIR / source_name
    if not source_dir.exists():
        return []
    return sorted(source_dir.glob("*.json"))


def load_json_file(file_path: Path) -> dict | list:
    return json.loads(file_path.read_text(encoding="utf-8"))


def extract_france_travail_records(file_path: Path) -> list[dict]:
    payload = load_json_file(file_path)
    offers = payload.get("resultats", []) if isinstance(payload, dict) else []
    records: list[dict] = []

    for offer in offers:
        source_offer_id = offer.get("id")
        source_url = (
            offer.get("origineOffre", {}).get("urlOrigine")
            or offer.get("contact", {}).get("urlPostulation")
            or (FRANCE_TRAVAIL_URL.format(offer_id=source_offer_id) if source_offer_id else None)
        )

        records.append(
            {
                "source_system": "france_travail",
                "source_offer_id": source_offer_id,
                "source_url": source_url,
                "source_file_name": file_path.name,
                "source_file_path": str(file_path.as_posix()),
                "raw_hash": build_raw_hash(offer),
                "raw_payload": offer,
            }
        )

    return records


def extract_indeed_records(file_path: Path) -> list[dict]:
    payload = load_json_file(file_path)
    offers = payload if isinstance(payload, list) else []
    records: list[dict] = []

    for offer in offers:
        records.append(
            {
                "source_system": "indeed",
                "source_offer_id": offer.get("source_job_id"),
                "source_url": offer.get("job_url"),
                "source_file_name": file_path.name,
                "source_file_path": str(file_path.as_posix()),
                "raw_hash": build_raw_hash(offer),
                "raw_payload": offer,
            }
        )

    return records


def insert_records(table_name: str, records: list[dict]) -> int:
    if not records:
        return 0

    insert_sql = f"""
        insert into landing.{table_name} (
            source_system,
            source_offer_id,
            source_url,
            source_file_name,
            source_file_path,
            raw_hash,
            raw_payload
        )
        values (
            %(source_system)s,
            %(source_offer_id)s,
            %(source_url)s,
            %(source_file_name)s,
            %(source_file_path)s,
            %(raw_hash)s,
            %(raw_payload)s
        )
    """

    prepared_records = [
        {**record, "raw_payload": Json(record["raw_payload"])}
        for record in records
    ]

    with connect(build_connection_string()) as conn:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, prepared_records)
        conn.commit()

    return len(records)


def load_france_travail() -> int:
    total_inserted = 0

    for file_path in iter_json_files("france_travail"):
        records = extract_france_travail_records(file_path)
        inserted = insert_records("raw_france_travail_offers", records)
        total_inserted += inserted
        print(f"[france_travail] {file_path.name}: {inserted} offres chargees")

    return total_inserted


def load_indeed() -> int:
    total_inserted = 0

    for file_path in iter_json_files("indeed"):
        records = extract_indeed_records(file_path)
        inserted = insert_records("raw_indeed_offers", records)
        total_inserted += inserted
        print(f"[indeed] {file_path.name}: {inserted} offres chargees")

    return total_inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load raw JSON offers into PostgreSQL landing tables.")
    parser.add_argument(
        "--source",
        choices=["all", "france_travail", "indeed"],
        default="all",
        help="Choose which source to load.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total_inserted = 0

    if args.source in {"all", "france_travail"}:
        total_inserted += load_france_travail()

    if args.source in {"all", "indeed"}:
        total_inserted += load_indeed()

    print(f"Total inserted rows: {total_inserted}")


if __name__ == "__main__":
    main()
