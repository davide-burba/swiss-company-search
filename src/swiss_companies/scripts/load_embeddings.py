"""
Load precomputed embeddings into the database.

Reads uid/embedding pairs from data_intermediate/<input_file> and updates
the embedding column in the database.

Examples:
    uv run python -m swiss_companies.scripts.load_embeddings
    uv run python -m swiss_companies.scripts.load_embeddings --input_file embeddings_1000.csv
"""

import csv
import json
from pathlib import Path

import fire
from sqlalchemy import update
from tqdm import tqdm

from swiss_companies.config import GlobalConfig
from swiss_companies.database import DelayedDB
from swiss_companies.models import ZefixCompany

DATA_INTERMEDIATE = Path("data_intermediate")


def load(
    input_file: str = "embeddings.csv",
    batch_size: int = 512,
):
    """
    Load embeddings from a CSV file into the database.

    Args:
        input_file:  CSV filename in data_intermediate/ (default: embeddings.csv)
        batch_size:  Rows to update per transaction (default: 512)
    """
    input_path = DATA_INTERMEDIATE / input_file

    rows = []
    with open(input_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({"uid": row["uid"], "embedding": json.loads(row["embedding"])})

    print(f"Loading {len(rows):,} embeddings into the database…")

    config = GlobalConfig()
    db = DelayedDB()
    db.setup(config.db_url.get_secret_value())

    with db.engine.begin() as conn:
        for i in tqdm(range(0, len(rows), batch_size), desc="Loading", unit="batch"):
            batch = rows[i : i + batch_size]
            for row in batch:
                conn.execute(
                    update(ZefixCompany)
                    .where(ZefixCompany.uid == row["uid"])
                    .values(embedding=row["embedding"])
                )

    print(f"Done. {len(rows):,} embeddings loaded.")


if __name__ == "__main__":
    fire.Fire(load)
