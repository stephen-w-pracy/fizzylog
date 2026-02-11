from __future__ import annotations

import argparse
import logging

import uvicorn

from .api import create_app
from .config import load_config, storage_dsn
from .db import init_db
from .ingest import LogIngester


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="fizzylog")
    parser.add_argument("--config", required=True, help="Path to config.yml")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = load_config(args.config)
    sqlite_path = storage_dsn(config.storage)

    init_db(sqlite_path)

    ingester = LogIngester(config, sqlite_path)
    app = create_app(config, ingester.state, sqlite_path)

    @app.on_event("startup")
    def _startup() -> None:
        ingester.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        ingester.stop()

    uvicorn.run(app, host="127.0.0.1", port=config.api.port, log_level="info")


if __name__ == "__main__":
    main()
