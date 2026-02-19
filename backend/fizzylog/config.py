from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
import os

import yaml


DEFAULT_IGNORE_EXTENSIONS = [
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
]


@dataclass
class LogConfig:
    path: str
    format: str = "nginx_combined"


@dataclass
class ApiConfig:
    port: int = 8081


@dataclass
class WindowConfig:
    lookback_seconds: int = 21600
    bucket_seconds: int = 60


@dataclass
class PathsConfig:
    include_exact: List[str]
    aliases: Dict[str, str] = field(default_factory=lambda: {"/index.html": "/"})
    strip_query_string: bool = True
    ignore_static_assets: bool = True
    ignore_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_EXTENSIONS))


@dataclass
class StatusFilterConfig:
    default_mode: str = "ranges"
    default_ranges: List[str] = field(default_factory=lambda: ["2xx", "3xx"])
    default_exact: List[int] = field(default_factory=list)


@dataclass
class UIConfig:
    refresh_seconds: int = 2
    max_points: int = 360
    time_default: str = "local"


@dataclass
class StorageConfig:
    backend: str = "sqlite"
    sqlite_path: str = "/var/lib/fizzylog/rollups.sqlite"
    retention_seconds: int = 43200


@dataclass
class IngestConfig:
    flush_seconds: int = 2


@dataclass
class Config:
    log: LogConfig
    api: ApiConfig
    window: WindowConfig
    paths: PathsConfig
    status_filter: StatusFilterConfig
    ui: UIConfig
    storage: StorageConfig
    ingest: IngestConfig


def _normalize_extensions(values: List[str]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        if not value:
            continue
        value = value.strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        if value not in normalized:
            normalized.append(value)
    return normalized


def _get_section(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    section = data.get(key)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ValueError(f"Config section '{key}' must be a mapping")
    return section


def load_config(path: str) -> Config:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Config file must be a mapping at top level")

    log_section = _get_section(data, "log")
    if "path" not in log_section:
        raise ValueError("log.path is required")
    log_cfg = LogConfig(
        path=str(log_section["path"]),
        format=str(log_section.get("format", "nginx_combined")),
    )

    api_section = _get_section(data, "api")
    api_cfg = ApiConfig(
        port=int(api_section.get("port", 8081)),
    )

    window_section = _get_section(data, "window")
    window_cfg = WindowConfig(
        lookback_seconds=int(window_section.get("lookback_seconds", 21600)),
        bucket_seconds=int(window_section.get("bucket_seconds", 60)),
    )

    paths_section = _get_section(data, "paths")
    include_exact = paths_section.get("include_exact")
    if not include_exact:
        raise ValueError("paths.include_exact is required and must be a non-empty list")
    if not isinstance(include_exact, list):
        raise ValueError("paths.include_exact must be a list")
    include_exact = [str(item) for item in include_exact]

    aliases = paths_section.get("aliases", {"/index.html": "/"})
    if aliases is None:
        aliases = {}
    if not isinstance(aliases, dict):
        raise ValueError("paths.aliases must be a mapping")
    aliases = {str(k): str(v) for k, v in aliases.items()}

    ignore_extensions = paths_section.get("ignore_extensions", DEFAULT_IGNORE_EXTENSIONS)
    if ignore_extensions is None:
        ignore_extensions = []
    if not isinstance(ignore_extensions, list):
        raise ValueError("paths.ignore_extensions must be a list")

    paths_cfg = PathsConfig(
        include_exact=include_exact,
        aliases=aliases,
        strip_query_string=bool(paths_section.get("strip_query_string", True)),
        ignore_static_assets=bool(paths_section.get("ignore_static_assets", True)),
        ignore_extensions=_normalize_extensions([str(v) for v in ignore_extensions]),
    )

    status_section = _get_section(data, "status_filter")
    default_exact = status_section.get("default_exact", [])
    if default_exact is None:
        default_exact = []
    if not isinstance(default_exact, list):
        raise ValueError("status_filter.default_exact must be a list")
    status_cfg = StatusFilterConfig(
        default_mode=str(status_section.get("default_mode", "ranges")),
        default_ranges=[str(v) for v in status_section.get("default_ranges", ["2xx", "3xx"])],
        default_exact=[int(v) for v in default_exact],
    )

    ui_section = _get_section(data, "ui")
    ui_cfg = UIConfig(
        refresh_seconds=int(ui_section.get("refresh_seconds", 2)),
        max_points=int(ui_section.get("max_points", 360)),
        time_default=str(ui_section.get("time_default", "local")),
    )

    storage_section = _get_section(data, "storage")
    storage_cfg = StorageConfig(
        backend=str(storage_section.get("backend", "sqlite")),
        sqlite_path=str(storage_section.get("sqlite_path", "/var/lib/fizzylog/rollups.sqlite")),
        retention_seconds=int(storage_section.get("retention_seconds", 43200)),
    )

    ingest_section = _get_section(data, "ingest")
    ingest_cfg = IngestConfig(
        flush_seconds=int(ingest_section.get("flush_seconds", 2)),
    )

    if log_cfg.format != "nginx_combined":
        raise ValueError("Only nginx_combined log format is supported")
    if api_cfg.port <= 0 or api_cfg.port > 65535:
        raise ValueError("api.port must be between 1 and 65535")
    if window_cfg.bucket_seconds <= 0:
        raise ValueError("window.bucket_seconds must be > 0")
    if window_cfg.lookback_seconds <= 0:
        raise ValueError("window.lookback_seconds must be > 0")
    if ingest_cfg.flush_seconds <= 0:
        raise ValueError("ingest.flush_seconds must be > 0")
    if storage_cfg.retention_seconds <= 0:
        raise ValueError("storage.retention_seconds must be > 0")
    if ui_cfg.time_default not in ("local", "utc"):
        raise ValueError("ui.time_default must be 'local' or 'utc'")

    return Config(
        log=log_cfg,
        api=api_cfg,
        window=window_cfg,
        paths=paths_cfg,
        status_filter=status_cfg,
        ui=ui_cfg,
        storage=storage_cfg,
        ingest=ingest_cfg,
    )


def storage_dsn(storage: StorageConfig) -> str:
    if storage.backend == "memory":
        return "file:fizzylog?mode=memory&cache=shared"
    return storage.sqlite_path
