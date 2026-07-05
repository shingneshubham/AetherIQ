# 🌍 AetherIQ — Surface AQI Prediction & HCHO Hotspot Detection

> **ISRO Bharatiya Antariksh Hackathon 2026**

AetherIQ is an end-to-end geospatial data acquisition pipeline that automates the collection of multi-source Earth Observation datasets for **Surface Air Quality Index (AQI) Prediction** and **Formaldehyde (HCHO) Hotspot Detection** across India using **Google Earth Engine (GEE)**.

---

## 🚀 Features

- Automated Sentinel-5P trace gas downloads (HCHO, NO₂, SO₂, CO, O₃)
- ERA5-Land meteorological data acquisition
- MODIS & VIIRS active fire detection
- WorldPop population density
- SRTM elevation
- Automatic metadata generation
- SHA-256 checksum verification
- Resume interrupted downloads
- Retry mechanism with exponential backoff
- Download verification
- Production-ready modular architecture

---

## 🛠 Tech Stack

- Python 3.10+
- Google Earth Engine (GEE)
- geedim
- Rasterio
- NumPy
- Pandas
- tqdm

---

# 📦 Installation

```bash
# Clone the repository
git clone https://github.com/shingneshubham/AetherIQ.git

cd AetherIQ

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Authenticate Google Earth Engine
earthengine authenticate
```

---

# 📁 Project Structure

```text
AetherIQ/
│
├── data/
│   └── raw/
│       ├── sentinel5p/
│       ├── era5/
│       ├── modis_fire/
│       ├── viirs_fire/
│       ├── worldpop/
│       ├── srtm/
│       ├── metadata.csv
│       └── checksums.csv
│
├── logs/
│
├── scripts/
│   ├── config.py
│   ├── utils.py
│   ├── download_sentinel5p.py
│   ├── download_era5.py
│   ├── download_modis_fire.py
│   ├── download_viirs_fire.py
│   ├── download_static.py
│   └── run_all.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 🛰 Data Sources

| Dataset | Source |
|---------|--------|
| Sentinel-5P | Google Earth Engine |
| ERA5-Land | Google Earth Engine |
| MODIS Fire | Google Earth Engine |
| VIIRS Fire | Google Earth Engine |
| WorldPop | Google Earth Engine |
| SRTM | Google Earth Engine |

---

# 🔄 Pipeline Workflow

```text
Sentinel-5P
      │
ERA5-Land
      │
MODIS Fire
      │
VIIRS Fire
      │
WorldPop
      │
SRTM
      │
────────────────────
Data Validation
      │
Metadata Logging
      │
SHA-256 Checksums
      │
GeoTIFF Dataset
      │
Preprocessing
      │
Surface AQI Prediction
      │
HCHO Hotspot Detection
```

---

# ▶ Running the Pipeline

## Run Everything

```bash
python scripts/run_all.py
```

## Run Individual Dataset

```bash
python scripts/run_all.py --dataset sentinel5p
```

```bash
python scripts/run_all.py --dataset era5
```

```bash
python scripts/run_all.py --dataset modis_fire
```

```bash
python scripts/run_all.py --dataset viirs_fire
```

```bash
python scripts/run_all.py --dataset static
```

---

# 📊 Dataset Statistics (2021–2024)

| Dataset | Files |
|---------|------:|
| Sentinel-5P | 240 |
| ERA5-Land | 48 |
| MODIS Fire | 48 |
| VIIRS Fire | 48 |
| WorldPop | 1 |
| SRTM | 1 |

**Total Generated:** **386 GeoTIFF files**

---

# ✅ Production Features

- Direct-to-disk downloads using geedim
- Resume interrupted downloads
- Retry mechanism with exponential backoff
- Download verification
- SHA-256 checksum generation
- Metadata logging
- Per-dataset logging
- Fault-tolerant execution
- Modular architecture
- Command-line interface

---

# 📌 Manual Datasets

The following datasets are **not available through Google Earth Engine** and must be downloaded manually:

- CPCB AQI Ground Observations
- INSAT-3D Aerosol Optical Depth (AOD)

---

# 🔮 Future Work

- CPCB AQI preprocessing
- INSAT-3D integration
- Feature engineering
- Machine Learning model development
- Surface AQI prediction
- HCHO hotspot detection
- Interactive visualization dashboard
- Web deployment

---

# 🙏 Acknowledgements

- Google Earth Engine
- European Space Agency (Sentinel-5P)
- ECMWF
- NASA
- WorldPop
- ISRO Bharatiya Antariksh Hackathon 2026

---

# 📄 License

This project has been developed for the **ISRO Bharatiya Antariksh Hackathon 2026**.

---

## 👨‍💻 Author

**Shubham Shingne**

B.Tech CSE (Data Science)  
Lovely Professional University

GitHub: https://github.com/shingneshubham
