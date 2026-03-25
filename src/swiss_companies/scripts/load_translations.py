"""
Load translated descriptions into the zefix_companies table.

Reads translations from data_intermediate/<input_file> and updates
description_lang / description_en only for UIDs already in the database.

Examples:
    uv run python -m swiss_companies.scripts.load_translations
    uv run python -m swiss_companies.scripts.load_translations --input_file descriptions_en.csv
    uv run python -m swiss_companies.scripts.load_translations --batch_size 5000
"""

import csv
from pathlib import Path

import fire
from sqlalchemy import text

from swiss_companies.config import GlobalConfig
from swiss_companies.database import db

DATA_INTERMEDIATE = Path("data_intermediate")


def _read_translations(path: Path) -> dict[str, dict]:
    """Read translations CSV, deduplicating by uid (last entry wins)."""
    rows: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["uid"]] = {
                "uid": row["uid"],
                "description_lang": row["description_lang"],
                "description_en": row["description_en"],
            }
    return rows


def load(
    input_file: str = "descriptions_en.csv",
    batch_size: int = 1000,
):
    """
    Load translated descriptions into the zefix_companies table.

    Only updates rows whose UIDs already exist in the database.

    Args:
        input_file:  CSV filename in data_intermediate/ (default: descriptions_en.csv)
        batch_size:  Number of rows to update per batch (default: 1000)
    """
    input_path = DATA_INTERMEDIATE / input_file
    if not input_path.exists():
        raise FileNotFoundError(f"Translations file not found: {input_path}")

    config = GlobalConfig()
    db.setup(config.db_url.get_secret_value())

    translations = _read_translations(input_path)
    print(f"Read {len(translations):,} translations from {input_path}")

    stmt = text(
        "UPDATE zefix_companies "
        "SET description_lang = :description_lang, description_en = :description_en "
        "WHERE uid = :uid"
    )

    with db.engine.begin() as conn:
        db_uids = {row[0] for row in conn.execute(text("SELECT uid FROM zefix_companies"))}
        print(f"Found {len(db_uids):,} UIDs in the database")

        rows = [v for uid, v in translations.items() if uid in db_uids]
        skipped = len(translations) - len(rows)
        print(f"Matched {len(rows):,} translations ({skipped:,} skipped — not in DB)")

        if not rows:
            print("Nothing to load.")
            return

        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            conn.execute(stmt, batch)
            total += len(batch)
            print(f"  updated {total:,} / {len(rows):,}", end="\r", flush=True)

    print(f"\nDone. {total:,} rows updated in zefix_companies.")


if __name__ == "__main__":
    fire.Fire(load)
