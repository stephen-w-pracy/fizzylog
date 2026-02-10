# fizzylog

**Light and refreshing web traffic visualization for lab environments.**

fizzylog is a small, self-contained tool for watching web traffic *bubble up* during demos and hands-on labs. It tails an NGINX access log, aggregates requests over time, and renders a clean, interactive time-series chart—one line per configured path.

It’s designed to be easy to run, easy to tear down, and easy to understand.

## What it does

* Tails an NGINX access log in real time
* Aggregates request counts into time buckets
* Stores compact rollups in SQLite
* Serves a simple API via FastAPI
* Displays an interactive line chart using Apache ECharts
* Filters by status ranges (2xx/3xx/4xx/5xx) or exact codes
* Supports zooming and live updates

You configure the exact paths you want to visualize (for example `/` and `/terms.html`), and fizzylog shows how traffic to those pages changes over time.

## What it’s for

* Instructor-led training labs
* Demo environments
* Synthetic traffic experiments
* Quick visual feedback during presentations

It's a keyhole, not an observability platform.

## Design principles

* **Lightweight** – minimal dependencies, no build step for the UI
* **Ephemeral** – optimized for short-lived environments
* **Explicit** – UTC everywhere, no hidden magic
* **Focused** – paths and status codes only

## Quick start

1) Create a config (see `config.example.yml`).
2) Run the service:
   ```sh
   python -m fizzylog.main --config /etc/fizzylog/config.yml
   ```
3) Serve the UI with NGINX and proxy `/api/` to `127.0.0.1:8081`.

## Configuration

All settings are declared in YAML. A fully documented template is included at `config.example.yml`.

Key defaults:

* Access log: `/var/log/nginx/access.log`
* SQLite DB: `/var/lib/fizzylog/rollups.sqlite`
* FastAPI: `127.0.0.1:8081`
* UI refresh: every 2 seconds
* Default status filter: `2xx+3xx`

## API

* `GET /api/v1/meta` — configuration defaults for the UI
* `GET /api/v1/series` — chart buckets and series data
* `GET /api/v1/health` — liveness and ingest status

## Packaging helpers

* `packaging/fizzylog.service` — systemd unit template
* `packaging/nginx.conf` — nginx site template
* `packaging/setup_vm.sh` — root-run setup script for Ubuntu-based VMs

## Status

This project is under active development.
The API, configuration, and UI are intentionally small and subject to change before the first formal release.
