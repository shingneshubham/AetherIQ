"""
AetherIQ — Utility Functions
==============================
Reusable helpers shared across all download scripts.
Handles GEE initialisation, folder setup, logging, download verification,
SHA-256 checksums, and metadata tracking.
"""

import csv
import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from calendar import monthrange
from pathlib import Path
from typing import List, Optional, Tuple

import rasterio

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import config


# ---------------------------------------------------------------------------
# GEE initialisation
# ---------------------------------------------------------------------------

def init_gee() -> None:
    """Initialise Google Earth Engine with the configured project ID.

    Raises:
        RuntimeError: If authentication or initialisation fails.
    """
    import ee

    try:
        ee.Initialize(project=config.GEE_PROJECT)
    except Exception as exc:
        raise RuntimeError(
            f"GEE initialisation failed. Run `earthengine authenticate` first. "
            f"Error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def get_india_geometry():
    """Return an ``ee.Geometry.Rectangle`` covering India.

    Returns:
        ee.Geometry.Rectangle: Bounding box from ``config.INDIA_BBOX``.
    """
    import ee

    west, south, east, north = config.INDIA_BBOX
    return ee.Geometry.Rectangle([west, south, east, north])


# ---------------------------------------------------------------------------
# Temporal helpers
# ---------------------------------------------------------------------------

def get_monthly_intervals(
    start_date: str,
    end_date: str,
) -> List[Tuple[str, str, int, int]]:
    """Generate monthly intervals between *start_date* and *end_date*.

    Args:
        start_date: ISO start date, e.g. ``'2021-01-01'``.
        end_date: ISO end date (inclusive month), e.g. ``'2024-12-31'``.

    Returns:
        List of ``(month_start, month_end, year, month)`` tuples.  Dates are
        ISO-formatted strings.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    intervals: List[Tuple[str, str, int, int]] = []

    current = start.replace(day=1)
    while current <= end:
        year = current.year
        month = current.month
        days_in_month = monthrange(year, month)[1]
        month_start = current.strftime("%Y-%m-%d")
        month_end_dt = current.replace(day=days_in_month)
        # For EE filterDate the end is exclusive, so add one day
        from datetime import timedelta
        next_month = month_end_dt + timedelta(days=1)
        month_end = next_month.strftime("%Y-%m-%d")
        intervals.append((month_start, month_end, year, month))
        current = next_month

    return intervals


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(name: str) -> logging.Logger:
    """Configure a logger that writes to both console and a log file.

    Args:
        name: Logger/file name (without extension).  The log file is written
            to ``config.LOG_DIR / '{name}.log'``.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.LOG_DIR / f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


# ---------------------------------------------------------------------------
# Folder setup
# ---------------------------------------------------------------------------

def setup_folders() -> None:
    """Create every directory listed in ``config.ALL_DIRS``."""
    for d in config.ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Download verification
# ---------------------------------------------------------------------------

def verify_download(path: Path) -> bool:
    """Verify that a downloaded GeoTIFF is valid.

    Checks:
        1. File exists.
        2. File size > 0.
        3. File opens successfully with rasterio.

    Args:
        path: Path to the GeoTIFF file.

    Returns:
        ``True`` if the file passes all checks, ``False`` otherwise.
    """
    if not path.exists():
        return False
    if path.stat().st_size == 0:
        return False
    try:
        with rasterio.open(path) as ds:
            _ = ds.read(1, window=rasterio.windows.Window(0, 0, 1, 1))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SHA-256 checksum
# ---------------------------------------------------------------------------

def generate_sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Args:
        path: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_checksum(filepath: Path, sha256: str) -> None:
    """Append a checksum entry to ``config.CHECKSUMS_CSV``.

    Args:
        filepath: Path to the downloaded file.
        sha256: SHA-256 hex digest.
    """
    csv_path = config.CHECKSUMS_CSV
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["filename", "sha256", "timestamp"])
        writer.writerow([
            str(filepath.relative_to(config.RAW_DIR)),
            sha256,
            datetime.utcnow().isoformat(),
        ])


# ---------------------------------------------------------------------------
# Metadata tracking
# ---------------------------------------------------------------------------

def save_metadata(
    dataset: str,
    variable: str,
    year: int,
    month: int,
    filename: str,
    collection: str,
    band: str,
    scale: int,
    projection: str,
    start_date: str,
    end_date: str,
    download_time: float,
    status: str,
) -> None:
    """Append a metadata row to ``config.METADATA_CSV``.

    Args:
        dataset: Dataset identifier (e.g. ``'sentinel5p'``).
        variable: Variable name (e.g. ``'no2'``).
        year: Data year.
        month: Data month.
        filename: Output filename (relative to raw dir).
        collection: GEE collection ID.
        band: Band name(s).
        scale: Spatial resolution in metres.
        projection: CRS string.
        start_date: Composite start date.
        end_date: Composite end date.
        download_time: Download duration in seconds.
        status: ``'success'`` or ``'failed'``.
    """
    csv_path = config.METADATA_CSV
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "dataset", "variable", "year", "month", "filename",
                "collection", "band", "scale", "projection",
                "start_date", "end_date", "download_time", "status",
            ])
        writer.writerow([
            dataset, variable, year, month, filename,
            collection, band, scale, projection,
            start_date, end_date, f"{download_time:.1f}", status,
        ])


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def retry_download(
    download_fn,
    max_retries: int = config.MAX_RETRIES,
    base_delay: float = config.RETRY_BASE_DELAY,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Execute *download_fn* with exponential-backoff retries.

    Args:
        download_fn: Callable that performs the download.  Must raise on
            failure.
        max_retries: Maximum number of attempts.
        base_delay: Initial delay in seconds (doubled each retry).
        logger: Optional logger for retry messages.

    Returns:
        ``True`` if *download_fn* succeeded, ``False`` after all retries
        exhausted.
    """
    for attempt in range(1, max_retries + 1):
        try:
            download_fn()
            return True
        except Exception as exc:
            if logger:
                logger.warning(
                    "Attempt %d/%d failed: %s", attempt, max_retries, exc
                )
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                if logger:
                    logger.info("Retrying in %.0fs ...", delay)
                time.sleep(delay)
    return False


if __name__ == "__main__":
    setup_folders()
    print("Folder setup complete.")
