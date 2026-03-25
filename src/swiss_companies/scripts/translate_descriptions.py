"""
Translate company descriptions to English using Helsinki-NLP/Opus-MT
models via CTranslate2.

Reads descriptions from data_raw/<input_file> and writes results to
data_intermediate/<output_file>. Resume-safe: skips UIDs already present
in the output file. Models are converted to CTranslate2 format on first
use and cached in models/.

Examples:
    uv run python -m swiss_companies.scripts.translate_descriptions
    uv run python -m swiss_companies.scripts.translate_descriptions --input_file companies_TI_ZH.csv
    uv run python -m swiss_companies.scripts.translate_descriptions --inter_threads 8
"""

import csv
import subprocess
import time
import warnings
from collections import defaultdict
from pathlib import Path
from urllib.request import urlretrieve

import ctranslate2
import fasttext
import fire
from tqdm import tqdm
from transformers import MarianTokenizer

warnings.filterwarnings("ignore", category=FutureWarning)

DATA_RAW = Path("data_raw")
DATA_INTERMEDIATE = Path("data_intermediate")
MODELS_DIR = Path("models")
FASTTEXT_MODEL_PATH = MODELS_DIR / "lid.176.bin"
FASTTEXT_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"

LANG_TO_MODEL = {
    "de": "Helsinki-NLP/opus-mt-de-en",
    "it": "Helsinki-NLP/opus-mt-it-en",
    "fr": "Helsinki-NLP/opus-mt-fr-en",
}
FALLBACK_MODEL = "Helsinki-NLP/opus-mt-mul-en"

MAX_INPUT_TOKENS = 512
LOG_EVERY_N_ROWS = 5_000


# ─── Language Detection (fasttext — ~1000x faster than langdetect) ───────────


def _ensure_fasttext_model() -> fasttext.FastText._FastText:
    if not FASTTEXT_MODEL_PATH.exists():
        MODELS_DIR.mkdir(exist_ok=True)
        tqdm.write("Downloading fasttext language-detection model (once)...")
        urlretrieve(FASTTEXT_URL, str(FASTTEXT_MODEL_PATH))
    return fasttext.load_model(str(FASTTEXT_MODEL_PATH))


def _detect_langs_batch(
    texts: list[str], model: fasttext.FastText._FastText
) -> list[str]:
    """Detect languages for a batch of texts. Returns ISO 639-1 codes."""
    cleaned = [t.replace("\n", " ").strip() if t else "" for t in texts]
    labels, _ = model.predict(cleaned)
    return [l[0].replace("__label__", "") if l else "unknown" for l in labels]


# ─── Model Loading (same converter approach as original) ─────────────────────


def _load_model(model_name: str, compute_type: str, inter_threads: int):
    model_dir = MODELS_DIR / model_name.replace("/", "__")
    if not model_dir.exists():
        tqdm.write(f"Converting {model_name} to CTranslate2 format (one-time)...")
        MODELS_DIR.mkdir(exist_ok=True)
        subprocess.run(
            [
                "ct2-transformers-converter",
                "--model",
                model_name,
                "--output_dir",
                str(model_dir),
                "--quantization",
                compute_type,
                "--force",
            ],
            check=True,
        )
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    translator = ctranslate2.Translator(
        str(model_dir),
        device="cpu",
        inter_threads=inter_threads,
        compute_type=compute_type,
    )
    return tokenizer, translator


def _translate_batch(
    texts: list[str], tokenizer, translator
) -> tuple[list[str], list[bool]]:
    """Translate a batch. Returns (translations, truncated_flags)."""
    input_tokens = []
    truncated = []
    for t in texts:
        tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(t))
        if len(tokens) > MAX_INPUT_TOKENS:
            tqdm.write(
                f"  ⚠ Truncating input from {len(tokens)} to {MAX_INPUT_TOKENS} tokens"
            )
            tokens = tokens[:MAX_INPUT_TOKENS]
            truncated.append(True)
        else:
            truncated.append(False)
        input_tokens.append(tokens)

    results = translator.translate_batch(input_tokens)
    output_ids = [tokenizer.convert_tokens_to_ids(r.hypotheses[0]) for r in results]
    return tokenizer.batch_decode(output_ids, skip_special_tokens=True), truncated


# ─── Status Logging ─────────────────────────────────────────────────────────


class ProgressLogger:
    def __init__(self, total: int):
        self.total = total
        self.start_time = time.time()
        self.translated = 0
        self.lang_counts: dict[str, int] = defaultdict(int)

    def update(self, n: int, lang: str):
        self.translated += n
        self.lang_counts[lang] += n

    def log_status(self):
        elapsed = time.time() - self.start_time
        rate = self.translated / elapsed if elapsed > 0 else 0
        remaining = self.total - self.translated
        eta_min = (remaining / rate / 60) if rate > 0 else float("inf")
        langs = ", ".join(f"{k}={v:,}" for k, v in sorted(self.lang_counts.items()))
        tqdm.write(
            f"  ⟶ {self.translated:,}/{self.total:,} done "
            f"| {rate:.0f} rows/sec "
            f"| ETA {eta_min:.0f} min "
            f"| langs: {langs}"
        )


# ─── Main Pipeline ──────────────────────────────────────────────────────────


def translate(
    input_file: str = "companies.csv",
    output_file: str = "descriptions_en.csv",
    batch_size: int = 512,
    compute_type: str = "int8",
    inter_threads: int = 1,
    limit: int = 0,
):
    """
    Translate company descriptions to English using Helsinki-NLP/Opus-MT
    models via CTranslate2.

    Args:
        input_file:    CSV filename in data_raw/ (default: companies.csv)
        output_file:   CSV filename in data_intermediate/ (default: descriptions_en.csv)
        batch_size:    Number of texts per translation call (default: 512)
        compute_type:  CTranslate2 quantization (default: int8)
        inter_threads: Number of parallel translation workers (default: 1)
        limit:         Max rows to process, 0 = all (default: 0)
    """
    input_path = DATA_RAW / input_file
    DATA_INTERMEDIATE.mkdir(exist_ok=True)
    output_path = DATA_INTERMEDIATE / output_file

    # ── Resume: load already-translated UIDs ────────────────────────────────
    already_done: set[str] = set()
    if output_path.exists():
        with open(output_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already_done.add(row["uid"])
        print(f"Resuming: {len(already_done):,} UIDs already translated.")

    # ── Read input, deduplicate by uid ──────────────────────────────────────
    seen_uids: set[str] = set()
    all_rows: list[dict] = []
    with open(input_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["uid"] in seen_uids:
                continue
            seen_uids.add(row["uid"])
            all_rows.append(row)

    rows = [
        r for r in all_rows if r.get("description") and r["uid"] not in already_done
    ]
    if limit:
        rows = rows[:limit]

    total = len(rows)
    print(f"Rows to translate: {total:,}")
    if not total:
        print("Nothing to do.")
        return

    # ── Batch language detection (fasttext) ─────────────────────────────────
    print("Detecting languages (fasttext) ...")
    t_detect = time.time()
    ft_model = _ensure_fasttext_model()
    all_descriptions = [r["description"] for r in rows]
    all_langs = _detect_langs_batch(all_descriptions, ft_model)
    del ft_model  # free memory before loading translation models
    print(f"Language detection done in {time.time() - t_detect:.1f}s")

    for row, lang in zip(rows, all_langs):
        row["_lang"] = lang

    lang_counts = defaultdict(int)
    for lang in all_langs:
        lang_counts[lang] += 1
    print(
        "Language distribution: "
        f"{dict(sorted(lang_counts.items(), key=lambda x: -x[1]))}"
    )

    # ── Group by language for efficient batching ────────────────────────────
    lang_groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        lang_groups[row["_lang"]].append(row)

    # ── Translate ───────────────────────────────────────────────────────────
    loaded_models: dict[str, tuple] = {}
    progress = ProgressLogger(total)

    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(
            out_f, fieldnames=["uid", "description_lang", "description_en", "truncated"]
        )
        if write_header:
            writer.writeheader()

        pbar = tqdm(total=total, desc="Translating", unit="row")

        # Process largest language groups first for better progress visibility
        for lang, group in sorted(lang_groups.items(), key=lambda x: -len(x[1])):
            model_name = LANG_TO_MODEL.get(
                lang, FALLBACK_MODEL if lang != "en" else None
            )

            if model_name and model_name not in loaded_models:
                tqdm.write(
                    f"Loading model: {model_name} (for {lang}, {len(group):,} rows)"
                )
                loaded_models[model_name] = _load_model(
                    model_name, compute_type, inter_threads
                )

            for i in range(0, len(group), batch_size):
                batch = group[i : i + batch_size]
                texts = [r["description"] for r in batch]

                if model_name is None:
                    # English passthrough
                    translations = texts
                    truncated_flags = [False] * len(texts)
                else:
                    tok, translator = loaded_models[model_name]
                    translations, truncated_flags = _translate_batch(
                        texts, tok, translator
                    )

                for row, translation, was_truncated in zip(
                    batch, translations, truncated_flags
                ):
                    writer.writerow(
                        {
                            "uid": row["uid"],
                            "description_lang": lang,
                            "description_en": translation,
                            "truncated": was_truncated,
                        }
                    )

                out_f.flush()
                pbar.update(len(batch))
                progress.update(len(batch), lang)

                if progress.translated % LOG_EVERY_N_ROWS < batch_size:
                    progress.log_status()

        pbar.close()

    elapsed = time.time() - progress.start_time
    print(
        f"\nDone. {total:,} descriptions translated in {elapsed / 60:.1f} min "
        f"→ {output_path}"
    )


if __name__ == "__main__":
    fire.Fire(translate)
