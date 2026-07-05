"""
AetherIQ — CPCB Ground-Station Data Preprocessing
====================================================
Cleans and merges manually downloaded CPCB (Central Pollution Control
Board) CSV files into a single analysis-ready Parquet dataset.

━━━ MANUAL DOWNLOAD INSTRUCTIONS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPCB does NOT provide a public download API. You must download the data
manually from the CPCB CAAQMS portal:

    1.  Open https://app.cpcbccr.com/ccr/#/caaqm-dashboard-all/caaqm-landing
    2.  Click  "All Stations"  (or choose specific stations).
    3.  Select  "All Parameters"  (PM2.5, PM10, NO2, SO2, CO, O3, etc.).
    4.  Set the date range:
            Start  →  2021-01-01
            End    →  2024-01-01
    5.  Click  "Submit"  to load the data.
    6.  Click  "Export"  (CSV icon) to download the file.
    7.  Save the CSV file(s) into:
            AetherIQ/data/CPCB/

    Tips:
    ─────
    • The portal may limit exports to 6 months at a time — download in
      chunks and save each CSV separately.  This script merges all CSVs
      automatically.
    • Common file names: "site_YYYY.csv", "all_stations_2021.csv", etc.
    • If the portal returns Excel (.xlsx), convert to CSV first.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage
-----
    python scripts/preprocess_cpcb.py
"""

import os
import sys
import glob

import pandas as pd
import numpy as np

# ── Project imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config


# ── Column name mapping ───────────────────────────────────────────────────
# The CPCB portal uses inconsistent naming across downloads.  This dict
# maps common variants to our canonical names.
COLUMN_MAP = {
    # Station / site
    'station': 'station',
    'station name': 'station',
    'site': 'station',
    'site_name': 'station',
    'station_name': 'station',
    'stationname': 'station',
    'location': 'station',
    # Date / time
    'date': 'date',
    'from date': 'date',
    'from_date': 'date',
    'sampling date': 'date',
    'to date': 'date_end',
    'to_date': 'date_end',
    # Pollutants
    'pm2.5': 'PM2.5',
    'pm25': 'PM2.5',
    'pm 2.5': 'PM2.5',
    'pm2.5 (ug/m3)': 'PM2.5',
    'pm10': 'PM10',
    'pm 10': 'PM10',
    'pm10 (ug/m3)': 'PM10',
    'no2': 'NO2',
    'no2 (ug/m3)': 'NO2',
    'so2': 'SO2',
    'so2 (ug/m3)': 'SO2',
    'co': 'CO',
    'co (mg/m3)': 'CO',
    'ozone': 'O3',
    'o3': 'O3',
    'o3 (ug/m3)': 'O3',
}

CANONICAL_COLUMNS = ['station', 'date', 'PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3']


def standardise_columns(df):
    """
    Rename columns to canonical names using COLUMN_MAP.
    Unknown columns are dropped.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame with arbitrary column names.

    Returns
    -------
    pd.DataFrame
        DataFrame with standardised column names, containing only
        the canonical pollutant columns.
    """
    # Lowercase and strip whitespace for matching
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns=COLUMN_MAP)

    # Keep only canonical columns that exist
    available = [c for c in CANONICAL_COLUMNS if c in df.columns]
    df = df[available]
    return df


def preprocess_cpcb():
    """
    Read all CSV files from data/CPCB/, clean and merge them into a
    single Parquet file.

    Output
    ------
    data/CPCB/cpcb_clean.parquet
    """
    csv_pattern = os.path.join(config.CPCB_DIR, '*.csv')
    csv_files = sorted(glob.glob(csv_pattern))

    if not csv_files:
        print(f"[FAIL] No CSV files found in {config.CPCB_DIR}")
        print("    Please download data from CPCB first. See docstring for instructions.")
        return

    print(f"[i] Found {len(csv_files)} CSV file(s) in {config.CPCB_DIR}")

    frames = []
    for fp in csv_files:
        try:
            df = pd.read_csv(fp, low_memory=False)
            df = standardise_columns(df)
            frames.append(df)
            print(f"    OK {os.path.basename(fp):40s} - {len(df):>8,} rows")
        except Exception as exc:
            print(f"    FAIL {os.path.basename(fp):40s} - SKIPPED ({exc})")

    if not frames:
        print("[FAIL] No files could be read successfully.")
        return

    # ── Merge ──────────────────────────────────────────────────────────
    merged = pd.concat(frames, ignore_index=True)

    # ── Date conversion ────────────────────────────────────────────────
    if 'date' in merged.columns:
        merged['date'] = pd.to_datetime(merged['date'], errors='coerce')

    # ── Numeric coercion for pollutant columns ─────────────────────────
    pollutant_cols = ['PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3']
    for col in pollutant_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

    # ── Remove duplicates ──────────────────────────────────────────────
    before = len(merged)
    merged = merged.drop_duplicates()
    after = len(merged)
    dupes_removed = before - after

    # ── Flag missing values as NaN (no interpolation) ──────────────────
    # Already handled by errors='coerce' above -- non-numeric -> NaN.

    # ── Save ───────────────────────────────────────────────────────────
    output_path = os.path.join(config.CPCB_DIR, 'cpcb_clean.parquet')
    merged.to_parquet(output_path, index=False, engine='pyarrow')

    # ── Summary statistics ─────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  CPCB Preprocessing Summary")
    print(f"{'='*60}")

    if 'station' in merged.columns:
        print(f"  Stations       : {merged['station'].nunique():,}")
    if 'date' in merged.columns:
        print(f"  Date range     : {merged['date'].min()} -> {merged['date'].max()}")

    print(f"  Total rows     : {len(merged):,}")
    print(f"  Duplicates rm. : {dupes_removed:,}")

    print(f"\n  Missing values (% NaN):")
    for col in pollutant_cols:
        if col in merged.columns:
            pct = merged[col].isna().mean() * 100
            print(f"    {col:8s} : {pct:6.2f}%")
        else:
            print(f"    {col:8s} : column not found")

    print(f"\n  Output saved to: {output_path}")
    print(f"{'='*60}")


if __name__ == '__main__':
    preprocess_cpcb()
