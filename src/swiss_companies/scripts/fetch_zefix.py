import csv
import json
import time
from pathlib import Path

import fire
import requests

SPARQL_ENDPOINT = "https://lindas.admin.ch/query"

QUERY = """
PREFIX schema: <http://schema.org/>
PREFIX admin: <https://schema.ld.admin.ch/>

SELECT ?org ?legalName ?uid ?legalForm ?description ?street ?zip ?city ?canton
WHERE {{
  GRAPH <https://lindas.admin.ch/foj/zefix> {{
    ?org a admin:ZefixOrganisation ;
         schema:legalName ?legalName ;
         schema:additionalType ?legalForm ;
         schema:address ?addr .

    ?addr schema:addressRegion ?canton ;
          schema:addressLocality ?city .

    OPTIONAL {{ ?org schema:description ?description . }}
    OPTIONAL {{
      ?addr schema:streetAddress ?street ;
            schema:postalCode ?zip .
    }}

    ?org schema:identifier ?uidIri .
    FILTER(CONTAINS(STR(?uidIri), "/UID/"))
    BIND(REPLACE(STR(?uidIri), ".*/UID/", "") AS ?uid)

    {canton_filter}
  }}
}}
LIMIT {limit}
OFFSET {offset}
"""

RAW_DIR = Path("data_raw")
PAGE_SIZE = 10_000


def build_canton_filter(cantons: list[str]) -> str:
    if not cantons:
        return ""
    values = ", ".join(f'"{c}"' for c in cantons)
    return f"FILTER(?canton IN ({values}))"


def sparql_query(query: str) -> list[dict]:
    response = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["results"]["bindings"]


def fetch_all(cantons: list[str] | None) -> list[dict]:
    canton_filter = build_canton_filter(cantons or [])
    scope = f"cantons {', '.join(cantons)}" if cantons else "all Switzerland"
    print(f"Fetching companies from Zefix — {scope}")

    all_rows = []
    offset = 0

    while True:
        query = QUERY.format(
            canton_filter=canton_filter,
            limit=PAGE_SIZE,
            offset=offset,
        )
        page = sparql_query(query)
        if not page:
            break

        rows = [{k: v["value"] for k, v in row.items()} for row in page]
        all_rows.extend(rows)
        print(f"  fetched {len(all_rows):,} records...", end="\r", flush=True)

        if len(page) < PAGE_SIZE:
            break  # last page
        offset += PAGE_SIZE
        time.sleep(0.5)  # be polite

    print(f"\nTotal records: {len(all_rows):,}")
    return all_rows


def save(companies: list[dict], suffix: str = ""):
    RAW_DIR.mkdir(exist_ok=True)
    stem = f"companies{suffix}"

    json_path = RAW_DIR / f"{stem}.json"
    with open(json_path, "w") as f:
        json.dump(companies, f, ensure_ascii=False, indent=2)
    print(f"Saved → {json_path}")

    csv_path = RAW_DIR / f"{stem}.csv"
    fieldnames = list(companies[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(companies)
    print(f"Saved → {csv_path}")


def print_stats(companies: list[dict]):
    cantons: dict[str, int] = {}
    legal_forms: dict[str, int] = {}
    has_description = 0

    for c in companies:
        cantons[c.get("canton", "?")] = cantons.get(c.get("canton", "?"), 0) + 1
        lf = c.get("legalForm", "").split("/")[-1]
        legal_forms[lf] = legal_forms.get(lf, 0) + 1
        if c.get("description"):
            has_description += 1

    print(
        f"\nDescription coverage: {has_description:,} / {len(companies):,} ({100 * has_description // len(companies)}%)"
    )

    print("\nTop cantons:")
    for k, v in sorted(cantons.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: {v:,}")

    print("\nLegal form breakdown (ECH-97 codes):")
    for lf, count in sorted(legal_forms.items(), key=lambda x: -x[1])[:10]:
        print(f"  {lf}: {count:,}")


def main(cantons: str = "TI,ZH", all: bool = False):
    """
    Fetch Zefix company data from LINDAS SPARQL endpoint.

    Args:
        cantons: Comma-separated canton codes to fetch (default: "TI,ZH")
        all:     Fetch all Swiss companies, ignoring --cantons (slow, ~600k records)

    Examples:
        python fetch_zefix.py                        # fetch TI and ZH
        python fetch_zefix.py --cantons TI           # only Ticino
        python fetch_zefix.py --cantons TI,ZH,GE     # three cantons
        python fetch_zefix.py --all                  # full Switzerland
    """
    if isinstance(cantons, (list, tuple)):
        canton_list = [c.strip().upper() for c in cantons]
    else:
        canton_list = [c.strip().upper() for c in cantons.split(",")]
    selected = None if all else canton_list
    suffix = "" if all else f"_{'_'.join(selected)}"

    companies = fetch_all(selected)
    if companies:
        save(companies, suffix=suffix)
        print_stats(companies)
    else:
        print("No results returned.")


if __name__ == "__main__":
    fire.Fire(main)
