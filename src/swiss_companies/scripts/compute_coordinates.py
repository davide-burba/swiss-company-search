"""
Geocode company addresses using a local Nominatim instance.

Reads addresses from data_raw/<input_file>, writes uid/lat/lng to
data_intermediate/<output_file>. Resume-safe: skips UIDs already in
the output file.

Prerequisites:
    Start a local Nominatim container loaded with the Switzerland extract:

        docker run -e PBF_URL=https://download.geofabrik.de/europe/switzerland-latest.osm.pbf \\
            -p 8080:8080 mediagis/nominatim:4.4

    Import the output file with: just load-geocoding <output_file>

Examples:
    just geocode
    just geocode --workers 16
    just geocode --input_file companies_TI_ZH.csv
"""

import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fire
import requests
from tqdm import tqdm

DATA_RAW = Path("data_raw")
DATA_INTERMEDIATE = Path("data_intermediate")
DEFAULT_NOMINATIM_URL = "http://localhost:8080"


def _geocode_one(
    uid: str,
    street: str | None,
    zip_: str | None,
    city: str,
    nominatim_url: str,
    session: requests.Session,
) -> tuple[str, float | None, float | None]:
    params: dict = {"format": "json", "limit": 1, "countrycodes": "ch"}
    if street:
        params["street"] = street
    if zip_:
        params["postalcode"] = zip_
    params["city"] = city

    try:
        r = session.get(f"{nominatim_url}/search", params=params, timeout=10)
        r.raise_for_status()
        results = r.json()
        if results:
            return uid, float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return uid, None, None


def geocode(
    input_file: str = "companies.csv",
    output_file: str = "coordinates.csv",
    nominatim_url: str = DEFAULT_NOMINATIM_URL,
    workers: int = 8,
    limit: int = 0,
):
    """
    Geocode company addresses using a local Nominatim instance.

    Args:
        input_file:    CSV filename in data_raw/ (default: companies.csv)
        output_file:   CSV filename in data_intermediate/ (default: coordinates.csv)
        nominatim_url: Base URL of the local Nominatim instance (default: http://localhost:8080)
        workers:       Number of parallel HTTP workers (default: 8)
        limit:         Max rows to process, 0 = all (default: 0)
    """
    input_path = DATA_RAW / input_file
    DATA_INTERMEDIATE.mkdir(exist_ok=True)
    output_path = DATA_INTERMEDIATE / output_file

    # Resume: load already-geocoded UIDs
    already_done: set[str] = set()
    if output_path.exists():
        with open(output_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already_done.add(row["uid"])
        print(f"Resuming: {len(already_done):,} UIDs already geocoded.")

    # Read input, deduplicate by uid
    seen_uids: set[str] = set()
    rows: list[dict] = []
    with open(input_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["uid"] in seen_uids or row["uid"] in already_done:
                continue
            seen_uids.add(row["uid"])
            rows.append(row)

    if limit:
        rows = rows[:limit]

    total = len(rows)
    print(f"Addresses to geocode: {total:,}")
    if not total:
        print("Nothing to do.")
        return

    http = requests.Session()
    http.headers["User-Agent"] = "swiss-companies-geocoder/1.0"

    geocoded = 0
    failed = 0
    start = time.time()

    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=["uid", "lat", "lng"])
        if write_header:
            writer.writeheader()

        with tqdm(total=total, unit="addr") as pbar:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _geocode_one,
                        row["uid"],
                        row.get("street") or None,
                        row.get("zip") or None,
                        row["city"],
                        nominatim_url,
                        http,
                    ): row["uid"]
                    for row in rows
                }
                for future in as_completed(futures):
                    uid, lat, lng = future.result()
                    if lat is not None:
                        writer.writerow({"uid": uid, "lat": lat, "lng": lng})
                        out_f.flush()
                        geocoded += 1
                    else:
                        failed += 1
                    pbar.update(1)

    elapsed = time.time() - start
    rate = total / elapsed if elapsed > 0 else 0
    print(
        f"\nDone in {elapsed / 60:.1f} min ({rate:.0f} addr/sec) — "
        f"geocoded: {geocoded:,}, failed/no result: {failed:,}"
    )
    print(f"Output → {output_path}")


if __name__ == "__main__":
    fire.Fire(geocode)
