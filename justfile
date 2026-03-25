start-api:
    uv run fastapi dev src/swiss_companies/main.py

fetch-zefix *args:
    uv run python -m swiss_companies.scripts.fetch_zefix {{args}}

load-zefix csv_path *args:
    uv run python -m swiss_companies.scripts.load_zefix {{csv_path}} {{args}}

sample-zefix csv_path *args:
    uv run python -m swiss_companies.scripts.sample_zefix {{csv_path}} {{args}}

truncate-zefix:
    uv run python -m swiss_companies.scripts.truncate_zefix

prepare *args:
    just fetch-zefix --all {{args}}
    just translate-descriptions
    just compute-coordinates
    just classify-sectors
    just compute-embeddings

reload:
    just truncate-zefix
    just load-zefix data_raw/companies.csv
    just load-translations
    just load-coordinates
    just load-sectors

prepare-and-reload *args:
    just prepare {{args}}
    just reload

translate-descriptions *args:
    uv run python -m swiss_companies.scripts.translate_descriptions {{args}}

load-translations *args:
    uv run python -m swiss_companies.scripts.load_translations {{args}}

start-nominatim:
    docker run -e PBF_URL=https://download.geofabrik.de/europe/switzerland-latest.osm.pbf \
        -v nominatim-switzerland:/var/lib/postgresql/14/main \
        -p 8080:8080 mediagis/nominatim:4.4

compute-coordinates *args:
    uv run python -m swiss_companies.scripts.compute_coordinates {{args}}

load-coordinates *args:
    uv run python -m swiss_companies.scripts.load_coordinates {{args}}

compute-embeddings *args:
    uv run python -m swiss_companies.scripts.compute_embeddings {{args}}

classify-sectors *args:
    uv run python -m swiss_companies.scripts.classify_sectors {{args}}

load-sectors *args:
    uv run python -m swiss_companies.scripts.load_sectors {{args}}

start-ui:
    npm --prefix web run dev
