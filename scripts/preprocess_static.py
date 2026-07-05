"""
AetherIQ — Static Data Preprocessing
====================================
Processes raw WorldPop and SRTM GeoTIFFs to replace NoData values and
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


def preprocess_dataset(
    input_dir: Path,
    output_dir: Path,
    dataset_name: str,
    logger: logging.Logger,
) -> Dict[str, int]:
    """Preprocess all files for a specific static dataset.
    
    Args:
        input_dir: Directory containing raw GeoTIFFs.
        output_dir: Directory to save processed GeoTIFFs.
        dataset_name: Display name of the dataset (e.g., 'WorldPop', 'SRTM').
        logger: The configured logger instance.
        
    Returns:
        A dictionary with counts for 'processed', 'skipped', and 'failed'.
    """
    logger.info("Starting %s preprocessing...", dataset_name)
    
    if not input_dir.exists():
        logger.warning("Input directory not found: %s. Skipping.", input_dir)
        return {"processed": 0, "skipped": 0, "failed": 0}
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files: List[Path] = sorted(input_dir.glob("*.tif"))
    if not files:
        logger.info("No files found in %s.", input_dir)
        return {"processed": 0, "skipped": 0, "failed": 0}
        
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    
    # Process files with progress bar
    for file_path in tqdm(files, desc=dataset_name, unit="file"):
        out_path = output_dir / file_path.name
        
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
            
    logger.info("Finished %s preprocessing.", dataset_name)
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
    """Run the Static Data preprocessing pipeline.
    
    Reads raw GeoTIFFs for WorldPop and SRTM, replaces NoData values, and saves them
    to the processed directory while maintaining success/failed statistics.
    """
    logger = utils.setup_logging("preprocess_static")
    logger.info("Starting Static Data preprocessing pipeline...")
    
    pipeline_start_time = time.time()
    
    # WorldPop
    worldpop_out = config.PROCESSED_STATIC_DIR / "worldpop"
    worldpop_counts = preprocess_dataset(
        input_dir=config.WORLDPOP_DIR,
        output_dir=worldpop_out,
        dataset_name="WorldPop",
        logger=logger,
    )
    
    # SRTM
    srtm_out = config.PROCESSED_STATIC_DIR / "srtm"
    srtm_counts = preprocess_dataset(
        input_dir=config.SRTM_DIR,
        output_dir=srtm_out,
        dataset_name="SRTM",
        logger=logger,
    )
    
    total_processed = worldpop_counts["processed"] + srtm_counts["processed"]
    total_skipped = worldpop_counts["skipped"] + srtm_counts["skipped"]
    total_failed = worldpop_counts["failed"] + srtm_counts["failed"]
    
    pipeline_elapsed = time.time() - pipeline_start_time
    hours, rem = divmod(pipeline_elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    elapsed_str = f"{int(hours):02d}h {int(minutes):02d}m {seconds:05.2f}s"
    
    summary = (
        "\n==================================\n"
        "Static Data Preprocessing Summary\n"
        "==================================\n"
        f"WorldPop processed: {worldpop_counts['processed']}\n"
        f"WorldPop skipped: {worldpop_counts['skipped']}\n"
        f"WorldPop failed: {worldpop_counts['failed']}\n\n"
        f"SRTM processed: {srtm_counts['processed']}\n"
        f"SRTM skipped: {srtm_counts['skipped']}\n"
        f"SRTM failed: {srtm_counts['failed']}\n\n"
        f"Total processed: {total_processed}\n"
        f"Total skipped: {total_skipped}\n"
        f"Total failed: {total_failed}\n\n"
        f"Elapsed time: {elapsed_str}\n"
        "=================================="
    )
    logger.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
