import csv
import random
from pathlib import Path

import fire

RAW_DIR = Path("data_raw")


def sample(csv_path: str, n: int = 10000, seed: int = 42):
    """
    Generate a random sample CSV from an existing Zefix CSV file.

    Args:
        csv_path: Path to the source CSV file
        n:        Number of rows to sample (default: 10000)
        seed:     Random seed for reproducibility (default: 42)

    Examples:
        python sample_zefix.py data_raw/companies.csv
        python sample_zefix.py data_raw/companies.csv --n 5000 --seed 7
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    random.seed(seed)
    sampled = random.sample(rows, min(n, len(rows)))
    print(f"Sampled {len(sampled):,} / {len(rows):,} rows (seed={seed})")

    out_path = RAW_DIR / f"companies_sample_{n}_seed{seed}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(sampled)
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    fire.Fire(sample)
