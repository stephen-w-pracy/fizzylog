from fizzylog.api import _build_series


def test_series_zero_fill_alignment():
    buckets = [0, 60, 120]
    rows = [(0, "/", 2), (120, "/", 4), (60, "/terms", 1)]
    series = _build_series(buckets, ["/", "/terms"], rows)

    assert series[0]["path"] == "/"
    assert series[0]["counts"] == [2, 0, 4]
    assert series[1]["path"] == "/terms"
    assert series[1]["counts"] == [0, 1, 0]
