# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is fizzylog

A lightweight web traffic visualizer for lab/demo environments. It tails an NGINX access log, aggregates request counts into time buckets, stores rollups in SQLite, and serves an interactive line chart via a FastAPI backend and vanilla JS frontend (Apache ECharts).

## Architecture

Single Python service with two concurrent concerns:
1. **Ingest loop** — background thread that tails the NGINX access log, parses lines, normalizes paths, buckets by UTC epoch seconds, and flushes rollup deltas to SQLite every `flush_seconds`.
2. **FastAPI server** — reads rollups from SQLite and serves JSON endpoints (`/api/v1/meta`, `/api/v1/series`, `/api/v1/health`). NGINX reverse-proxies `/api/` to this service and serves the static frontend directly.

All timestamps are stored and transmitted as UTC epoch seconds. The frontend handles local/UTC display toggle.

## Repository layout

- `backend/fizzylog/` — Python package: `main.py` (entrypoint), `config.py`, `db.py`, `ingest.py`, `api.py`, `models.py`
- `backend/tests/` — pytest tests with `conftest.py` for path setup
- `frontend/` — static HTML/JS/CSS (no build step, no framework)
- `packaging/` — systemd unit, nginx config, VM setup script
- `SPEC.md` — authoritative specification; implementation must match it exactly
- `AGENTS.md` — implementation guardrails (scope boundaries, do/don't rules)

## Commands

### Run the backend
```sh
cd backend
pip install -r requirements.txt
python -m fizzylog.main --config /etc/fizzylog/config.yml
```

### Run tests
```sh
cd backend
python -m pytest tests/
python -m pytest tests/test_paths.py          # single file
python -m pytest tests/test_paths.py::test_x  # single test
```

## Key constraints

- SPEC.md is the source of truth — do not expand scope beyond what it defines.
- No build step for the frontend; vanilla JS + ECharts from CDN.
- SQLite in WAL mode: one writer (ingest), many readers (API).
- Only explicitly configured paths are tracked (`paths.include_exact`); no auto-discovery.
- Rollup-only storage — no per-request event logging.
- Config is YAML; see `config.example.yml` for all options.
