"""
AetherIQ — INSAT-3D/3DR AOD Data Instructions & Placeholder Reader
=====================================================================
INSAT-3D/3DR Aerosol Optical Depth (AOD) data is NOT available on
Google Earth Engine.  It must be downloaded manually from the MOSDAC
(Meteorological & Oceanographic Satellite Data Archival Centre) portal.

This script:
  1.  Prints step-by-step download instructions.
  2.  Provides a placeholder read_insat_aod() function for when files
      are available.

Usage
-----
    python scripts/insat_aod_instructions.py
"""

import os
import sys

import numpy as np

# ── Project imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import config


def print_download_instructions():
    """
    Print step-by-step instructions for downloading INSAT-3D/3DR AOD
    data from the MOSDAC portal.
    """
    instructions = """
╔══════════════════════════════════════════════════════════════════╗
║           INSAT-3D/3DR AOD — Manual Download Guide             ║
╚══════════════════════════════════════════════════════════════════╝

INSAT AOD data must be downloaded manually from MOSDAC.  Follow
these steps:

─── Step 1: Register ──────────────────────────────────────────────
    • Go to  https://www.mosdac.gov.in
    • Click  "Register"  (top-right).
    • Fill in the registration form with your institutional email.
    • Verify your email and log in.

─── Step 2: Navigate to INSAT-3D Aerosol Products ─────────────────
    • From the main page, go to:
          Data → Catalog → INSAT-3D/3DR
    • Or use the direct search:
          https://www.mosdac.gov.in/catalog
    • Look for product categories:
          - "INSAT-3D Aerosol Optical Depth"
          - "INSAT-3DR Aerosol Optical Depth"
    • Select  "Level-2"  or  "Level-3"  products as available.

─── Step 3: Set Filters ───────────────────────────────────────────
    • Date range   :  2021-01-01  to  2024-01-01
    • Region       :  India  (or set manually:
                       Lat 6°N – 37.5°N, Lon 68°E – 97.5°E)
    • Product type :  AOD (Aerosol Optical Depth)

─── Step 4: Download ──────────────────────────────────────────────
    • Select the files (HDF5 format, .h5 or .hdf5).
    • Download in batches.
    • Save all files to:
          {output_dir}

─── Step 5: Verify ───────────────────────────────────────────────
    • Files should be in HDF5 format.
    • Typical size: 5–50 MB per file.
    • Use the read_insat_aod() function in this script to verify
      that files are readable.

─── Notes ─────────────────────────────────────────────────────────
    • MOSDAC may require approval for bulk downloads.
    • Data availability may vary — some months might be missing.
    • If you need FTP access, email: helpdesk@mosdac.gov.in
    • AOD layer names inside the HDF5 may vary; inspect with
      `h5py` or HDFView to confirm.
""".format(output_dir=config.INSAT_AOD_DIR)

    print(instructions)


def read_insat_aod(filepath):
    """
    Read an INSAT-3D/3DR AOD HDF5 file and return the AOD layer
    as an xarray DataArray.

    Parameters
    ----------
    filepath : str
        Absolute path to an INSAT AOD HDF5 file (.h5 / .hdf5).

    Returns
    -------
    xarray.DataArray
        2-D DataArray with AOD values.  Coordinates are added if
        latitude/longitude datasets are found in the file.

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    KeyError
        If the expected AOD dataset is not found inside the file.

    Notes
    -----
    TODO: Update the dataset key ('AOD') once actual file structure is
          confirmed.  Inspect files with:
              import h5py
              with h5py.File(filepath, 'r') as f:
                  print(list(f.keys()))
    """
    import h5py
    import xarray as xr

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # TODO: Confirm dataset key names from actual INSAT HDF5 files.
    #       Common keys: 'AOD', 'Aerosol_Optical_Depth', 'AOD_550'
    aod_key = 'AOD'
    lat_key = 'Latitude'
    lon_key = 'Longitude'

    with h5py.File(filepath, 'r') as f:
        available_keys = list(f.keys())
        print(f"[i] HDF5 keys: {available_keys}")

        if aod_key not in f:
            raise KeyError(
                f"Dataset '{aod_key}' not found. "
                f"Available keys: {available_keys}. "
                "Update aod_key in read_insat_aod() to match your file."
            )

        aod_data = f[aod_key][:]

        # Attempt to read coordinate arrays
        lat = f[lat_key][:] if lat_key in f else None
        lon = f[lon_key][:] if lon_key in f else None

    # Build xarray DataArray
    if lat is not None and lon is not None:
        # Handle 1-D vs. 2-D coordinate arrays
        if lat.ndim == 2:
            lat = lat[:, 0]
        if lon.ndim == 2:
            lon = lon[0, :]

        da = xr.DataArray(
            data=aod_data,
            dims=['latitude', 'longitude'],
            coords={'latitude': lat, 'longitude': lon},
            name='AOD',
            attrs={'source': 'INSAT-3D/3DR', 'units': 'dimensionless'},
        )
    else:
        da = xr.DataArray(
            data=aod_data,
            dims=['y', 'x'],
            name='AOD',
            attrs={'source': 'INSAT-3D/3DR', 'units': 'dimensionless'},
        )

    # Replace fill values with NaN
    da = da.where(da >= 0)

    print(f"[OK] Loaded AOD - shape: {da.shape}, "
          f"range: [{float(da.min()):.4f}, {float(da.max()):.4f}]")

    return da


if __name__ == '__main__':
    print_download_instructions()
