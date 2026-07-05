"""
AetherIQ — Feature Merge Pipeline
=================================
Creates the final machine-learning-ready raster stack by combining
all processed datasets. Aligns everything to the HCHO grid.
"""

import logging
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple

import rasterio
from tqdm import tqdm

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config, utils


def get_available_months() -> List[Tuple[int, int]]:
    """Detect available months based on the HCHO reference dataset.
    
    Returns:
        Sorted list of (year, month) tuples.
    """
    months = set()
    hcho_dir = config.PROCESSED_S5P_DIR / "hcho"
    if not hcho_dir.exists():
        return []
    
    pattern = re.compile(r"(\d{4})_(\d{2})")
    for p in hcho_dir.glob("*.tif"):
        match = pattern.search(p.name)
        if match:
            months.add((int(match.group(1)), int(match.group(2))))
    
    return sorted(list(months))


def get_monthly_file(dir_path: Path, year: int, month: int, dataset_name: str) -> Path:
    """Find a monthly file matching the year_month pattern."""
    if not dir_path.exists():
        raise FileNotFoundError(
            f"Missing {dataset_name} for {year}-{month:02d}. Expected in {dir_path}"
        )
        
    pattern = f"*{year}_{month:02d}*.tif"
    matches = list(dir_path.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"Missing {dataset_name} for {year}-{month:02d}. Expected in {dir_path}"
        )
        
    return sorted(matches)[0]


def get_static_file(dir_path: Path, dataset_name: str) -> Path:
    """Find the latest static file in a directory."""
    if not dir_path.exists():
        raise FileNotFoundError(f"Missing {dataset_name}. Expected in {dir_path}")
        
    matches = list(dir_path.glob("*.tif"))
    if not matches:
        raise FileNotFoundError(f"Missing {dataset_name}. Expected in {dir_path}")
        
    return sorted(matches)[-1]


def _extract_era5_bands(src_path: Path, dst_path: Path, logger: logging.Logger) -> None:
    """Extract exactly 6 bands from ERA5 to match the 15-band feature schema.
    
    Preserves:
      1. Temperature
      2. Wind U
      3. Wind V
      4. Surface Pressure
      5. Dew Point
      6. Boundary Layer Height (assumed to be band 6)
    """
    with rasterio.open(src_path) as src:
        if src.count < 6:
            raise ValueError(
                f"ERA5 file {src_path.name} has {src.count} bands, expected at least 6."
            )
        
        profile = src.profile.copy()
        profile.update(count=6)
        
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(1, 7):
                dst.write(src.read(i), i)
                
    logger.debug("Extracted 6 bands from ERA5 -> %s", dst_path.name)


def merge_single_month(
    year: int,
    month: int,
    logger: logging.Logger,
) -> bool:
    """Merge all datasets for a single month into one feature stack.
    
    Args:
        year: The year to process.
        month: The month to process.
        logger: The configured logger instance.
        
    Returns:
        True if the month was successfully processed, False otherwise.
    """
    out_path = config.PROCESSED_FEATURES_DIR / f"features_{year}_{month:02d}.tif"
    
    try:
        # Gather all required paths in exact requested band order
        paths_to_merge = []
        
        # 1. Reference grid: HCHO
        hcho_path = get_monthly_file(
            config.PROCESSED_S5P_DIR / "hcho", year, month, "HCHO"
        )
        paths_to_merge.append(hcho_path)
        
        # 2-5. S5P Gases (dynamically driven by config)
        for gas in config.S5P_COLLECTIONS:
            if gas == "hcho":
                continue
            p = get_monthly_file(
                config.PROCESSED_S5P_DIR / gas, year, month, gas.upper()
            )
            paths_to_merge.append(p)
            
        # 6-11. ERA5
        era5_path = get_monthly_file(config.PROCESSED_ERA5_DIR, year, month, "ERA5")
        paths_to_merge.append(era5_path)
        
        # 12. MODIS Fire
        modis_path = get_monthly_file(
            config.PROCESSED_FIRE_DIR / "modis", year, month, "MODIS"
        )
        paths_to_merge.append(modis_path)
        
        # 13. VIIRS Fire
        viirs_path = get_monthly_file(
            config.PROCESSED_FIRE_DIR / "viirs", year, month, "VIIRS"
        )
        paths_to_merge.append(viirs_path)
        
        # 14. Static: WorldPop
        worldpop_path = get_static_file(
            config.PROCESSED_STATIC_DIR / "worldpop", "WorldPop"
        )
        paths_to_merge.append(worldpop_path)
        
        # 15. Static: SRTM
        srtm_path = get_static_file(config.PROCESSED_STATIC_DIR / "srtm", "SRTM")
        paths_to_merge.append(srtm_path)
        
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            
            # Step A: Pre-process ERA5 to extract exactly the 6 bands needed
            era5_extracted_path = temp_dir / f"extracted_{era5_path.name}"
            _extract_era5_bands(era5_path, era5_extracted_path, logger)
            
            # Update the paths_to_merge list to use the extracted ERA5 raster
            # ERA5 is exactly at index equal to the number of S5P collections
            era5_index = len(config.S5P_COLLECTIONS)
            paths_to_merge[era5_index] = era5_extracted_path
            
            aligned_files = [hcho_path]
            
            # Step B: Align everything to HCHO
            for i, src_path in enumerate(paths_to_merge[1:], start=1):
                aligned_path = temp_dir / f"aligned_{src_path.name}"
                logger.info(
                    "Aligning %d/%d: %s",
                    i,
                    len(paths_to_merge) - 1,
                    src_path.name,
                )
                utils.align_raster_to_reference(src_path, hcho_path, aligned_path)
                aligned_files.append(aligned_path)
                
            # Step C: Validate spatial consistency and count bands
            with rasterio.open(aligned_files[0]) as ref:
                ref_crs = ref.crs
                ref_transform = ref.transform
                ref_width = ref.width
                ref_height = ref.height
                
            total_bands = 0
            for p in aligned_files:
                with rasterio.open(p) as src:
                    if (
                        src.crs != ref_crs
                        or src.transform != ref_transform
                        or src.width != ref_width
                        or src.height != ref_height
                    ):
                        raise ValueError(
                            f"Spatial inconsistency found in {p.name} after alignment."
                        )
                    total_bands += src.count
                    
            # Step D: Validate exactly 15 bands
            if total_bands != 15:
                raise ValueError(
                    f"Validation failed: Expected exactly 15 feature bands, found {total_bands}."
                )
                
            # Step E: Stack everything
            logger.info(
                "Stacking %d files (%d bands) into %s...",
                len(aligned_files),
                total_bands,
                out_path.name,
            )
            utils.stack_rasters(aligned_files, out_path)
            
            # Step F: Verify output
            if not utils.verify_download(out_path):
                raise RuntimeError("Output verification failed for %s" % out_path.name)
            
        return True

    except FileNotFoundError as e:
        logger.warning("Skipping %d-%02d gracefully: %s", year, month, e)
        return False
    except Exception:
        logger.exception("Failed to merge features for %d-%02d", year, month)
        return False


def merge_all(logger: logging.Logger) -> Dict[str, int]:
    """Run the feature merging pipeline for all available months.
    
    Args:
        logger: The configured logger instance.
        
    Returns:
        A dictionary with counts for 'processed', 'skipped', and 'failed'.
    """
    config.PROCESSED_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    
    months_to_process = get_available_months()
    if not months_to_process:
        logger.warning("No data found to merge (checked HCHO processed dir).")
        return {"processed": 0, "skipped": 0, "failed": 0}
        
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    
    for year, month in tqdm(months_to_process, desc="Merging", unit="month"):
        out_path = config.PROCESSED_FEATURES_DIR / f"features_{year}_{month:02d}.tif"
        
        # Resume support
        if out_path.exists() and utils.verify_download(out_path):
            logger.info("SKIP (exists): %s", out_path.name)
            skipped_count += 1
            continue
            
        start_time = time.time()
        success = merge_single_month(year, month, logger)
        
        if success:
            processed_count += 1
            elapsed = time.time() - start_time
            logger.info("Processed %s (%.1f s)", out_path.name, elapsed)
        else:
            failed_count += 1
            
    logger.info("Finished feature merge pipeline.")
    logger.info(
        "Processed=%d Skipped=%d Failed=%d",
        processed_count,
        skipped_count,
        failed_count,
    )
    
    return {
        "processed": processed_count,
        "skipped": skipped_count,
        "failed": failed_count,
    }


def main() -> None:
    """Run the Feature Merge pipeline."""
    logger = utils.setup_logging("merge_features")
    logger.info("Starting Feature Merge pipeline...")
    
    pipeline_start_time = time.time()
    
    counts = merge_all(logger)
    
    pipeline_elapsed = time.time() - pipeline_start_time
    hours, rem = divmod(pipeline_elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    elapsed_str = f"{int(hours):02d}h {int(minutes):02d}m {seconds:05.2f}s"
    
    summary = (
        "\n========================================\n"
        "Feature Merge Summary\n"
        "========================================\n"
        f"Months processed: {counts['processed']}\n"
        f"Months skipped:   {counts['skipped']}\n"
        f"Months failed:    {counts['failed']}\n"
        f"Elapsed time:     {elapsed_str}\n"
        "========================================"
    )
    logger.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
