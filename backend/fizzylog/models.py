from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


STATUS_RANGE_BOUNDS = {
    "2xx": (200, 299),
    "3xx": (300, 399),
    "4xx": (400, 499),
    "5xx": (500, 599),
}


@dataclass(frozen=True)
class StatusFilter:
    mode: str
    ranges: List[str]
    exact: List[int]


def parse_status_ranges(value: Optional[str]) -> List[str]:
    if not value:
        return []
    ranges: List[str] = []
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        if token not in STATUS_RANGE_BOUNDS:
            raise ValueError(f"Invalid status range '{token}'")
        if token not in ranges:
            ranges.append(token)
    return ranges


def parse_status_exact(value: Optional[str]) -> List[int]:
    if not value:
        return []
    exact: List[int] = []
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"Invalid status code '{token}'")
        code = int(token)
        if code < 100 or code > 599:
            raise ValueError(f"Invalid status code '{token}'")
        if code not in exact:
            exact.append(code)
    return exact


def resolve_status_filter(
    config_mode: str,
    config_ranges: List[str],
    config_exact: List[int],
    status_ranges: Optional[str],
    status_exact: Optional[str],
) -> StatusFilter:
    exact = parse_status_exact(status_exact)
    if exact:
        return StatusFilter(mode="exact", ranges=[], exact=exact)

    ranges = parse_status_ranges(status_ranges)
    if ranges:
        return StatusFilter(mode="ranges", ranges=ranges, exact=[])

    if config_mode == "exact":
        return StatusFilter(mode="exact", ranges=[], exact=list(config_exact))

    return StatusFilter(mode="ranges", ranges=list(config_ranges), exact=[])
