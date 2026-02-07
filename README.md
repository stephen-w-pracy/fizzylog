# fizzylog

**Light and refreshing web traffic visualization for lab environments.**

fizzylog is a small, self-contained tool for watching web traffic *bubble up* during demos and hands-on labs. It tails an NGINX access log, aggregates requests over time, and renders a clean, interactive time-series chart—one line per page you care about.

It’s designed to be easy to run, easy to tear down, and easy to understand.

## What it does

* Tails an NGINX access log in real time
* Aggregates request counts into time buckets
* Stores compact rollups in SQLite
* Serves a simple API via FastAPI
* Displays an interactive line chart using Apache ECharts

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

## Status

This project is under active development.
The API, configuration, and UI are intentionally small and subject to change before the first formal release.
