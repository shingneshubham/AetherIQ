# AetherIQ — Surface AQI Prediction & HCHO Hotspot Detection

> **ISRO Bhartiya Antariksh Hackathon 2026**
>
> Satellite-driven Air Quality Index prediction and Formaldehyde hotspot
> detection over India using multi-source Earth Observation data.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Google Earth Engine | Authenticated (`earthengine authenticate`) |
| GEE Cloud Project | `aetheriq-2026-1731` |

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-org>/AetherIQ.git
cd AetherIQ

# Create virtual environment
python -m venv .venv

# Activate
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Authenticate with Google Earth Engine (one-time)
earthengine authenticate
```

## Project Structure

```
AetherIQ/
├── data/
│   └── raw/
│       ├── sentinel5p/
│       │   ├── hcho/          # Formaldehyde monthly medians
│       │   ├── no2/           # Nitrogen dioxide
│       │   ├── so2/           # Sulphur dioxide
│       │   ├── co/            # Carbon monoxide
│       │   └── o3/            # Ozone
│       ├── era5/              # ERA5-Land meteorological reanalysis
│       ├── modis_fire/        # MODIS active fire counts
│       ├── viirs_fire/        # VIIRS active fire counts
│       ├── worldpop/          # Population density
│       ├── srtm/              # SRTM elevation
│       ├── metadata.csv       # Download metadata log
│       └── checksums.csv      # SHA-256 checksums
│
├── scripts/
│   ├── config.py                 # Central configuration
│   ├── utils.py                  # Shared utilities
│   ├── download_sentinel5p.py    # S5P trace-gas downloader
│   ├── download_era5.py          # ERA5-Land downloader
│   ├── download_modis_fire.py    # MODIS fire downloader
│   ├── download_viirs_fire.py    # VIIRS fire downloader
│   ├── download_static.py        # WorldPop + SRTM downloader
│   └── run_all.py                # Pipeline orchestrator (CLI)
│
├── logs/                         # Per-dataset log files
├── requirements.txt
└── README.md
```

## Data Sources

### Satellite Trace Gases — Sentinel-5P / TROPOMI

| Variable | GEE Collection | Band |
|---|---|---|
| HCHO | `COPERNICUS/S5P/OFFL/L3_HCHO` | `tropospheric_HCHO_column_number_density` |
| NO₂ | `COPERNICUS/S5P/OFFL/L3_NO2` | `tropospheric_NO2_column_number_density` |
| SO₂ | `COPERNICUS/S5P/OFFL/L3_SO2` | `SO2_column_number_density` |
| CO | `COPERNICUS/S5P/OFFL/L3_CO` | `CO_column_number_density` |
| O₃ | `COPERNICUS/S5P/OFFL/L3_O3` | `O3_column_number_density` |

- **QA Mask**: `qa_value >= 0.75`
- **Composite**: Monthly **median**
- **Output**: `data/raw/sentinel5p/{variable}/{variable}_YYYY_MM.tif`

### Meteorology — ERA5-Land

| Band | Description |
|---|---|
| `temperature_2m` | 2-metre temperature |
| `u_component_of_wind_10m` | U-component of 10m wind |
| `v_component_of_wind_10m` | V-component of 10m wind |
| `surface_pressure` | Surface pressure |
| `dewpoint_temperature_2m` | 2-metre dewpoint temperature |
| `boundary_layer_height` | Planetary boundary layer height |

- **Filter**: `hour == 8` (08:00 UTC ≈ 13:30 IST)
- **Composite**: Monthly **mean**
- **Output**: `data/raw/era5/era5_YYYY_MM.tif`

### Fire Activity — MODIS & VIIRS

| Sensor | Collection | Processing |
|---|---|---|
| MODIS | `MODIS/061/MOD14A1` | Binary fire mask (`FireMask >= 7`), monthly **sum** |
| VIIRS | `NASA/VIIRS/002/VNP14A1` | Binary fire mask (`FireMask >= 7`), monthly **sum** |

> **Important**: FireMask is categorical. Raw values are **never** summed directly.
> They are first converted to binary (fire = 1, no fire = 0), then summed.

- **Output**: `data/raw/modis_fire/modis_fire_YYYY_MM.tif`
- **Output**: `data/raw/viirs_fire/viirs_fire_YYYY_MM.tif`

### Static Datasets

| Dataset | Collection | Output |
|---|---|---|
| WorldPop | `WorldPop/GP/100m/pop` | `data/raw/worldpop/worldpop_latest.tif` |
| SRTM | `USGS/SRTMGL1_003` | `data/raw/srtm/srtm_elevation.tif` |

## Running the Pipeline

### Full Pipeline

```bash
python scripts/run_all.py
```

### Specific Datasets

```bash
python scripts/run_all.py --dataset sentinel5p
python scripts/run_all.py --dataset era5
python scripts/run_all.py --dataset modis_fire
python scripts/run_all.py --dataset viirs_fire
python scripts/run_all.py --dataset static
```

### Custom Date Range

```bash
python scripts/run_all.py --start 2023-01-01 --end 2023-12-31
```

### Dry Run

```bash
python scripts/run_all.py --dry-run
```

Shows what would be downloaded without actually downloading.

### Individual Scripts

```bash
python scripts/download_sentinel5p.py
python scripts/download_era5.py
python scripts/download_modis_fire.py
python scripts/download_viirs_fire.py
python scripts/download_static.py
```

## Execution Order

1. **Static datasets** (WorldPop, SRTM) — downloaded once
2. **Sentinel-5P** — 5 variables × 48 months = 240 files
3. **ERA5-Land** — 48 months = 48 files
4. **MODIS Fire** — 48 months = 48 files
5. **VIIRS Fire** — 48 months = 48 files

**Total: ~386 GeoTIFF files** (for the full 2021–2024 range)

## Pipeline Features

- **geedim** for direct-to-disk downloads (no Google Drive dependency)
- **Resume support**: skips already-downloaded, verified files
- **Retry logic**: up to 3 attempts with exponential backoff per file
- **Download verification**: file existence + size + rasterio open check
- **SHA-256 checksums**: `data/raw/checksums.csv`
- **Metadata tracking**: `data/raw/metadata.csv` with full provenance
- **Logging**: per-dataset log files in `logs/`
- **Fault-tolerant**: a single failed download never crashes the pipeline
- **CLI**: flexible `--dataset`, `--start`, `--end`, `--dry-run` options

## Datasets NOT Available Through GEE

The following datasets must be **downloaded manually** as they are not
available through Google Earth Engine:

- **CPCB AQI ground observations** — Download from
  [CPCB CCR](https://airquality.cpcb.gov.in/) or the CPCB data portal.
- **INSAT-3D AOD (Aerosol Optical Depth)** — Download from
  [MOSDAC](https://mosdac.gov.in/) (Meteorological & Oceanographic
  Satellite Data Archival Centre).

## License

This project is developed for the ISRO Bhartiya Antariksh Hackathon 2026.
