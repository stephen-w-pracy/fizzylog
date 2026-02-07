from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .config import Config
from . import db


LOG_PATTERN = re.compile(
    r'^(?P<remote>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d{3}) (?P<size>\S+) "(?P<referer>[^"]*)" "(?P<ua>[^"]*)"'
)


@dataclass
class IngestState:
    tailing: bool = False
    last_ingest_utc: Optional[int] = None


def parse_log_line(line: str) -> Optional[Tuple[int, str, int]]:
    match = LOG_PATTERN.match(line)
    if not match:
        return None
    timestamp = match.group("time")
    request = match.group("request")
    status_text = match.group("status")

    try:
        dt = datetime.strptime(timestamp, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
        event_time_utc = int(dt.timestamp())
    except ValueError:
        return None

    if not status_text.isdigit():
        return None
    status = int(status_text)

    if not request or request == "-":
        return None
    parts = request.split()
    if len(parts) < 2:
        return None
    path = parts[1]
    return event_time_utc, path, status


def normalize_path(raw_path: str, config: Config) -> Optional[str]:
    if not raw_path:
        return None

    path = raw_path
    if config.paths.strip_query_string and "?" in path:
        path = path.split("?", 1)[0]

    if config.paths.ignore_static_assets:
        _, ext = os.path.splitext(path.lower())
        if ext and ext in config.paths.ignore_extensions:
            return None

    path = config.paths.aliases.get(path, path)
    if path not in config.paths.include_exact:
        return None

    return path


def bucket_start_utc(event_time_utc: int, bucket_seconds: int) -> int:
    return (event_time_utc // bucket_seconds) * bucket_seconds


class LogIngester:
    def __init__(self, config: Config, sqlite_path: str) -> None:
        self.config = config
        self.sqlite_path = sqlite_path
        self.state = IngestState()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._last_error_log = 0.0

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _log_parse_error(self, message: str) -> None:
        now = time.time()
        if now - self._last_error_log >= 5:
            self._last_error_log = now
            print(message)

    def _open_log(self) -> Optional[Tuple[object, int]]:
        try:
            handle = open(self.config.log.path, "r", encoding="utf-8", errors="replace")
        except OSError as exc:
            self.state.tailing = False
            self._log_parse_error(f"ingest: unable to open log: {exc}")
            return None
        try:
            stat = os.fstat(handle.fileno())
            inode = stat.st_ino
            handle.seek(0, os.SEEK_END)
            self.state.tailing = True
            return handle, inode
        except OSError as exc:
            handle.close()
            self.state.tailing = False
            self._log_parse_error(f"ingest: unable to stat log: {exc}")
            return None

    def _run(self) -> None:
        db.init_db(self.sqlite_path)
        conn = db.get_connection(self.sqlite_path)

        buffer: Dict[Tuple[int, str, int], int] = {}
        flush_seconds = self.config.ingest.flush_seconds
        retention_seconds = self.config.storage.retention_seconds
        next_flush = time.time() + flush_seconds
        next_retention = time.time() + retention_seconds

        log_handle = None
        log_inode = None

        try:
            while not self._stop_event.is_set():
                try:
                    if log_handle is None:
                        opened = self._open_log()
                        if opened is None:
                            time.sleep(1)
                            continue
                        log_handle, log_inode = opened

                    line = log_handle.readline()
                    if line:
                        parsed = parse_log_line(line)
                        if parsed is None:
                            self._log_parse_error("ingest: parse error")
                        else:
                            event_time_utc, path_raw, status = parsed
                            path = normalize_path(path_raw, self.config)
                            if path:
                                bucket = bucket_start_utc(event_time_utc, self.config.window.bucket_seconds)
                                key = (bucket, path, status)
                                buffer[key] = buffer.get(key, 0) + 1
                                self.state.last_ingest_utc = event_time_utc
                    else:
                        time.sleep(0.2)
                        try:
                            stat = os.stat(self.config.log.path)
                            if stat.st_ino != log_inode or stat.st_size < log_handle.tell():
                                log_handle.close()
                                log_handle = None
                                log_inode = None
                                self.state.tailing = False
                        except OSError:
                            log_handle.close()
                            log_handle = None
                            log_inode = None
                            self.state.tailing = False

                    now = time.time()
                    if now >= next_flush:
                        db.write_rollups(conn, buffer)
                        buffer.clear()
                        next_flush = now + flush_seconds

                    if now >= next_retention:
                        cutoff = int(now) - retention_seconds
                        db.apply_retention(conn, cutoff)
                        next_retention = now + retention_seconds
                except Exception as exc:
                    self._log_parse_error(f"ingest: unexpected error: {exc}")
                    time.sleep(1)
        except Exception as exc:
            self._log_parse_error(f"ingest: fatal error: {exc}")
        finally:
            if buffer:
                db.write_rollups(conn, buffer)
            if log_handle is not None:
                log_handle.close()
            conn.close()
