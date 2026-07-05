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
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import calculate_default_transform, reproject

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



# ============================================================================
# Raster preprocessing utilities
# ============================================================================

# Shared logger for raster utilities
_raster_log: logging.Logger = setup_logging("raster_utils")


def read_raster(path: Path) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Read a raster file and return its data array and profile.

    Args:
        path: Path to the raster file (e.g. GeoTIFF).

    Returns:
        A tuple of ``(data, profile)`` where *data* is a 3-D numpy array with
        shape ``(bands, height, width)`` and *profile* is a dict-like
        rasterio profile containing CRS, transform, dtype, etc.

    Raises:
        FileNotFoundError: If *path* does not exist.
        rasterio.errors.RasterioIOError: If the file cannot be opened.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Raster file not found: {path}")

    try:
        with rasterio.open(path) as src:
            data: np.ndarray = src.read()
            profile: Dict[str, Any] = dict(src.profile)
        _raster_log.debug("Read raster %s — shape %s", path.name, data.shape)
        return data, profile
    except rasterio.errors.RasterioIOError:
        _raster_log.error("Failed to open raster: %s", path)
        raise
    except Exception as exc:
        _raster_log.error("Unexpected error reading %s: %s", path, exc)
        raise


def write_raster(path: Path, data: np.ndarray, profile: Dict[str, Any]) -> None:
    """Write a numpy array to a raster file.

    Args:
        path: Destination file path.  Parent directories are created
            automatically.
        data: 2-D ``(height, width)`` or 3-D ``(bands, height, width)``
            numpy array.
        profile: Rasterio profile dict (CRS, transform, dtype, …).
            The ``count``, ``height``, ``width``, and ``dtype`` keys are
            updated to match *data* before writing.

    Raises:
        ValueError: If *data* does not have 2 or 3 dimensions.
        rasterio.errors.RasterioIOError: If the file cannot be written.
    """
    path = Path(path)
    if data.ndim == 2:
        data = data[np.newaxis, :, :]
    elif data.ndim != 3:
        raise ValueError(
            f"Expected 2-D or 3-D array, got {data.ndim}-D array."
        )

    profile = {**profile}
    profile.update(
        count=data.shape[0],
        height=data.shape[1],
        width=data.shape[2],
        dtype=data.dtype.name,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data)
        _raster_log.debug("Wrote raster %s — shape %s", path.name, data.shape)
    except Exception as exc:
        _raster_log.error("Failed to write raster %s: %s", path, exc)
        raise


def replace_nodata(
    data: np.ndarray,
    nodata: Union[int, float],
    fill_value: float = np.nan,
) -> np.ndarray:
    """Replace nodata pixels with *fill_value*.

    Args:
        data: Input array (modified in-place when possible).
        nodata: The nodata sentinel value to search for.
        fill_value: Replacement value (default ``np.nan``).

    Returns:
        A copy of *data* with nodata pixels replaced.  If *nodata* is
        ``None`` the original array is returned unchanged.

    Raises:
        TypeError: If *data* is not a numpy array.
    """
    if not isinstance(data, np.ndarray):
        raise TypeError(f"Expected np.ndarray, got {type(data).__name__}.")

    if nodata is None:
        _raster_log.debug("No nodata value supplied — skipping replacement.")
        return data

    result = data.copy()
    if np.isnan(nodata):
        mask = np.isnan(result)
    else:
        mask = result == nodata

    count = int(np.count_nonzero(mask))
    result[mask] = fill_value
    _raster_log.debug(
        "Replaced %d nodata pixels (nodata=%s → fill=%s).",
        count,
        nodata,
        fill_value,
    )
    return result


def reproject_raster(
    src_path: Path,
    dst_path: Path,
    dst_crs: str = "EPSG:4326",
) -> None:
    """Reproject a raster to a new coordinate reference system.

    Args:
        src_path: Path to the source raster.
        dst_path: Path for the reprojected output.
        dst_crs: Target CRS string (default ``'EPSG:4326'``).

    Raises:
        FileNotFoundError: If *src_path* does not exist.
        rasterio.errors.RasterioIOError: On read/write failures.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Source raster not found: {src_path}")

    try:
        with rasterio.open(src_path) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
            profile = dict(src.profile)
            profile.update(
                crs=dst_crs,
                transform=transform,
                width=width,
                height=height,
            )

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(dst_path, "w", **profile) as dst:
                for band_idx in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band_idx),
                        destination=rasterio.band(dst, band_idx),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest,
                    )
        _raster_log.info(
            "Reprojected %s → %s (CRS: %s).", src_path.name, dst_path.name, dst_crs
        )
    except Exception as exc:
        _raster_log.error("Reprojection failed for %s: %s", src_path, exc)
        raise


def resample_raster(
    src_path: Path,
    dst_path: Path,
    scale_factor: float,
) -> None:
    """Resample a raster by a given scale factor.

    A *scale_factor* > 1 up-samples (more pixels); < 1 down-samples.

    Args:
        src_path: Path to the source raster.
        dst_path: Path for the resampled output.
        scale_factor: Multiplicative factor applied to width and height.

    Raises:
        FileNotFoundError: If *src_path* does not exist.
        ValueError: If *scale_factor* is not positive.
        rasterio.errors.RasterioIOError: On read/write failures.
    """
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Source raster not found: {src_path}")
    if scale_factor <= 0:
        raise ValueError(f"scale_factor must be positive, got {scale_factor}.")

    try:
        with rasterio.open(src_path) as src:
            new_height = int(src.height * scale_factor)
            new_width = int(src.width * scale_factor)

            data = src.read(
                out_shape=(src.count, new_height, new_width),
                resampling=Resampling.bilinear,
            )

            new_transform = from_bounds(
                *src.bounds, width=new_width, height=new_height
            )
            profile = dict(src.profile)
            profile.update(
                height=new_height,
                width=new_width,
                transform=new_transform,
            )

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(data)

        _raster_log.info(
            "Resampled %s → %s (scale=%.2f, %dx%d).",
            src_path.name,
            dst_path.name,
            scale_factor,
            new_width,
            new_height,
        )
    except Exception as exc:
        _raster_log.error("Resampling failed for %s: %s", src_path, exc)
        raise


def align_raster_to_reference(
    src_path: Path,
    reference_path: Path,
    dst_path: Path,
) -> None:
    """Reproject and resample *src_path* to match a reference raster's grid.

    The output will share the reference raster's CRS, transform, width, and
    height so that both rasters are pixel-aligned.

    Args:
        src_path: Path to the source raster.
        reference_path: Path to the reference raster whose grid is adopted.
        dst_path: Path for the aligned output.

    Raises:
        FileNotFoundError: If *src_path* or *reference_path* does not exist.
        rasterio.errors.RasterioIOError: On read/write failures.
    """
    src_path = Path(src_path)
    reference_path = Path(reference_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Source raster not found: {src_path}")
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference raster not found: {reference_path}")

    try:
        with rasterio.open(reference_path) as ref:
            ref_crs = ref.crs
            ref_transform = ref.transform
            ref_width = ref.width
            ref_height = ref.height

        with rasterio.open(src_path) as src:
            profile = dict(src.profile)
            profile.update(
                crs=ref_crs,
                transform=ref_transform,
                width=ref_width,
                height=ref_height,
            )

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(dst_path, "w", **profile) as dst:
                for band_idx in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band_idx),
                        destination=rasterio.band(dst, band_idx),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=ref_transform,
                        dst_crs=ref_crs,
                        resampling=Resampling.bilinear,
                    )
        _raster_log.info(
            "Aligned %s to %s → %s.",
            src_path.name,
            reference_path.name,
            dst_path.name,
        )
    except Exception as exc:
        _raster_log.error("Alignment failed for %s: %s", src_path, exc)
        raise


def stack_rasters(
    input_files: List[Path],
    output_path: Path,
) -> None:
    """Stack multiple single- or multi-band rasters into one multi-band file.

    All input rasters **must** share the same CRS, transform, width, and
    height.  Use :func:`align_raster_to_reference` beforehand if they differ.

    Args:
        input_files: Ordered list of raster file paths.
        output_path: Path for the stacked output GeoTIFF.

    Raises:
        ValueError: If *input_files* is empty or rasters have mismatched
            spatial properties.
        FileNotFoundError: If any input file does not exist.
        rasterio.errors.RasterioIOError: On read/write failures.
    """
    if not input_files:
        raise ValueError("input_files must not be empty.")

    input_files = [Path(p) for p in input_files]
    for p in input_files:
        if not p.exists():
            raise FileNotFoundError(f"Input raster not found: {p}")

    try:
        # Read the first file to establish the reference grid
        with rasterio.open(input_files[0]) as ref:
            ref_crs = ref.crs
            ref_transform = ref.transform
            ref_width = ref.width
            ref_height = ref.height

        # Count total bands and validate spatial consistency
        total_bands: int = 0
        for p in input_files:
            with rasterio.open(p) as src:
                if (
                    src.crs != ref_crs
                    or src.transform != ref_transform
                    or src.width != ref_width
                    or src.height != ref_height
                ):
                    raise ValueError(
                        f"Raster {p.name} has different spatial properties "
                        f"than {input_files[0].name}.  Align rasters first."
                    )
                total_bands += src.count

        # Build the output profile based on the first file
        with rasterio.open(input_files[0]) as first:
            profile = dict(first.profile)
        profile.update(count=total_bands)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(output_path, "w", **profile) as dst:
            dst_band: int = 1
            for p in input_files:
                with rasterio.open(p) as src:
                    for band_idx in range(1, src.count + 1):
                        dst.write(src.read(band_idx), dst_band)
                        dst_band += 1

        _raster_log.info(
            "Stacked %d files (%d bands) → %s.",
            len(input_files),
            total_bands,
            output_path.name,
        )
    except Exception as exc:
        _raster_log.error("Stacking failed: %s", exc)
        raise


if __name__ == "__main__":
    setup_folders()
    print("Folder setup complete.")
