"""
AetherIQ — Central Configuration
=================================
All pipeline settings, paths, and collection metadata.
Every other module imports from here. No hardcoded paths elsewhere.
"""

import os
from pathlib import Path
from typing import Dict, List

# ── Google Earth Engine ─────────────────────────────────────────────────
GEE_PROJECT: str = "aetheriq-2026-1731"

# ── Temporal range ───────────────────────────────────────────────────
START_DATE: str = "2021-01-01"
END_DATE: str = "2024-12-31"

# ── Spatial extent (India bounding box) ─────────────────────────────
# Format: [west, south, east, north]
INDIA_BBOX: List[float] = [68.0, 6.0, 97.5, 37.5]

# ── Download settings ───────────────────────────────────────────────
TARGET_SCALE: int = 11132
OUTPUT_FORMAT: str = "GeoTIFF"
MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 10.0
MAX_WORKERS: int = 4

# ── QA threshold for Sentinel-5P ────────────────────────────────────
S5P_QA_THRESHOLD: float = 0.75

# ── Base directory (project root) ───────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ── Derived paths ───────────────────────────────────────────────────
DATA_DIR: Path = BASE_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
LOG_DIR: Path = BASE_DIR / "logs"

# Raw data sub-directories
S5P_DIR: Path = RAW_DIR / "sentinel5p"
ERA5_DIR: Path = RAW_DIR / "era5"
MODIS_FIRE_DIR: Path = RAW_DIR / "modis_fire"
VIIRS_FIRE_DIR: Path = RAW_DIR / "viirs_fire"
WORLDPOP_DIR: Path = RAW_DIR / "worldpop"
SRTM_DIR: Path = RAW_DIR / "srtm"

# Sentinel-5P sub-directories
HCHO_DIR: Path = S5P_DIR / "hcho"
NO2_DIR: Path = S5P_DIR / "no2"
SO2_DIR: Path = S5P_DIR / "so2"
CO_DIR: Path = S5P_DIR / "co"
O3_DIR: Path = S5P_DIR / "o3"

# Metadata and checksum files
METADATA_CSV: Path = RAW_DIR / "metadata.csv"
CHECKSUMS_CSV: Path = RAW_DIR / "checksums.csv"

# ── Sentinel-5P collection definitions ─────────────────────────────
S5P_COLLECTIONS: Dict[str, Dict[str, str]] = {
    "hcho": {
        "collection": "COPERNICUS/S5P/OFFL/L3_HCHO",
        "band": "tropospheric_HCHO_column_number_density",
    },
    "no2": {
        "collection": "COPERNICUS/S5P/OFFL/L3_NO2",
        "band": "tropospheric_NO2_column_number_density",
    },
    "so2": {
        "collection": "COPERNICUS/S5P/OFFL/L3_SO2",
        "band": "SO2_column_number_density",
    },
    "co": {
        "collection": "COPERNICUS/S5P/OFFL/L3_CO",
        "band": "CO_column_number_density",
    },
    "o3": {
        "collection": "COPERNICUS/S5P/OFFL/L3_O3",
        "band": "O3_column_number_density",
    },
}

# ── ERA5-Land bands ─────────────────────────────────────────────────
ERA5_BANDS: List[str] = [
    "temperature_2m",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "surface_pressure",
    "dewpoint_temperature_2m",
    "total_precipitation",
    "surface_solar_radiation_downwards",
]

# ── All directories to create at startup ───────────────────────────
ALL_DIRS: List[Path] = [
    DATA_DIR,
    RAW_DIR,
    LOG_DIR,
    S5P_DIR,
    HCHO_DIR,
    NO2_DIR,
    SO2_DIR,
    CO_DIR,
    O3_DIR,
    ERA5_DIR,
    MODIS_FIRE_DIR,
    VIIRS_FIRE_DIR,
    WORLDPOP_DIR,
    SRTM_DIR,
]
