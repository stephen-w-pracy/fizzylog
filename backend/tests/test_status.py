import pytest

from fizzylog.models import resolve_status_filter


def test_status_ranges_parsing():
    result = resolve_status_filter(
        "ranges",
        ["2xx", "3xx"],
        [],
        "2xx,4xx",
        None,
    )
    assert result.mode == "ranges"
    assert result.ranges == ["2xx", "4xx"]


def test_status_exact_overrides_ranges():
    result = resolve_status_filter(
        "ranges",
        ["2xx"],
        [],
        "2xx,3xx",
        "200,404",
    )
    assert result.mode == "exact"
    assert result.exact == [200, 404]


def test_status_invalid_range():
    with pytest.raises(ValueError):
        resolve_status_filter(
            "ranges",
            ["2xx"],
            [],
            "6xx",
            None,
        )
