"""
Classify companies into NOGA sectors using sentence embedding similarity.

Reads translated descriptions from data_intermediate/<input_file> and writes
uid, sector_section, sector_division to data_intermediate/<output_file>.
Resume-safe: skips UIDs already present in the output file.

Examples:
    uv run python -m swiss_companies.scripts.classify_sectors
    uv run python -m swiss_companies.scripts.classify_sectors --model all-mpnet-base-v2
    uv run python -m swiss_companies.scripts.classify_sectors --batch_size 1024
"""

import csv
from pathlib import Path

import fire
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from swiss_companies.noga import NOGA_DIVISIONS

DATA_INTERMEDIATE = Path("data_intermediate")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _label_text(code: str, name: str, description: str) -> str:
    return f"{code}: {name}. {description}"


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity. a: (N, D), b: (M, D) -> (N, M)."""
    a = a / np.linalg.norm(a, axis=1, keepdims=True)
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    return a @ b.T


# ─── Main ─────────────────────────────────────────────────────────────────────


def classify(
    input_file: str = "descriptions_en.csv",
    output_file: str = "sectors.csv",
    model: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 512,
):
    """
    Classify companies into NOGA sectors using sentence embedding similarity.

    Args:
        input_file:  CSV filename in data_intermediate/ (default: descriptions_en.csv)
        output_file: CSV filename in data_intermediate/ (default: sectors.csv)
        model:       Sentence-transformers model name (default: all-MiniLM-L6-v2)
        batch_size:  Descriptions to encode per batch (default: 512)
    """
    input_path = DATA_INTERMEDIATE / input_file
    DATA_INTERMEDIATE.mkdir(exist_ok=True)
    output_path = DATA_INTERMEDIATE / output_file

    # ── Resume: load already-classified UIDs ────────────────────────────────
    already_done: set[str] = set()
    if output_path.exists():
        with open(output_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already_done.add(row["uid"])
        print(f"Resuming: {len(already_done):,} UIDs already classified.")

    # ── Read input ───────────────────────────────────────────────────────────
    rows: list[dict] = []
    with open(input_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("description_en") and row["uid"] not in already_done:
                rows.append(row)

    total = len(rows)
    print(f"Rows to classify: {total:,}")
    if not total:
        print("Nothing to do.")
        return

    # ── Device ───────────────────────────────────────────────────────────────
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Using device: {device}")

    # ── Load model and encode NOGA labels ────────────────────────────────────
    print(f"Loading model: {model}")
    st_model = SentenceTransformer(model, device=device)

    division_codes = [d[0] for d in NOGA_DIVISIONS]
    division_section = {d[0]: d[1] for d in NOGA_DIVISIONS}
    division_texts = [_label_text(d[0], d[2], d[3]) for d in NOGA_DIVISIONS]
    division_embs = st_model.encode(
        division_texts, convert_to_numpy=True, show_progress_bar=False
    )

    print(f"Encoded {len(division_codes)} divisions.")

    # ── Classify in batches ──────────────────────────────────────────────────
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(
            out_f, fieldnames=["uid", "sector_section", "sector_division"]
        )
        if write_header:
            writer.writeheader()

        for i in tqdm(range(0, total, batch_size), desc="Classifying", unit="batch"):
            batch = rows[i : i + batch_size]
            texts = [r["description_en"] for r in batch]

            desc_embs = st_model.encode(
                texts, convert_to_numpy=True, show_progress_bar=False
            )

            division_sims = _cosine_sim(desc_embs, division_embs)
            division_idxs = division_sims.argmax(axis=1)

            for row, d_idx in zip(batch, division_idxs):
                division_code = division_codes[d_idx]
                writer.writerow(
                    {
                        "uid": row["uid"],
                        "sector_section": division_section[division_code],
                        "sector_division": division_code,
                    }
                )

            out_f.flush()

    print(f"\nDone. {total:,} companies classified → {output_path}")


if __name__ == "__main__":
    fire.Fire(classify)
