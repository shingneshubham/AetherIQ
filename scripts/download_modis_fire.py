"""
AetherIQ — MODIS Active Fire Data Download
============================================
Downloads monthly fire-occurrence composites from MODIS (MOD14A1)
via Google Earth Engine using **geedim**.

FireMask is categorical — raw values are converted to a binary mask
(fire = 1, no fire = 0) before summing across the month.

Usage::

    python scripts/download_modis_fire.py
"""

import sys
import time
from pathlib import Path
from typing import Dict

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config import (
    END_DATE,
    INDIA_BBOX,
    MODIS_FIRE_DIR,
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


logger = setup_logging("fire")

MODIS_COLLECTION: str = "MODIS/061/MOD14A1"


def _to_binary_fire(image):
    """Convert MODIS FireMask to binary fire presence.

    FireMask values >= 7 indicate nominal-to-high confidence fire pixels.
    This avoids summing raw categorical values.

    Args:
        image: ``ee.Image`` with a ``FireMask`` band.

    Returns:
        Binary ``ee.Image`` (1 = fire, 0 = no fire).
    """
    return image.select("FireMask").gte(7).rename("fire").toInt32()


def download_single_month(
    month_start: str,
    month_end: str,
    year: int,
    month: int,
) -> bool:
    """Download a single monthly MODIS fire-occurrence composite.

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

    filename = f"modis_fire_{year:04d}_{month:02d}.tif"
    out_path = MODIS_FIRE_DIR / filename

    if out_path.exists() and verify_download(out_path):
        logger.info("SKIP (exists) %s", filename)
        return True

    if out_path.exists():
        out_path.unlink()

    india = get_india_geometry()
    t0 = time.time()

    def _do_download():
        composite = (
            ee.ImageCollection(MODIS_COLLECTION)
            .filterDate(month_start, month_end)
            .filterBounds(india)
            .map(_to_binary_fire)
            .sum()
            .clip(india)
        )

        gd_image = gd.download.BaseImage(composite)
        gd_image.download(
            str(out_path),
            region=india,
            scale=TARGET_SCALE,
            crs="EPSG:4326",
            dtype="int32",
        )

    success = retry_download(_do_download, logger=logger)
    elapsed = time.time() - t0

    if success and verify_download(out_path):
        sha = generate_sha256(out_path)
        save_checksum(out_path, sha)
        save_metadata(
            dataset="modis_fire",
            variable="fire",
            year=year,
            month=month,
            filename=f"modis_fire/{filename}",
            collection=MODIS_COLLECTION,
            band="FireMask (binary)",
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
            dataset="modis_fire",
            variable="fire",
            year=year,
            month=month,
            filename=f"modis_fire/{filename}",
            collection=MODIS_COLLECTION,
            band="FireMask (binary)",
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date=month_start,
            end_date=month_end,
            download_time=elapsed,
            status="failed",
        )
        logger.error("FAILED %s after retries", filename)
        return False


def download_all_modis_fire(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Dict[str, int]:
    """Download all monthly MODIS fire composites.

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
        "Downloading MODIS Fire | %s | %d months",
        MODIS_COLLECTION, len(intervals),
    )

    for m_start, m_end, yr, mo in tqdm(
        intervals, desc="MODIS Fire", unit="month"
    ):
        try:
            ok = download_single_month(m_start, m_end, yr, mo)
            if ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            logger.error(
                "Unhandled error for MODIS Fire %04d-%02d: %s", yr, mo, exc
            )
            stats["failed"] += 1

    logger.info(
        "MODIS Fire complete: %d success, %d failed",
        stats["success"], stats["failed"],
    )
    return stats


if __name__ == "__main__":
    download_all_modis_fire()
