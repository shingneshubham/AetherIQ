"""
AetherIQ — ERA5-Land Meteorological Data Download
===================================================
Downloads monthly mean composites of ERA5-Land reanalysis data via
Google Earth Engine using **geedim**, filtered to 08:00 UTC.

Bands: temperature_2m, u/v wind 10m, surface_pressure,
       dewpoint_temperature_2m, boundary_layer_height.

Usage::

    python scripts/download_era5.py
"""

import sys
import time
from pathlib import Path
from typing import Dict

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config import (
    END_DATE,
    ERA5_BANDS,
    ERA5_DIR,
    INDIA_BBOX,
    START_DATE,
    TARGET_SCALE,
)
from scripts.utils import (
    generate_sha256,
    get_india_geometry,
    get_monthly_intervals,
    init_gee,
    retry_download,
    save_checksum,
    save_metadata,
    setup_folders,
    setup_logging,
    verify_download,
)


logger = setup_logging("era5")

ERA5_COLLECTION: str = "ECMWF/ERA5_LAND/HOURLY"


def download_single_month(
    month_start: str,
    month_end: str,
    year: int,
    month: int,
) -> bool:
    """Download a single monthly mean ERA5-Land composite.

    Filters to hour == 8 (08:00 UTC ≈ 13:30 IST) to match Sentinel-5P
    overpass time.

    Args:
        month_start: Start date (inclusive).
        month_end: End date (exclusive).
        year: Data year.
        month: Data month.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    import ee
    import geedim as gd

    filename = f"era5_{year:04d}_{month:02d}.tif"
    out_path = ERA5_DIR / filename

    # Resume support
    if out_path.exists() and verify_download(out_path):
        logger.info("SKIP (exists) %s", filename)
        return True

    if out_path.exists():
        out_path.unlink()

    india = get_india_geometry()
    t0 = time.time()

    def _do_download():
        collection = (
            ee.ImageCollection(ERA5_COLLECTION)
            .filterDate(month_start, month_end)
            .filterBounds(india)
            .filter(ee.Filter.eq("hour", 8))
            .select(ERA5_BANDS)
        )

        composite = collection.mean().clip(india)

        gd_image = gd.download.BaseImage(composite)
        gd_image.download(
            str(out_path),
            region=india,
            scale=TARGET_SCALE,
            crs="EPSG:4326",
            dtype="float64",
        )

    success = retry_download(_do_download, logger=logger)
    elapsed = time.time() - t0

    bands_str = ",".join(ERA5_BANDS)

    if success and verify_download(out_path):
        sha = generate_sha256(out_path)
        save_checksum(out_path, sha)
        save_metadata(
            dataset="era5",
            variable="multi",
            year=year,
            month=month,
            filename=f"era5/{filename}",
            collection=ERA5_COLLECTION,
            band=bands_str,
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date=month_start,
            end_date=month_end,
            download_time=elapsed,
            status="success",
        )
        logger.info("OK %s (%.1fs)", filename, elapsed)
        return True
    else:
        save_metadata(
            dataset="era5",
            variable="multi",
            year=year,
            month=month,
            filename=f"era5/{filename}",
            collection=ERA5_COLLECTION,
            band=bands_str,
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date=month_start,
            end_date=month_end,
            download_time=elapsed,
            status="failed",
        )
        logger.error("FAILED %s after retries", filename)
        return False


def download_all_era5(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Dict[str, int]:
    """Download all monthly ERA5-Land composites.

    Args:
        start_date: Override start date.
        end_date: Override end date.

    Returns:
        Dict with ``'success'`` and ``'failed'`` counts.
    """
    init_gee()
    setup_folders()

    intervals = get_monthly_intervals(start_date, end_date)
    stats = {"success": 0, "failed": 0}

    logger.info(
        "Downloading ERA5-Land | %s | %d months",
        ERA5_COLLECTION, len(intervals),
    )

    for m_start, m_end, yr, mo in tqdm(
        intervals, desc="ERA5", unit="month"
    ):
        try:
            ok = download_single_month(m_start, m_end, yr, mo)
            if ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            logger.error("Unhandled error for ERA5 %04d-%02d: %s", yr, mo, exc)
            stats["failed"] += 1

    logger.info(
        "ERA5 complete: %d success, %d failed",
        stats["success"], stats["failed"],
    )
    return stats


if __name__ == "__main__":
    download_all_era5()
