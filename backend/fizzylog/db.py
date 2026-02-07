from __future__ import annotations

import os
import sqlite3
from typing import Dict, Iterable, List, Tuple

from .models import StatusFilter, STATUS_RANGE_BOUNDS


SCHEMA = """
CREATE TABLE IF NOT EXISTS rollup_counts (
    bucket_start_utc INTEGER NOT NULL,
    path TEXT NOT NULL,
    status INTEGER NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (bucket_start_utc, path, status)
);
CREATE INDEX IF NOT EXISTS idx_rollup_time ON rollup_counts (bucket_start_utc);
CREATE INDEX IF NOT EXISTS idx_rollup_path_time ON rollup_counts (path, bucket_start_utc);
"""


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")


def get_connection(sqlite_path: str, read_only: bool = False) -> sqlite3.Connection:
    if sqlite_path.startswith("file:"):
        conn = sqlite3.connect(sqlite_path, uri=True, timeout=30)
    elif read_only:
        uri = f"file:{sqlite_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30)
    else:
        conn = sqlite3.connect(sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def init_db(sqlite_path: str) -> None:
    if sqlite_path != ":memory:" and not sqlite_path.startswith("file:"):
        directory = os.path.dirname(sqlite_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    conn = get_connection(sqlite_path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


def write_rollups(conn: sqlite3.Connection, rows: Dict[Tuple[int, str, int], int]) -> None:
    if not rows:
        return
    payload = [
        (bucket, path, status, count)
        for (bucket, path, status), count in rows.items()
        if count
    ]
    if not payload:
        return
    with conn:
        conn.executemany(
            """
            INSERT INTO rollup_counts (bucket_start_utc, path, status, count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bucket_start_utc, path, status)
            DO UPDATE SET count = count + excluded.count
            """,
            payload,
        )


def apply_retention(conn: sqlite3.Connection, cutoff_utc: int) -> None:
    with conn:
        conn.execute(
            "DELETE FROM rollup_counts WHERE bucket_start_utc < ?",
            (cutoff_utc,),
        )


def _build_status_clause(status_filter: StatusFilter) -> Tuple[str, List[int]]:
    if status_filter.mode == "exact":
        if not status_filter.exact:
            return "0", []
        placeholders = ",".join(["?"] * len(status_filter.exact))
        return f"status IN ({placeholders})", list(status_filter.exact)

    ranges = status_filter.ranges
    if not ranges:
        return "0", []
    parts: List[str] = []
    params: List[int] = []
    for entry in ranges:
        bounds = STATUS_RANGE_BOUNDS.get(entry)
        if not bounds:
            continue
        lower, upper = bounds
        parts.append("(status BETWEEN ? AND ?)")
        params.extend([lower, upper])
    if not parts:
        return "0", []
    return " OR ".join(parts), params


def query_rollups(
    conn: sqlite3.Connection,
    paths: List[str],
    status_filter: StatusFilter,
    start_bucket_utc: int,
    end_bucket_utc: int,
) -> List[Tuple[int, str, int]]:
    if not paths:
        return []
    path_placeholders = ",".join(["?"] * len(paths))
    status_clause, status_params = _build_status_clause(status_filter)
    sql = (
        "SELECT bucket_start_utc, path, SUM(count) as count "
        "FROM rollup_counts "
        "WHERE bucket_start_utc BETWEEN ? AND ? "
        f"AND path IN ({path_placeholders}) "
        f"AND ({status_clause}) "
        "GROUP BY bucket_start_utc, path "
        "ORDER BY bucket_start_utc ASC"
    )
    params: List[int] = [start_bucket_utc, end_bucket_utc]
    params.extend(paths)
    params.extend(status_params)
    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    return [(int(row["bucket_start_utc"]), str(row["path"]), int(row["count"])) for row in rows]
