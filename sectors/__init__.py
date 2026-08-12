"""Sector / theme classification for Taiwan stocks."""

from sectors.aggregate import compute_sector_stats
from sectors.taxonomy import (
    HOT_SECTORS,
    SECTOR_LABEL,
    classify_symbol,
    get_sector_for_symbol,
    list_sectors,
)

__all__ = [
    "HOT_SECTORS",
    "SECTOR_LABEL",
    "classify_symbol",
    "compute_sector_stats",
    "get_sector_for_symbol",
    "list_sectors",
]
