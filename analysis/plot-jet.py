#!/usr/bin/env python3
"""
Plot jet diagnostics from the annual mean of the zonal-mean wind.

Left y-axis:
    lat_of_max (solid lines)

Right y-axis:
    pfull_of_max_hPa (dashed lines)

X-axis:
    Years (2000–2035)

Input files (same directory as this script):
    ua_results_slabctr.nc
    ua_results_g5-2km.nc
    ua_results_u4-10km.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import matplotlib.pyplot as plt

REFERENCE_FILE = "/gpfs/data/fs72044/icon13/analysis/slabctr_WIND.nc"
G5_FILE = "/gpfs/data/fs72044/icon13/analysis/slab-fallout-g5-2km_WIND.nc"
U4_FILE = "/gpfs/data/fs72044/icon13/analysis/slab-fallout-u4-10km_WIND.nc"

DEFAULT_INPUT: str = "default"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute annual zonal-mean zonal wind (ua) over 20–80° and 100–400 hPa."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=DEFAULT_INPUT,
        help="The input to choose, either default with reference,G5,U4 or custom dataset path.",
    )
    parser.add_argument(
        "--lat-min",
        type=float,
        default=20.0,
        help="Minimum latitude in degrees for the analysis band (default: 20).",
    )
    parser.add_argument(
        "--lat-max",
        type=float,
        default=80.0,
        help="Maximum latitude in degrees for the analysis band (default: 80).",
    )
    parser.add_argument(
        "--pmin",
        type=float,
        default=100.0,
        help="Lower pressure limit in hPa (default: 100).",
    )
    parser.add_argument(
        "--pmax",
        type=float,
        default=400.0,
        help="Upper pressure limit in hPa (default: 400).",
    )
    parser.add_argument(
        "--output",
        default="jet_max_time_series.pdf",
        help="Output image path for the jet plot.",
    )
    return parser.parse_args()


def open_dataset(path: str) -> xr.Dataset:
    """Open the NetCDF file lazily with dask chunking for the large 3D fields."""
    return xr.open_dataset(
        path,
        decode_times=False,
        chunks={"time": 10, "height": 47, "lat": 180, "lon": 360},
    )


def decode_time_index(time: xr.DataArray) -> xr.DataArray:
    """Decode ICON's numeric time coordinate (YYYYMMDD format) to datetime64."""
    if np.issubdtype(time.dtype, np.datetime64):
        return time

    # Assume time values are integers in YYYYMMDD format
    try:
        values = time.values.astype(np.int64)
        # Convert integers to strings with zero-padding to 8 chars
        date_strings = np.array([f"{v:08d}" for v in values])
        # Parse as datetime with YYYYMMDD format
        decoded = pd.to_datetime(date_strings, format="%Y%m%d", utc=False).to_numpy(dtype="datetime64[ns]")
        return xr.DataArray(
            decoded, 
            coords={time.name: decoded}, 
            dims=(time.name,), 
            name=time.name
        )
    except Exception as e:
        raise ValueError(
            f"Could not decode time coordinate '{time.name}' with dtype {time.dtype}: {e}"
        )


def compute_annual_max_ws_location(
    ds: xr.Dataset,
    lat_min: float = 20.0,
    lat_max: float = 80.0,
    pmin_hpa: float = 100.0,
    pmax_hpa: float = 400.0,
) -> xr.Dataset:
    """Compute max wind speed and its location (lat, height) from pre-computed annual/zonal means."""
    if "wind_speed" not in ds:
        raise ValueError("Dataset must contain 'wind_speed' (pre-computed zonal/annual mean).")
    if "pfull" not in ds:
        raise ValueError("Dataset must include 'pfull' to restrict by pressure.")

    ds = ds.assign_coords(time=decode_time_index(ds["time"]))
    ds = ds.sel(lat=slice(lat_min, lat_max))
    
    pfull_hpa = ds["pfull"] / 100.0
    pressure_mask = (
        (pfull_hpa >= min(pmin_hpa, pmax_hpa))
        & (pfull_hpa <= max(pmin_hpa, pmax_hpa))
    )

    ws_masked = ds["wind_speed"].where(pressure_mask)
    
    if "time" not in ws_masked.dims:
        raise ValueError("Dataset wind_speed must have 'time' dimension.")
    
    years = ws_masked["time"].dt.year.values
    max_ws_values = []
    lat_values = []
    height_values = []
    pfull_values = []

    for t_idx, year in enumerate(years):
        yearly = ws_masked.isel(time=t_idx)
        stacked = yearly.stack(z=("lat", "height"))
        filled = stacked.fillna(-np.inf)
        idx = int(filled.argmax(dim="z").compute().item())

        max_ws = float(filled.isel(z=idx).compute().item())
        lat_of_max = float(stacked["lat"].isel(z=idx).compute().item())
        height_of_max = float(stacked["height"].isel(z=idx).compute().item())

        pfull_of_max = float(
            ds["pfull"].isel(time=t_idx).sel(height=height_of_max, lat=lat_of_max, method="nearest").compute().item()
        ) / 100.0

        max_ws_values.append(max_ws)
        lat_values.append(lat_of_max)
        height_values.append(height_of_max)
        pfull_values.append(pfull_of_max)

    return xr.Dataset(
        data_vars={
            "ws_max": (
                ["year"],
                np.array(max_ws_values, dtype=float),
                {"units": "m s-1", "long_name": "Annual maximum of year-mean zonally averaged wind speed"},
            ),
            "lat_of_max": (
                ["year"],
                np.array(lat_values, dtype=float),
                {"units": "degrees_north", "long_name": "Latitude of max wind speed"},
            ),
            "height_of_max": (
                ["year"],
                np.array(height_values, dtype=float),
                {"units": ds["height"].attrs.get("units", "unknown"), "long_name": "Height of max wind speed"},
            ),
            "pfull_of_max_hPa": (
                ["year"],
                np.array(pfull_values, dtype=float),
                {"units": "hPa", "long_name": "Pressure at max wind speed"},
            ),
        },
        coords={"year": years},
    )

def load_data(
    filename: Path | str,
    lat_min: float,
    lat_max: float,
    pmin_hpa: float,
    pmax_hpa: float
) -> None:
    input_ds = xr.open_dataset(filename)

    result_ds = compute_annual_max_ws_location(
        input_ds,
        lat_min=lat_min,
        lat_max=lat_max,
        pmin_hpa=pmin_hpa,
        pmax_hpa=pmax_hpa,
    )

    years = pd.to_datetime(result_ds["year"].values, format="%Y")

    lat = result_ds["lat_of_max"].squeeze()
    p = result_ds["pfull_of_max_hPa"].squeeze()

    mask = (years.year >= 2000) & (years.year <= 2035)

    years = years[mask]
    lat = lat.isel(year=mask).values
    p = p.isel(year=mask).values

    return years, lat, p


def plot_jet_evolution(args: argparse.Namespace) -> None:
    output_path = Path(args.output)

    if args.input == DEFAULT_INPUT:
        datasets = [
            ("reference", REFERENCE_FILE, "tab:blue"),
            ("5G2", G5_FILE, "tab:orange"),
            ("4U10", U4_FILE, "tab:green"),
        ]
    else:
        datasets = [
            ("run", args.input, "tab:blue"),
        ] 

    fig, ax_lat = plt.subplots(figsize=(12, 6))

    ax_p = ax_lat.twinx()

    # move y-axes outward slightly
    ax_lat.spines["left"].set_position(("outward", 8))
    ax_p.spines["right"].set_position(("outward", 8))

    # make right axis dashed
    ax_p.spines["right"].set_linestyle("--")
    ax_p.spines["right"].set_linewidth(1.0) #remove

    legend_lines = []
    legend_labels = []

    for label, filename, color in datasets:

        years, lat, p = load_data(
            filename,
            lat_min=args.lat_min,
            lat_max=args.lat_max,
            pmin_hpa=args.pmin,
            pmax_hpa=args.pmax
        )

        line_lat, = ax_lat.plot(
            years,
            lat,
            color=color,
            linestyle="-",
            linewidth=1.5,
        )

        ax_p.plot(
            years,
            p,
            color=color,
            linestyle="--",
            linewidth=1.5,
        )

        legend_lines.append(line_lat)
        legend_labels.append(label)

    # Left axis: latitude
    ax_lat.set_ylabel("Latitude of jet maximum (°N)", fontsize=14)
    ax_lat.set_ylim(35, 80)
    ax_lat.tick_params(axis="both", labelsize=14)
    ax_lat.spines["right"].set_visible(False) #remove

    # Right axis: pressure
    ax_p.set_ylabel("Pressure of jet maximum (hPa)", fontsize=14)
    ax_p.set_ylim(250, 100)   # inverted
    ax_p.tick_params(axis="y", labelsize=14)
    ax_p.spines["left"].set_visible(False) #remove

    # X axis
    ax_lat.set_xlim(
        pd.Timestamp("2000-01-01"),
        pd.Timestamp("2035-12-31"),
    )

    ax_lat.spines["top"].set_visible(False) #remove
    ax_p.spines["top"].set_visible(False) #remove


    plt.xticks(rotation=30)

    # Title
    fig.suptitle("Latitude and pressure of maximum jet wind speed", fontsize=18)

    # Legend
    ax_lat.legend(
        legend_lines,
        legend_labels,
        loc="upper right",
        fontsize=14,
        frameon=False,
    )

    fig.autofmt_xdate()

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)


def main() -> None:
    args = parse_args()

    plot_jet_evolution(args)

if __name__ == "__main__":
    main()