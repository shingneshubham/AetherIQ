"""
AetherIQ — Sentinel-5P Preprocessing
====================================
Processes raw Sentinel-5P GeoTIFFs to replace NoData values and
prepare them for further analysis.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Dict, List

from tqdm import tqdm

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config, utils


def preprocess_variable(var: str, logger: logging.Logger) -> Dict[str, int]:
    """Preprocess all files for a specific Sentinel-5P variable.
    
    Args:
        var: The variable to process (e.g., 'hcho', 'no2').
        logger: The configured logger instance.
        
    Returns:
        A dictionary with counts for 'processed', 'skipped', and 'failed'.
    """
    logger.info("Starting variable %s", var.upper())
    
    in_dir = config.S5P_DIR / var
    if not in_dir.exists():
        logger.warning("Input directory not found: %s. Skipping.", in_dir)
        return {"processed": 0, "skipped": 0, "failed": 0}
        
    out_dir = config.PROCESSED_S5P_DIR / var
    out_dir.mkdir(parents=True, exist_ok=True)
    
    files: List[Path] = sorted(in_dir.glob("*.tif"))
    if not files:
        logger.info("No files found for %s.", var.upper())
        return {"processed": 0, "skipped": 0, "failed": 0}
        
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    
    # Process files with progress bar
    for file_path in tqdm(files, desc=var.upper(), unit="file"):
        out_path = out_dir / file_path.name
        
        # Resume support
        if out_path.exists() and utils.verify_download(out_path):
            logger.info("SKIP (exists): %s", out_path.name)
            skipped_count += 1
            continue
        
        start_time = time.time()
        try:
            # 1. Read raster using read_raster()
            data, profile = utils.read_raster(file_path)
            
            # 2. Replace NoData values using replace_nodata()
            nodata = profile.get("nodata")
            cleaned_data = utils.replace_nodata(data, nodata)
            
            # 3 & 4. Preserve CRS and metadata, save cleaned raster
            utils.write_raster(out_path, cleaned_data, profile)
            
            # Verify output after writing
            if not utils.verify_download(out_path):
                raise RuntimeError("Output verification failed")
            
            elapsed = time.time() - start_time
            logger.info("Processed %s (%.1f s)", file_path.name, elapsed)
            
            processed_count += 1
        except Exception:
            logger.exception("Failed to process %s", file_path.name)
            failed_count += 1
            
    logger.info("Finished variable %s", var.upper())
    print(f"processed count: {processed_count}")
    print(f"failed count: {failed_count}")
    print(f"skipped count: {skipped_count}")
    
    return {
        "processed": processed_count,
        "skipped": skipped_count,
        "failed": failed_count,
    }


def main() -> None:
    """Run the Sentinel-5P preprocessing pipeline.
    
    Reads raw GeoTIFFs, replaces NoData values, and saves them
    to the processed directory while maintaining success/failed statistics.
    """
    logger = utils.setup_logging("preprocess_s5p")
    logger.info("Starting Sentinel-5P preprocessing pipeline...")
    
    variables = list(config.S5P_COLLECTIONS.keys())
    
    total_processed = 0
    total_skipped = 0
    total_failed = 0
    vars_processed = 0
    
    pipeline_start_time = time.time()
    
    for var in variables:
        vars_processed += 1
        counts = preprocess_variable(var, logger)
        total_processed += counts["processed"]
        total_skipped += counts["skipped"]
        total_failed += counts["failed"]
        
    pipeline_elapsed = time.time() - pipeline_start_time
    hours, rem = divmod(pipeline_elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    elapsed_str = f"{int(hours):02d}h {int(minutes):02d}m {seconds:05.2f}s"
    
    summary = (
        "\n==================================\n"
        "Sentinel-5P Preprocessing Summary\n"
        "==================================\n"
        f"Variables processed: {vars_processed}\n"
        f"Files processed: {total_processed}\n"
        f"Files skipped: {total_skipped}\n"
        f"Files failed: {total_failed}\n"
        f"Elapsed time: {elapsed_str}\n"
        "=================================="
    )
    logger.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
