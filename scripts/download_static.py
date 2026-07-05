"""
AetherIQ — Static Dataset Download
====================================
Downloads one-time static datasets via Google Earth Engine using **geedim**:

- **WorldPop**: Latest available population density (100 m).
- **SRTM**: Elevation at 30 m (USGS SRTMGL1 v003).

Usage::

    python scripts/download_static.py
"""

import sys
import time
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config import (
    INDIA_BBOX,
    SRTM_DIR,
    TARGET_SCALE,
    WORLDPOP_DIR,
)
from scripts.utils import (
    generate_sha256,
    get_india_geometry,
    init_gee,
    retry_download,
    save_checksum,
    save_metadata,
    setup_folders,
    setup_logging,
    verify_download,
)


logger = setup_logging("static")


def download_worldpop() -> bool:
    """Download the latest WorldPop population density layer.

    Automatically detects the most recent year available in the
    ``WorldPop/GP/100m/pop`` collection.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    import ee
    import geedim as gd

    filename = "worldpop_latest.tif"
    out_path = WORLDPOP_DIR / filename

    if out_path.exists() and verify_download(out_path):
        logger.info("SKIP (exists) %s", filename)
        return True

    if out_path.exists():
        out_path.unlink()

    india = get_india_geometry()
    t0 = time.time()

    def _do_download():
        collection = (
            ee.ImageCollection("WorldPop/GP/100m/pop")
            .filterBounds(india)
            .sort("system:time_start", False)
        )

        latest = ee.Image(collection.first())
        latest_year = ee.Date(latest.get("system:time_start")).get("year").getInfo()
        logger.info("WorldPop latest year detected: %d", latest_year)

        image = latest.select("population").clip(india)

        gd_image = gd.download.BaseImage(image)
        gd_image.download(
            str(out_path),
            region=india,
            scale=TARGET_SCALE,
            crs="EPSG:4326",
            dtype="float32",
        )

    success = retry_download(_do_download, logger=logger)
    elapsed = time.time() - t0

    if success and verify_download(out_path):
        sha = generate_sha256(out_path)
        save_checksum(out_path, sha)
        save_metadata(
            dataset="worldpop",
            variable="population",
            year=0,
            month=0,
            filename=f"worldpop/{filename}",
            collection="WorldPop/GP/100m/pop",
            band="population",
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date="latest",
            end_date="latest",
            download_time=elapsed,
            status="success",
        )
        logger.info("OK %s (%.1fs)", filename, elapsed)
        return True
    else:
        save_metadata(
            dataset="worldpop",
            variable="population",
            year=0,
            month=0,
            filename=f"worldpop/{filename}",
            collection="WorldPop/GP/100m/pop",
            band="population",
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date="latest",
            end_date="latest",
            download_time=elapsed,
            status="failed",
        )
        logger.error("FAILED %s after retries", filename)
        return False


def download_srtm() -> bool:
    """Download SRTM elevation data.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    import ee
    import geedim as gd

    filename = "srtm_elevation.tif"
    out_path = SRTM_DIR / filename

    if out_path.exists() and verify_download(out_path):
        logger.info("SKIP (exists) %s", filename)
        return True

    if out_path.exists():
        out_path.unlink()

    india = get_india_geometry()
    t0 = time.time()

    def _do_download():
        image = (
            ee.Image("USGS/SRTMGL1_003")
            .select("elevation")
            .clip(india)
        )

        gd_image = gd.download.BaseImage(image)
        gd_image.download(
            str(out_path),
            region=india,
            scale=TARGET_SCALE,
            crs="EPSG:4326",
            dtype="int16",
        )

    success = retry_download(_do_download, logger=logger)
    elapsed = time.time() - t0

    if success and verify_download(out_path):
        sha = generate_sha256(out_path)
        save_checksum(out_path, sha)
        save_metadata(
            dataset="srtm",
            variable="elevation",
            year=0,
            month=0,
            filename=f"srtm/{filename}",
            collection="USGS/SRTMGL1_003",
            band="elevation",
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date="static",
            end_date="static",
            download_time=elapsed,
            status="success",
        )
        logger.info("OK %s (%.1fs)", filename, elapsed)
        return True
    else:
        save_metadata(
            dataset="srtm",
            variable="elevation",
            year=0,
            month=0,
            filename=f"srtm/{filename}",
            collection="USGS/SRTMGL1_003",
            band="elevation",
            scale=TARGET_SCALE,
            projection="EPSG:4326",
            start_date="static",
            end_date="static",
            download_time=elapsed,
            status="failed",
        )
        logger.error("FAILED %s after retries", filename)
        return False


def download_all_static() -> Dict[str, bool]:
    """Download all static datasets.

    Returns:
        Dict mapping dataset name to success status.
    """
    init_gee()
    setup_folders()

    results: Dict[str, bool] = {}

    logger.info("Downloading static datasets ...")

    results["worldpop"] = download_worldpop()
    results["srtm"] = download_srtm()

    for name, ok in results.items():
        status = "SUCCESS" if ok else "FAILED"
        logger.info("  %s: %s", name, status)

    return results


if __name__ == "__main__":
    download_all_static()
