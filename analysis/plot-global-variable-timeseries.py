#!/usr/bin/env python3
"""Plot global mean time series for the fixed reference, 5G2, and 4U10 runs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import xarray as xr

LAT_NAME = "lat"
LON_NAME = "lon"
TIME_NAME = "time"
VERT_NAME = "height"


def build_variable_field(ds: xr.Dataset, variable: str) -> xr.DataArray:
    if variable == "toanet":
        required_vars = ("rsdt", "rsut", "rlut")
        missing_vars = [name for name in required_vars if name not in ds.data_vars]
        if missing_vars:
            raise ValueError(
                "Variable 'toanet' requires rsdt, rsut, and rlut in the dataset. "
                f"Missing variables: {', '.join(missing_vars)}"
            )
        return ds["rsdt"] - ds["rsut"] - ds["rlut"]

    if variable not in ds.data_vars:
        raise ValueError(
            f"Variable '{variable}' not found in dataset. Available variables: {', '.join(ds.data_vars)}"
        )
    return ds[variable]

RUN_FILES = {
    "5G2": {
        "2d": "/gpfs/data/fs72044/icon17/analysis/slab-fallout-g5-2km_2d_200001-204912_remap.nc",
        "3d": "/gpfs/data/fs72044/icon17/analysis/slab-fallout-g5-2km_3d_200001-204912_remap.nc",
    },
    "4U10": {
        "2d": "/gpfs/data/fs72044/icon17/analysis/slab-fallout-u4-10km-2d_200001-204912.nc",
        "3d": "/gpfs/data/fs72044/icon17/analysis/slab-fallout-u4-10km-3d_200001-204912.nc",
    },
}

REFERENCE_FILES = {
    "2d": "/gpfs/data/fs72044/avoigt_teach/experiments/s2026/slabctr/slabctr_atm_2d_ml_1979-2035.remapcon-r360x180.nc",
    "3d": "/gpfs/data/fs72044/icon17/analysis/slabctr_atm_3d_ml_1979-2035_remap.nc",
}

START_DATE = "2000-01-01"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot global mean yearly time series for a chosen variable in the fixed reference, 5G2, and 4U10 runs."
    )
    parser.add_argument(
        "--variable",
        required=True,
        help="Variable name to plot, for example ts, rsdt, ta, or ua.",
    )
    parser.add_argument(
        "--variable-2",
        default=None,
        help="Optional second variable to plot on a secondary y-axis.",
    )
    parser.add_argument(
        "--mode",
        choices=("2d", "3d"),
        required=True,
        help="Select the 2D or 3D file set.",
    )
    parser.add_argument(
        "--output",
        default="global_variable_timeseries.png",
        help="Output image path for the time series plot.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional figure title.",
    )
    parser.add_argument(
        "--start-date",
        default=START_DATE,
        help="Start date for the plot, inclusive.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Optional end year for the plot, inclusive.",
    )
    return parser.parse_args()





def open_dataset(path: str) -> xr.Dataset:
    return xr.open_dataset(path, decode_times=False)


def parse_time_coord(time: xr.DataArray) -> xr.DataArray:
    if np.issubdtype(time.dtype, np.datetime64):
        return time

    units = time.attrs.get("units", "")
    if "%Y%m%d" in units:
        values = np.asarray(time.values, dtype=np.int64)
        strings = np.char.mod("%08d", values)
        dates = pd.to_datetime(strings.astype(str), format="%Y%m%d", utc=False)
        return xr.DataArray(dates, coords=time.coords, dims=time.dims, name=time.name)

    try:
        decoded = xr.decode_cf(xr.Dataset({time.name: time}))[time.name]
        if np.issubdtype(decoded.dtype, np.datetime64):
            return decoded
    except Exception:
        pass

    raise ValueError(
        f"Could not decode time coordinate '{time.name}' with dtype {time.dtype} and units {units}."
    )


def collapse_extra_dims(da: xr.DataArray, keep_dims: set[str]) -> xr.DataArray:
    extra_dims = [dim for dim in da.dims if dim not in keep_dims]
    if extra_dims:
        da = da.mean(dim=extra_dims)
    return da


def drop_incomplete_final_year(da: xr.DataArray, time_name: str) -> xr.DataArray:
    index = pd.DatetimeIndex(da[time_name].values)
    if len(index) == 0:
        return da

    last_year = index[-1].year
    last_year_count = int((index.year == last_year).sum())
    if last_year_count < 12:
        da = da.sel({time_name: index.year < last_year})
    return da


def area_weighted_global_mean(da: xr.DataArray, lat_name: str, lon_name: str) -> xr.DataArray:
    weights = np.cos(np.deg2rad(da[lat_name]))
    da = da.weighted(weights).mean(dim=lat_name)
    da = da.mean(dim=lon_name)
    return da


def annual_month_weighted_mean(da: xr.DataArray, time_name: str) -> xr.DataArray:
    time_index = pd.DatetimeIndex(da[time_name].values)
    month_weights = xr.DataArray(
        time_index.days_in_month.astype(float),
        coords={time_name: da[time_name]},
        dims=(time_name,),
    )

    weighted_sum = (da * month_weights).resample({time_name: "YS"}).sum()
    weight_sum = month_weights.resample({time_name: "YS"}).sum()
    annual_mean = weighted_sum / weight_sum
    annual_mean = annual_mean.where(weight_sum > 0, drop=True)
    return annual_mean


def extract_global_mean_series(path: str, variable: str, start_date: str, end_year: int | None) -> xr.DataArray:
    ds = open_dataset(path)

    lat_name = LAT_NAME
    lon_name = LON_NAME
    time_name = TIME_NAME

    ds = ds.assign_coords({time_name: parse_time_coord(ds[time_name])})

    da = build_variable_field(ds, variable)
    if lat_name not in da.dims or lon_name not in da.dims:
        raise ValueError(
            f"Dataset {path} does not have both latitude and longitude dimensions for variable {variable}. Found dims {da.dims}."
        )

    da = da.sel({time_name: slice(start_date, None)})
    if end_year is not None:
        da = da.sel({time_name: slice(None, f"{end_year}-12-31")})
    da = collapse_extra_dims(da, keep_dims={time_name, lat_name, lon_name})
    da = drop_incomplete_final_year(da, time_name)
    da = area_weighted_global_mean(da, lat_name, lon_name)
    da = annual_month_weighted_mean(da, time_name)
    if variable == "toanet":
        da.attrs["units"] = "W/m²"
    else:
        da.attrs["units"] = ds[variable].attrs.get("units", "")
    return da


def plot_series(
    series_list: Sequence[tuple[str, xr.DataArray]],
    variable: str,
    secondary_series_list: Sequence[tuple[str, xr.DataArray]] | None,
    secondary_variable: str | None,
    output_path: Path,
    title: str | None,
) -> None:
    has_secondary = secondary_series_list is not None and secondary_variable is not None
    # Replace toanet with net radiation for display
    display_variable = "net radiation" if variable == "toanet" else variable
    display_variable_2 = "net radiation" if secondary_variable == "toanet" else secondary_variable
    if has_secondary:
        fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharex=True)
        ax_primary, ax_secondary = axes
    else:
        fig, ax_primary = plt.subplots(figsize=(12, 6))
        ax_secondary = None

    units = next((series.attrs.get("units", "") for _, series in series_list if series.attrs.get("units", "")), "")
    secondary_units = next(
        (series.attrs.get("units", "") for _, series in (secondary_series_list or []) if series.attrs.get("units", "")),
        "",
    )

    primary_lines = []
    for label, series in series_list:
        x = pd.DatetimeIndex(series[series.dims[0]].values)
        line, = ax_primary.plot(x, series.values, label=label)
        primary_lines.append((label, line))

    secondary_lines = []
    if secondary_series_list and ax_secondary and secondary_variable:
        color_map = {label: line.get_color() for label, line in primary_lines}
        for label, series in secondary_series_list:
            x = pd.DatetimeIndex(series[series.dims[0]].values)
            line, = ax_secondary.plot(
                x,
                series.values,
                color=color_map.get(label),
                label=label,
            )
            secondary_lines.append(line)

    if units:
        ax_primary.set_ylabel(f"{display_variable} ({units})", fontsize=13)
    else:
        ax_primary.set_ylabel(f"{display_variable}", fontsize=13)

    ax_primary.set_title(display_variable, fontsize=14)
    ax_primary.legend(loc="upper right")
    ax_primary.xaxis.set_major_locator(mdates.YearLocator(5))
    ax_primary.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_primary.yaxis.set_major_locator(mticker.MaxNLocator(nbins=8))
    ax_primary.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
    ax_primary.tick_params(axis="both", labelsize=11)
    ax_primary.spines["bottom"].set_position(("axes", -0.02))
    ax_primary.spines["left"].set_position(("axes", -0.02))
    ax_primary.set_xlim(left=pd.to_datetime(series_list[0][1][series_list[0][1].dims[0]].values[0]))
    ax_primary.spines["top"].set_visible(False)
    ax_primary.spines["right"].set_visible(False)

    if ax_secondary and secondary_series_list and secondary_variable:
        if secondary_units:
            ax_secondary.set_ylabel(f"{display_variable_2} ({secondary_units})", fontsize=13)
        else:
            ax_secondary.set_ylabel(f"{display_variable_2}", fontsize=13)
        ax_secondary.set_title(display_variable_2, fontsize=14)
        ax_secondary.xaxis.set_major_locator(mdates.YearLocator(5))
        ax_secondary.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax_secondary.yaxis.set_major_locator(mticker.MaxNLocator(nbins=8))
        ax_secondary.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3g"))
        ax_secondary.tick_params(axis="both", labelsize=11)
        ax_secondary.spines["bottom"].set_position(("axes", -0.02))
        ax_secondary.spines["left"].set_position(("axes", -0.02))
        ax_secondary.set_xlim(left=pd.to_datetime(secondary_series_list[0][1][secondary_series_list[0][1].dims[0]].values[0]))
        ax_secondary.spines["top"].set_visible(False)
        ax_secondary.spines["right"].set_visible(False)

    fig.suptitle(title or f"Global yearly mean {variable}" if not has_secondary else (title or "Global yearly means"), fontsize=15)

    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)

    series_list = []
    for label in ("reference", "5G2", "4U10"):
        if label == "reference":
            path = REFERENCE_FILES[args.mode]
        else:
            path = RUN_FILES[label][args.mode]
        series = extract_global_mean_series(path, args.variable, args.start_date, args.end_year)
        series_list.append((label, series))

    secondary_series_list = None
    if args.variable_2:
        secondary_series_list = []
        for label in ("reference", "5G2", "4U10"):
            if label == "reference":
                path = REFERENCE_FILES[args.mode]
            else:
                path = RUN_FILES[label][args.mode]
            series = extract_global_mean_series(path, args.variable_2, args.start_date, args.end_year)
            secondary_series_list.append((label, series))

    plot_series(
        series_list,
        args.variable,
        secondary_series_list,
        args.variable_2,
        output_path,
        args.title,
    )
    if args.variable_2:
        print(f"Saved global mean {args.variable} and {args.variable_2} time series to {output_path}")
    else:
        print(f"Saved global mean {args.variable} time series to {output_path}")


if __name__ == "__main__":
    main()