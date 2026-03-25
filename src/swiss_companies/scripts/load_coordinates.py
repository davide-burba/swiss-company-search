"""
Load geocoded coordinates into the zefix_companies table.

Reads coordinates from data_intermediate/<input_file> and updates
lat / lng only for UIDs already in the database.

Examples:
    uv run python -m swiss_companies.scripts.load_coordinates
    uv run python -m swiss_companies.scripts.load_coordinates --input_file coordinates.csv
    uv run python -m swiss_companies.scripts.load_coordinates --batch_size 5000
"""

import csv
from pathlib import Path

import fire
from sqlalchemy import text

from swiss_companies.config import GlobalConfig
from swiss_companies.database import db

DATA_INTERMEDIATE = Path("data_intermediate")


def _read_coordinates(path: Path) -> dict[str, dict]:
    """Read coordinates CSV, deduplicating by uid (last entry wins)."""
    rows: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["uid"]] = {
                "uid": row["uid"],
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
            }
    return rows


def load(
    input_file: str = "coordinates.csv",
    batch_size: int = 1000,
):
    """
    Load geocoded coordinates into the zefix_companies table.

    Only updates rows whose UIDs already exist in the database.

    Args:
        input_file:  CSV filename in data_intermediate/ (default: coordinates.csv)
        batch_size:  Number of rows to update per batch (default: 1000)
    """
    input_path = DATA_INTERMEDIATE / input_file
    if not input_path.exists():
        raise FileNotFoundError(f"Coordinates file not found: {input_path}")

    config = GlobalConfig()
    db.setup(config.db_url.get_secret_value())

    coordinates = _read_coordinates(input_path)
    print(f"Read {len(coordinates):,} coordinates from {input_path}")

    stmt = text("UPDATE zefix_companies SET lat = :lat, lng = :lng WHERE uid = :uid")

    with db.engine.begin() as conn:
        db_uids = {
            row[0] for row in conn.execute(text("SELECT uid FROM zefix_companies"))
        }
        print(f"Found {len(db_uids):,} UIDs in the database")

        rows = [v for uid, v in coordinates.items() if uid in db_uids]
        skipped = len(coordinates) - len(rows)
        print(f"Matched {len(rows):,} coordinates ({skipped:,} skipped — not in DB)")

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
