"""
Compute sentence embeddings for semantic search.

Reads companies from data_raw/<companies_file> and translations from
data_intermediate/<descriptions_file>, encodes each company as
"{legal_name}. {description_en}" (or just the name when no description
is available) using a sentence-transformers model, and writes uid/embedding
pairs to data_intermediate/<output_file>.

Resume-safe: skips UIDs already present in the output file.

Examples:
    uv run python -m swiss_companies.scripts.compute_embeddings
    uv run python -m swiss_companies.scripts.compute_embeddings --model all-mpnet-base-v2
    uv run python -m swiss_companies.scripts.compute_embeddings --companies_file companies_1000.csv
"""

import csv
import json
from pathlib import Path

import fire
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

DATA_RAW = Path("data_raw")
DATA_INTERMEDIATE = Path("data_intermediate")


def _company_text(legal_name: str, description_en: str | None) -> str:
    if description_en:
        return f"{legal_name}. {description_en}"
    return legal_name


def compute(
    companies_file: str = "companies.csv",
    descriptions_file: str = "descriptions_en.csv",
    output_file: str = "embeddings.csv",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 512,
):
    """
    Compute sentence embeddings and write them to a CSV file.

    Args:
        companies_file:   CSV filename in data_raw/ (default: companies.csv)
        descriptions_file: CSV filename in data_intermediate/ (default: descriptions_en.csv)
        output_file:      CSV filename in data_intermediate/ (default: embeddings.csv)
        model:            Sentence-transformers model name (default: all-MiniLM-L6-v2)
        batch_size:       Companies to encode per batch (default: 512)
    """
    companies_path = DATA_RAW / companies_file
    descriptions_path = DATA_INTERMEDIATE / descriptions_file
    output_path = DATA_INTERMEDIATE / output_file
    DATA_INTERMEDIATE.mkdir(exist_ok=True)

    # ── Resume: load already-computed UIDs ───────────────────────────────────
    already_done: set[str] = set()
    if output_path.exists():
        with open(output_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already_done.add(row["uid"])
        print(f"Resuming: {len(already_done):,} UIDs already computed.")

    # ── Load descriptions ─────────────────────────────────────────────────────
    descriptions: dict[str, str] = {}
    if descriptions_path.exists():
        with open(descriptions_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                descriptions[row["uid"]] = row["description_en"]

    # ── Load companies ────────────────────────────────────────────────────────
    rows = []
    with open(companies_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["uid"] not in already_done:
                rows.append({"uid": row["uid"], "legal_name": row["legalName"]})

    if not rows:
        print("Nothing to do.")
        return

    print(f"Encoding {len(rows):,} companies in batches of {batch_size}…")

    # ── Device ────────────────────────────────────────────────────────────────
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using device: {device}")
    print(f"Loading model: {model}")
    st_model = SentenceTransformer(model, device=device)

    # ── Encode and write ──────────────────────────────────────────────────────
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=["uid", "embedding"])
        if write_header:
            writer.writeheader()

        for i in tqdm(range(0, len(rows), batch_size), desc="Embedding", unit="batch"):
            batch = rows[i : i + batch_size]
            texts = [
                _company_text(r["legal_name"], descriptions.get(r["uid"]))
                for r in batch
            ]
            embeddings = st_model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            for row, emb in zip(batch, embeddings):
                writer.writerow(
                    {"uid": row["uid"], "embedding": json.dumps(emb.tolist())}
                )

    print(f"\nDone. {len(rows):,} embeddings saved → {output_path}")


if __name__ == "__main__":
    fire.Fire(compute)
