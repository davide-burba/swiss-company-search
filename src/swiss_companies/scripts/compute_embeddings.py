"""
Compute and store sentence embeddings for semantic search.

Encodes each company as "{legal_name}. {description_en}" (or just the name
when no description is available) using a sentence-transformers model and
writes the resulting vector directly into the `embedding` column.

Resume-safe: only processes rows where embedding IS NULL.

Examples:
    uv run python -m swiss_companies.scripts.compute_embeddings
    uv run python -m swiss_companies.scripts.compute_embeddings --model all-mpnet-base-v2
    uv run python -m swiss_companies.scripts.compute_embeddings --batch_size 256
"""

import fire
import torch
from sentence_transformers import SentenceTransformer
from sqlalchemy import func, select, update
from tqdm import tqdm

from swiss_companies.config import EMBEDDING_MODEL, GlobalConfig
from swiss_companies.database import DelayedDB
from swiss_companies.models import ZefixCompany


def _company_text(legal_name: str, description_en: str | None) -> str:
    if description_en:
        return f"{legal_name}. {description_en}"
    return legal_name


def compute(
    model: str = EMBEDDING_MODEL,
    batch_size: int = 512,
):
    """
    Compute sentence embeddings and store them in the database.

    Args:
        model:      Sentence-transformers model name (default: all-MiniLM-L6-v2)
        batch_size: Companies to encode per batch (default: 512)
    """
    config = GlobalConfig()
    db = DelayedDB()
    db.setup(config.db_url.get_secret_value())

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using device: {device}")
    print(f"Loading model: {model}")
    st_model = SentenceTransformer(model, device=device)

    with db.engine.connect() as conn:
        total_remaining = conn.scalar(
            select(func.count()).select_from(ZefixCompany).where(ZefixCompany.embedding.is_(None))
        ) or 0
        print(f"Companies without embeddings: {total_remaining:,}")
        if not total_remaining:
            print("Nothing to do.")
            return
        rows = list(conn.execute(
            select(ZefixCompany.uid, ZefixCompany.legal_name, ZefixCompany.description_en)
            .where(ZefixCompany.embedding.is_(None))
        ))

    print(f"Encoding {len(rows):,} companies in batches of {batch_size}…")
    with db.engine.begin() as conn:
        for i in tqdm(range(0, len(rows), batch_size), desc="Embedding", unit="batch"):
            batch = rows[i : i + batch_size]
            texts = [_company_text(r.legal_name, r.description_en) for r in batch]
            embeddings = st_model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            for row, emb in zip(batch, embeddings):
                conn.execute(
                    update(ZefixCompany)
                    .where(ZefixCompany.uid == row.uid)
                    .values(embedding=emb.tolist())
                )

    print(f"\nDone. {len(rows):,} embeddings stored.")


if __name__ == "__main__":
    fire.Fire(compute)
