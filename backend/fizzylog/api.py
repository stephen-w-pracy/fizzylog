from __future__ import annotations

import math
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException

from .config import Config
from .db import get_connection, query_rollups
from .models import resolve_status_filter


def _build_series(
    bucket_starts: List[int],
    paths: List[str],
    rows: List[tuple],
) -> List[Dict[str, object]]:
    counts_by_path: Dict[str, Dict[int, int]] = {path: {} for path in paths}
    for bucket_start, path, count in rows:
        if path in counts_by_path:
            counts_by_path[path][bucket_start] = count

    series = []
    for path in paths:
        path_counts = counts_by_path.get(path, {})
        counts = [int(path_counts.get(bucket, 0)) for bucket in bucket_starts]
        series.append({"path": path, "counts": counts})
    return series


def create_app(config: Config, ingest_state, sqlite_path: str) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/meta")
    def get_meta() -> Dict[str, object]:
        return {
            "log": {"path": config.log.path, "format": config.log.format},
            "api": {"port": config.api.port},
            "window": {
                "lookback_seconds": config.window.lookback_seconds,
                "bucket_seconds": config.window.bucket_seconds,
            },
            "paths": {
                "include_exact": list(config.paths.include_exact),
                "aliases": dict(config.paths.aliases),
                "strip_query_string": config.paths.strip_query_string,
                "ignore_static_assets": config.paths.ignore_static_assets,
                "ignore_extensions": list(config.paths.ignore_extensions),
            },
            "status_filter": {
                "default_mode": config.status_filter.default_mode,
                "default_ranges": list(config.status_filter.default_ranges),
                "default_exact": list(config.status_filter.default_exact),
            },
            "ui": {
                "refresh_seconds": config.ui.refresh_seconds,
                "max_points": config.ui.max_points,
            },
            "storage": {
                "backend": config.storage.backend,
                "sqlite_path": config.storage.sqlite_path,
                "retention_seconds": config.storage.retention_seconds,
            },
        }

    @app.get("/api/v1/series")
    def get_series(
        status_ranges: Optional[str] = None,
        status_exact: Optional[str] = None,
    ) -> Dict[str, object]:
        try:
            status_filter = resolve_status_filter(
                config.status_filter.default_mode,
                config.status_filter.default_ranges,
                config.status_filter.default_exact,
                status_ranges,
                status_exact,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        bucket_seconds = config.window.bucket_seconds
        now_utc = int(time.time())
        end_bucket = (now_utc // bucket_seconds) * bucket_seconds
        max_points = max(1, config.ui.max_points)
        requested_points = max(1, math.ceil(config.window.lookback_seconds / bucket_seconds))
        bucket_count = min(max_points, requested_points)
        start_bucket = end_bucket - (bucket_count - 1) * bucket_seconds
        bucket_starts = [start_bucket + i * bucket_seconds for i in range(bucket_count)]

        conn = get_connection(sqlite_path, read_only=True)
        try:
            rows = query_rollups(
                conn,
                config.paths.include_exact,
                status_filter,
                start_bucket,
                end_bucket,
            )
        finally:
            conn.close()

        series = _build_series(bucket_starts, config.paths.include_exact, rows)
        return {"bucket_start_utc": bucket_starts, "series": series}

    @app.get("/api/v1/health")
    def get_health() -> Dict[str, object]:
        return {
            "ok": True,
            "tailing": bool(getattr(ingest_state, "tailing", False)),
            "last_ingest_utc": getattr(ingest_state, "last_ingest_utc", None),
        }

    return app
