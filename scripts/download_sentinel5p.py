"""
AetherIQ — Sentinel-5P Data Download
======================================
Downloads monthly median composites of tropospheric trace-gas columns
from TROPOMI / Sentinel-5P via Google Earth Engine using **geedim**.

Products: HCHO, NO2, SO2, CO, O3

Usage::

    python scripts/download_sentinel5p.py
"""

import sys
import time
from pathlib import Path
from typing import Dict

from tqdm import tqdm

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config import (
    END_DATE,
    S5P_COLLECTIONS,
    S5P_DIR,
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


logger = setup_logging("sentinel5p")


def download_month(
    variable: str,
    collection_id: str,
    band: str,
    output_dir: Path,
    month_start: str,
    month_end: str,
    year: int,
    month: int,
) -> bool:
    """Download a single monthly median composite for one S5P variable.

    Args:
        variable: Variable key (e.g. ``'no2'``).
        collection_id: GEE collection ID.
        band: Band to select.
        output_dir: Target directory.
        month_start: Start date (inclusive) ``'YYYY-MM-DD'``.
        month_end: End date (exclusive) ``'YYYY-MM-DD'``.
        year: Data year.
        month: Data month.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    import ee
    import geedim as gd

    filename = f"{variable}_{year:04d}_{month:02d}.tif"
    out_path = output_dir / filename

    # Resume: skip if already downloaded and valid
    if out_path.exists() and verify_download(out_path):
        logger.info("SKIP (exists) %s", filename)
        return True

    # Remove partial downloads
    if out_path.exists():
        out_path.unlink()

    india = get_india_geometry()
    t0 = time.time()

    def _do_download():
        composite = (
            ee.ImageCollection(collection_id)
            .filterDate(month_start, month_end)
            .filterBounds(india)
            .select(band)
            .median()
            .clip(india)
        )

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

    if success and verify_download(out_path):
        sha = generate_sha256(out_path)
        save_checksum(out_path, sha)
        save_metadata(
            dataset="sentinel5p",
            variable=variable,
            year=year,
            month=month,
            filename=f"sentinel5p/{variable}/{filename}",
            collection=collection_id,
            band=band,
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
            dataset="sentinel5p",
            variable=variable,
            year=year,
            month=month,
            filename=f"sentinel5p/{variable}/{filename}",
            collection=collection_id,
            band=band,
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date=month_start,
            end_date=month_end,
            download_time=elapsed,
            status="failed",
        )
        logger.error("FAILED %s after retries", filename)
        return False


def download_variable(
    variable: str,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Dict[str, int]:
    """Download all monthly composites for a single S5P variable.

    Args:
        variable: Variable key (e.g. ``'no2'``).
        start_date: Override start date.
        end_date: Override end date.

    Returns:
        Dict with ``'success'`` and ``'failed'`` counts.
    """
    output_dir = S5P_DIR / variable
    output_dir.mkdir(parents=True, exist_ok=True)

    collection_id = S5P_COLLECTIONS[variable]["collection"]
    band = S5P_COLLECTIONS[variable]["band"]
    intervals = get_monthly_intervals(start_date, end_date)
    stats = {"success": 0, "failed": 0}

    logger.info(
        "Downloading %s | %s | %d months",
        variable.upper(), collection_id, len(intervals),
    )

    for m_start, m_end, yr, mo in tqdm(
        intervals, desc=f"S5P {variable.upper()}", unit="month"
    ):
        try:
            ok = download_month(
                variable, collection_id, band, output_dir,
                m_start, m_end, yr, mo,
            )
            if ok:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        except Exception as exc:
            logger.error(
                "Unhandled error for %s %04d-%02d: %s",
                variable, yr, mo, exc,
            )
            stats["failed"] += 1

    return stats


def download_all_sentinel5p(
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> Dict[str, int]:
    """Download all Sentinel-5P variables.

    Args:
        start_date: Override start date.
        end_date: Override end date.

    Returns:
        Dict with total ``'success'`` and ``'failed'`` counts across
        all variables.
    """
    total_stats: Dict[str, int] = {"success": 0, "failed": 0}

    for var_name in S5P_COLLECTIONS:
        stats = download_variable(
            variable=var_name,
            start_date=start_date,
            end_date=end_date,
        )
        total_stats["success"] += stats["success"]
        total_stats["failed"] += stats["failed"]
        logger.info(
            "Completed %s: %d success, %d failed",
            var_name.upper(), stats["success"], stats["failed"],
        )

    return total_stats


if __name__ == "__main__":
    init_gee()
    setup_folders()
    download_all_sentinel5p()
