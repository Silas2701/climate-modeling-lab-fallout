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

RUN_FILES = {
    "5G2": "/gpfs/data/fs72044/icon13/cdo_tests/annual_zonal_mean_g5-2km.nc",
    "4U10": "/gpfs/data/fs72044/icon13/cdo_tests/annual_zonal_mean_u4-10km.nc"
}

REFERENCE_FILE = "/gpfs/data/fs72044/icon13/cdo_tests/annual_zonal_mean_slabctr.nc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute annual zonal-mean zonal wind (ua) over 20–80° and 100–400 hPa."
    )
    parser.add_argument(
        "--run",
        choices=("5G2", "4U10"),
        default="5G2",
        help="Run label to use for the 3D input file.",
    )
    parser.add_argument(
        "--source",
        choices=("run", "reference"),
        default="run",
        help="Use the model run or the reference dataset.",
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
        "--title",
        help="Title for the plot.",
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


def main() -> None:
    args = parse_args()

    if args.source == "run":
        input_path = RUN_FILES[args.run]
    else:
        input_path = REFERENCE_FILE

    print(f"Input file: {input_path}")
    print(f"Selected latitude band: {args.lat_min:.1f} to {args.lat_max:.1f}°")
    print(f"Selected pressure band: {args.pmin:.1f} to {args.pmax:.1f} hPa")

    ds = open_dataset("/gpfs/data/fs72044/icon13/cdo_tests/g5-full-FINAL.nc")
    ds_result = compute_annual_max_ws_location(
        ds,
        lat_min=args.lat_min,
        lat_max=args.lat_max,
        pmin_hpa=args.pmin,
        pmax_hpa=args.pmax,
    )
    
    output_path = Path(args.output)
    plot_jet_evolution(ds_result, output_path=output_path)

    if args.output:
        ds_result.to_netcdf(args.output)
        print(f"\nSaved annual max-location dataset to: {args.output}")


REFERENCE_FILE = "ua_results_slabctr.nc"
G5_FILE = "ua_results_g5-2km.nc"
U4_FILE = "ua_results_u4-10km.nc"


def load_data(filename):
    ds = xr.open_dataset(filename)

    years = pd.to_datetime(ds["time"].values)

    lat = ds["lat_of_max"].squeeze()
    p = ds["pfull_of_max_hPa"].squeeze()

    mask = (years.year >= 2000) & (years.year <= 2035)

    years = years[mask]
    lat = lat.isel(time=mask)
    p = p.isel(time=mask)

    return years, lat.values, p.values


def plot_jet_evolution(ds_result: xr.Dataset, output_path: Path) -> None:

    datasets = [
        ("reference", REFERENCE_FILE, "tab:blue"),
        ("5G2", G5_FILE, "tab:orange"),
        ("4U10", U4_FILE, "tab:green"),
    ]

    fig, ax_lat = plt.subplots(figsize=(10, 5))

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

        years, lat, p = load_data(filename)

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
    ax_lat.set_ylabel("Latitude of jet maximum (°N)")
    ax_lat.set_ylim(35, 80)
    ax_p.spines["left"].set_visible(False) #remove

    # Right axis: pressure
    ax_p.set_ylabel("Pressure of jet maximum (hPa)")
    ax_p.set_ylim(250, 100)   # inverted
    ax_p.tick_params(axis="y")
    ax_lat.spines["right"].set_visible(False) #remove

    # X axis
    ax_lat.set_xlim(
        pd.Timestamp("2000-01-01"),
        pd.Timestamp("2035-12-31"),
    )

    ax_lat.set_xlabel("Year")
    ax_lat.spines["top"].set_visible(False) #remove
    ax_p.spines["top"].set_visible(False) #remove


    plt.xticks(rotation=30)

    # Title
    ax_lat.set_title("Jet maximum latitude and pressure")

    # Legend
    ax_lat.legend(
        legend_lines,
        legend_labels,
        loc="upper right",
        frameon=False,
    )

    plt.tight_layout()

    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight",
    )


if __name__ == "__main__":
    main()