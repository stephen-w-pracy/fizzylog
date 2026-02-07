from fizzylog.config import (
    Config,
    IngestConfig,
    LogConfig,
    PathsConfig,
    StatusFilterConfig,
    StorageConfig,
    UIConfig,
    WindowConfig,
)
from fizzylog.ingest import normalize_path


def make_config(
    include_exact,
    aliases=None,
    strip_query_string=True,
    ignore_static_assets=False,
    ignore_extensions=None,
):
    return Config(
        log=LogConfig(path="/var/log/nginx/access.log"),
        window=WindowConfig(),
        paths=PathsConfig(
            include_exact=include_exact,
            aliases=aliases or {},
            strip_query_string=strip_query_string,
            ignore_static_assets=ignore_static_assets,
            ignore_extensions=ignore_extensions or [],
        ),
        status_filter=StatusFilterConfig(),
        ui=UIConfig(),
        storage=StorageConfig(sqlite_path=":memory:"),
        ingest=IngestConfig(),
    )


def test_normalize_strips_query_and_aliases():
    config = make_config(include_exact=["/"], aliases={"/index.html": "/"})
    assert normalize_path("/index.html?utm=1", config) == "/"


def test_normalize_ignores_unconfigured():
    config = make_config(include_exact=["/"], aliases={})
    assert normalize_path("/terms.html", config) is None


def test_normalize_ignores_static_assets():
    config = make_config(
        include_exact=["/"],
        ignore_static_assets=True,
        ignore_extensions=[".css", ".js"],
    )
    assert normalize_path("/style.css", config) is None
    assert normalize_path("/app.js", config) is None
