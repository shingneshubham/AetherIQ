"""
AetherIQ — Pipeline Runner
============================
Orchestrates all data acquisition downloads in the correct order.

Usage::

    python scripts/run_all.py
    python scripts/run_all.py --dataset sentinel5p
    python scripts/run_all.py --dataset era5
    python scripts/run_all.py --dataset modis_fire
    python scripts/run_all.py --dataset viirs_fire
    python scripts/run_all.py --dataset static
    python scripts/run_all.py --start 2023-01-01 --end 2023-12-31
    python scripts/run_all.py --dry-run
"""

import sys
import time
from pathlib import Path
from typing import Optional

import click

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.config import END_DATE, START_DATE
from scripts.utils import init_gee, setup_folders, setup_logging


logger = setup_logging("run_all")


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time as ``HH:MM:SS``."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


@click.command()
@click.option(
    "--dataset",
    type=click.Choice(
        [
            "sentinel5p",
            "era5",
            "modis_fire",
            "viirs_fire",
            "static",
        ],
        case_sensitive=False,
    ),
    default=None,
    help="Run a single dataset. Omit to run all.",
)
@click.option(
    "--start",
    "start_date",
    type=str,
    default=None,
    help=f"Override start date (default: {START_DATE}).",
)
@click.option(
    "--end",
    "end_date",
    type=str,
    default=None,
    help=f"Override end date (default: {END_DATE}).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be downloaded without actually downloading.",
)
def main(
    dataset: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    dry_run: bool,
) -> None:
    """Run the AetherIQ data acquisition pipeline."""
    sd = start_date or START_DATE
    ed = end_date or END_DATE

    logger.info("=" * 60)
    logger.info("  AetherIQ Data Acquisition Pipeline")
    logger.info("  Date range : %s to %s", sd, ed)
    logger.info("  Dataset    : %s", dataset or "ALL")
    logger.info("  Dry run    : %s", dry_run)
    logger.info("=" * 60)

    if dry_run:
        _print_dry_run(dataset, sd, ed)
        return

    init_gee()
    setup_folders()

    t0 = time.time()
    summary = {}

    # Execution order: static -> sentinel5p -> era5 -> modis_fire -> viirs_fire
    if dataset is None or dataset == "static":
        from scripts.download_static import download_all_static

        logger.info("\n>>> Static datasets")
        result = download_all_static()
        summary["static"] = result

    if dataset is None or dataset == "sentinel5p":
        from scripts.download_sentinel5p import download_all_sentinel5p

        logger.info("\n>>> Sentinel-5P")
        result = download_all_sentinel5p(start_date=sd, end_date=ed)
        summary["sentinel5p"] = result

    if dataset is None or dataset == "era5":
        from scripts.download_era5 import download_all_era5

        logger.info("\n>>> ERA5-Land")
        result = download_all_era5(start_date=sd, end_date=ed)
        summary["era5"] = result

    if dataset is None or dataset == "modis_fire":
        from scripts.download_modis_fire import download_all_modis_fire

        logger.info("\n>>> MODIS Fire")
        result = download_all_modis_fire(start_date=sd, end_date=ed)
        summary["modis_fire"] = result

    if dataset is None or dataset == "viirs_fire":
        from scripts.download_viirs_fire import download_all_viirs_fire

        logger.info("\n>>> VIIRS Fire")
        result = download_all_viirs_fire(start_date=sd, end_date=ed)
        summary["viirs_fire"] = result

    elapsed = time.time() - t0

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("  DOWNLOAD SUMMARY")
    logger.info("=" * 60)

    for name, result in summary.items():
        if isinstance(result, dict) and "success" in result:
            logger.info(
                "  %-15s  success=%d  failed=%d",
                name, result["success"], result["failed"],
            )
        elif isinstance(result, dict):
            # Static datasets return {name: bool}
            for sub_name, ok in result.items():
                status = "SUCCESS" if ok else "FAILED"
                logger.info("  %-15s  %s", sub_name, status)
        else:
            logger.info("  %-15s  %s", name, result)

    logger.info("-" * 60)
    logger.info("  Elapsed time: %s", _format_elapsed(elapsed))
    logger.info("=" * 60)


def _print_dry_run(
    dataset: Optional[str],
    start_date: str,
    end_date: str,
) -> None:
    """Show what would be downloaded without actually downloading."""
    from scripts.utils import get_monthly_intervals
    from scripts.config import S5P_COLLECTIONS, ERA5_BANDS

    intervals = get_monthly_intervals(start_date, end_date)
    n_months = len(intervals)

    logger.info("\n[DRY RUN] The following downloads would be performed:\n")

    if dataset is None or dataset == "static":
        logger.info("  STATIC DATASETS:")
        logger.info("    - WorldPop (latest year) -> data/raw/worldpop/worldpop_latest.tif")
        logger.info("    - SRTM elevation          -> data/raw/srtm/srtm_elevation.tif")
        logger.info("")

    if dataset is None or dataset == "sentinel5p":
        logger.info("  SENTINEL-5P (%d months x 5 variables = %d files):", n_months, n_months * 5)
        for var, meta in S5P_COLLECTIONS.items():
            logger.info("    - %s : %s", var.upper(), meta["collection"])
        logger.info("")

    if dataset is None or dataset == "era5":
        logger.info("  ERA5-LAND (%d months = %d files):", n_months, n_months)
        logger.info("    Bands: %s", ", ".join(ERA5_BANDS))
        logger.info("")

    if dataset is None or dataset == "modis_fire":
        logger.info("  MODIS FIRE (%d months = %d files):", n_months, n_months)
        logger.info("    Collection: MODIS/061/MOD14A1")
        logger.info("")

    if dataset is None or dataset == "viirs_fire":
        logger.info("  VIIRS FIRE (%d months = %d files):", n_months, n_months)
        logger.info("    Collection: NASA/VIIRS/002/VNP14A1")
        logger.info("")

    total = 0
    if dataset is None or dataset == "static":
        total += 2
    if dataset is None or dataset == "sentinel5p":
        total += n_months * 5
    if dataset is None or dataset == "era5":
        total += n_months
    if dataset is None or dataset == "modis_fire":
        total += n_months
    if dataset is None or dataset == "viirs_fire":
        total += n_months

    logger.info("  TOTAL FILES: %d", total)


if __name__ == "__main__":
    main()
