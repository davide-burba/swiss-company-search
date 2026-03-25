import csv
from pathlib import Path

import fire
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from swiss_companies.config import GlobalConfig
from swiss_companies.database import db
from swiss_companies.models import ZefixCompany


def _read_csv(path: Path) -> list[dict]:
    seen = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seen[row["uid"]] = {
                "uid": row["uid"],
                "org": row["org"],
                "legal_name": row["legalName"],
                "legal_form": row["legalForm"].split("/")[-1],
                "canton": row["canton"],
                "city": row["city"],
                "street": row.get("street") or None,
                "zip": row.get("zip") or None,
                "description": row.get("description") or None,
            }
    return list(seen.values())


def _upsert(rows: list[dict], batch_size: int) -> None:
    total = 0
    with Session(db.engine) as session:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            stmt = insert(ZefixCompany).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["uid"],
                set_={
                    "org": stmt.excluded.org,
                    "legal_name": stmt.excluded.legal_name,
                    "legal_form": stmt.excluded.legal_form,
                    "canton": stmt.excluded.canton,
                    "city": stmt.excluded.city,
                    "street": stmt.excluded.street,
                    "zip": stmt.excluded.zip,
                    "description": stmt.excluded.description,
                },
            )
            session.execute(stmt)
            total += len(batch)
            print(f"  upserted {total:,} / {len(rows):,}", end="\r", flush=True)
        session.commit()
    print(f"\nDone. {total:,} rows upserted into zefix_companies.")


def load(csv_path: str, batch_size: int = 1000):
    """
    Load Zefix company data from a CSV file into the zefix_companies table.

    Args:
        csv_path:   Path to the CSV file produced by fetch_zefix.py
        batch_size: Number of rows to upsert per batch (default: 1000)

    Examples:
        python load_zefix.py load data_raw/companies_TI_ZH.csv
        python load_zefix.py load data_raw/companies.csv --batch_size 5000
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    config = GlobalConfig()
    db.setup(config.db_url.get_secret_value())

    rows = _read_csv(path)
    print(f"Loaded {len(rows):,} rows from {path} (deduplicated by uid)")
    _upsert(rows, batch_size)


if __name__ == "__main__":
    fire.Fire(load)
