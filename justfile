start-api:
    uv run fastapi dev src/swiss_companies/main.py

fetch-zefix *args:
    uv run python -m swiss_companies.scripts.fetch_zefix {{args}}

load-zefix csv_path *args:
    uv run python -m swiss_companies.scripts.load_zefix {{csv_path}} {{args}}

sample-zefix csv_path *args:
    uv run python -m swiss_companies.scripts.sample_zefix {{csv_path}} {{args}}

migrate:
    #!/bin/bash
    echo "Waiting for database..."
    for i in $(seq 1 5); do
        pg_isready -h localhost -p 5431 -U swiss > /dev/null 2>&1 && break
        [ $i -eq 30 ] && echo "Database not ready after 30s, aborting." && exit 1
        sleep 1
    done
    uv run alembic upgrade head

truncate-zefix:
    uv run python -m swiss_companies.scripts.truncate_zefix

prepare *args:
    just fetch-zefix --all
    just translate-descriptions
    just start-nominatim
    just wait-nominatim
    just compute-coordinates
    just stop-nominatim
    just classify-sectors

prepare-subset n="1000":
    just fetch-zefix --all --limit {{n}}
    just translate-descriptions --input_file companies_{{n}}.csv --output_file descriptions_en_{{n}}.csv
    just start-nominatim
    just wait-nominatim
    just compute-coordinates --input_file companies_{{n}}.csv --output_file coordinates_{{n}}.csv
    just stop-nominatim
    just classify-sectors --input_file descriptions_en_{{n}}.csv --output_file sectors_{{n}}.csv

reload:
    just truncate-zefix
    just load-zefix data_raw/companies.csv
    just load-translations
    just load-coordinates
    just load-sectors
    just compute-embeddings

reload-subset n="1000":
    just truncate-zefix
    just load-zefix data_raw/companies_{{n}}.csv
    just load-translations --input_file descriptions_en_{{n}}.csv
    just load-coordinates --input_file coordinates_{{n}}.csv
    just load-sectors --input_file sectors_{{n}}.csv
    just compute-embeddings

prepare-and-reload:
    just prepare
    just reload

prepare-and-reload-subset n="1000":
    just prepare-subset {{n}}
    just reload-subset {{n}}

translate-descriptions *args:
    uv run python -m swiss_companies.scripts.translate_descriptions {{args}}

load-translations *args:
    uv run python -m swiss_companies.scripts.load_translations {{args}}

stop-nominatim:
    docker stop nominatim
    docker rm nominatim

start-nominatim:
    docker run -d --name nominatim \
        -e PBF_URL=https://download.geofabrik.de/europe/switzerland-latest.osm.pbf \
        -v nominatim-switzerland:/var/lib/postgresql/14/main \
        -p 8080:8080 mediagis/nominatim:4.4

wait-nominatim:
    #!/bin/bash
    echo "Waiting for Nominatim to be ready (may take a while on first run)..."
    until curl -sf http://localhost:8080/status > /dev/null; do sleep 5; done
    echo "Nominatim is ready."

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
