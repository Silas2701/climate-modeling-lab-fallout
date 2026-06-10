#!/gpfs/data/fs72044/icon17/.venv/bin/python
"""Create the Fallout temperature/wind zonal-mean plot as a PDF.

The script reproduces the notebook logic:
- average temperature, u wind, and v wind over time and longitude
- plot zonal-mean temperature with wind-speed contours
- save the figure to a PDF file

It works with either a single monthly NetCDF file or a glob pattern that
matches multiple monthly files, which lets you generate a month plot or a
yearly mean from all monthly files in that year.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

SEASONS = (
    ("DJF", ((-1, 12), (0, 1), (0, 2))),
    ("MAM", ((0, 3), (0, 4), (0, 5))),
    ("JJA", ((0, 6), (0, 7), (0, 8))),
    ("SON", ((0, 9), (0, 10), (0, 11))),
)


def open_dataset_from_pattern(pattern: str) -> xr.Dataset:
    """Open one NetCDF file or many files matched by a glob pattern."""
    matched_files = sorted(glob.glob(pattern))

    if not matched_files:
        raise FileNotFoundError(f"No files matched pattern: {pattern}")

    if len(matched_files) == 1:
        return xr.open_dataset(matched_files[0])

    return xr.open_mfdataset(matched_files, combine="by_coords")


def subset_dataset_by_time(ds: xr.Dataset, year: int | None, month: list[str] | None) -> xr.Dataset:
    """Subset the dataset to a month or year when requested."""
    if year is not None and month is not None:
        raise ValueError("Use either --year or --month, not both.")

    if year is not None:
        return ds.sel(time=slice(year * 10000 + 101, year * 10000 + 1231))

    if month is not None:
        month_text = "".join(month).strip()
        if len(month_text) == 6 and month_text.isdigit():
            month_text = f"{month_text[:4]}-{month_text[4:6]}"
        if len(month_text) != 7 or month_text[4] != "-":
            raise ValueError("Month must be given as YYYYMM, YYYY-MM, or split as YYYY MM.")
        year_value = int(month_text[:4])
        month_value = int(month_text[5:7])
        start = year_value * 10000 + month_value * 100 + 1
        end = year_value * 10000 + month_value * 100 + 31
        return ds.sel(time=slice(start, end))

    return ds


def select_month_range(ds: xr.Dataset, start_yyyymmdd: int, end_yyyymmdd: int) -> xr.Dataset:
    """Select a numeric YYYYMMDD time range."""
    return ds.sel(time=slice(start_yyyymmdd, end_yyyymmdd))


def select_season_dataset(ds: xr.Dataset, year: int, season: str) -> xr.Dataset:
    """Select the months belonging to one climatological season for a given year."""
    if season == "DJF":
        pieces = [
            select_month_range(ds, (year - 1) * 10000 + 1201, (year - 1) * 10000 + 1231),
            select_month_range(ds, year * 10000 + 101, year * 10000 + 131),
            select_month_range(ds, year * 10000 + 201, year * 10000 + 228),
        ]
    elif season == "MAM":
        pieces = [select_month_range(ds, year * 10000 + 301, year * 10000 + 531)]
    elif season == "JJA":
        pieces = [select_month_range(ds, year * 10000 + 601, year * 10000 + 831)]
    elif season == "SON":
        pieces = [select_month_range(ds, year * 10000 + 901, year * 10000 + 1130)]
    else:
        raise ValueError(f"Unsupported season: {season}")

    season_ds = xr.concat(
        pieces,
        dim="time",
        data_vars="minimal",
        coords="minimal",
        compat="override",
        combine_attrs="drop_conflicts",
    )
    if season_ds.sizes.get("time", 0) == 0:
        raise ValueError(f"No data available for {season} {year}.")
    return season_ds


def mean_over_available_dims(data_array: xr.DataArray, dims: tuple[str, ...]) -> xr.DataArray:
    """Average over each dimension in order when it exists in the data array."""
    reduced = data_array
    for dim in dims:
        if dim in reduced.dims:
            reduced = reduced.mean(dim=dim)
    return reduced


def prepare_zonal_mean_field(data_array: xr.DataArray) -> xr.DataArray:
    """Compute and order the zonal-mean field for plotting."""
    reduced = mean_over_available_dims(data_array, ("time", "lon"))
    plot_dims = [dim for dim in ("height", "lat") if dim in reduced.dims]
    if plot_dims:
        reduced = reduced.transpose(*plot_dims)
    return reduced


def zonal_mean_fields(ds: xr.Dataset) -> tuple[xr.DataArray, xr.DataArray]:
    """Compute temperature and wind-speed zonal means."""
    temp_zonal_mean = prepare_zonal_mean_field(ds["ta"])
    u_zonal_mean = prepare_zonal_mean_field(ds["ua"])
    v_zonal_mean = prepare_zonal_mean_field(ds["va"])

    wind_zonal_mean = np.sqrt(u_zonal_mean**2 + v_zonal_mean**2)
    return temp_zonal_mean, wind_zonal_mean


def normalize_title(title: str) -> str:
    """Expand literal newline escape sequences in a command-line title."""
    return title.replace("\\n", "\n")


def plot_zonal_mean_temperature_with_wind(
    temp_zonal_mean: xr.DataArray,
    wind_zonal_mean: xr.DataArray,
    title: str,
    output_pdf: Path,
) -> None:
    """Create the plot and save it as a PDF."""
    fig, ax = plt.subplots(figsize=(10, 6))

    mesh = ax.pcolormesh(
        temp_zonal_mean["lat"],
        temp_zonal_mean["height"],
        temp_zonal_mean,
        shading="auto",
        cmap="coolwarm",
    )

    contours = ax.contour(
        wind_zonal_mean["lat"],
        wind_zonal_mean["height"],
        wind_zonal_mean,
        colors="black",
        linewidths=0.7,
    )
    ax.clabel(contours, inline=True, fontsize=8, fmt="%.1f")

    ax.invert_yaxis()
    ax.set_xlabel("Latitude")
    ax.set_ylabel("Icon Height Levels")
    ax.set_title(title)
    fig.colorbar(mesh, ax=ax, label="ta (K)")
    fig.tight_layout()
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def plot_seasonal_zonal_mean_temperature_with_wind(
    seasonal_fields: list[tuple[str, xr.DataArray, xr.DataArray]],
    title: str,
    output_pdf: Path,
) -> None:
    """Create a 2x2 seasonal plot and save it as a PDF."""
    temp_stack = np.stack([field.values for _, field, _ in seasonal_fields])
    wind_stack = np.stack([field.values for _, _, field in seasonal_fields])
    temp_min = float(np.nanmin(temp_stack))
    temp_max = float(np.nanmax(temp_stack))
    wind_max = float(np.nanmax(wind_stack))

    contour_levels = np.linspace(0, wind_max, 8)[1:]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    mesh = None

    for axis, (season_name, temp_zonal_mean, wind_zonal_mean) in zip(axes_flat, seasonal_fields):
        height_levels = temp_zonal_mean["height"] - 1
        mesh = axis.pcolormesh(
            temp_zonal_mean["lat"],
            height_levels,
            temp_zonal_mean,
            shading="auto",
            cmap="coolwarm",
            vmin=temp_min,
            vmax=temp_max,
        )

        contours = axis.contour(
            wind_zonal_mean["lat"],
            height_levels,
            wind_zonal_mean,
            levels=contour_levels,
            colors="black",
            linewidths=0.7,
        )
        axis.clabel(contours, inline=True, fontsize=7, fmt="%.1f")
        axis.set_ylim(height_levels.max(), height_levels.min())
        #axis.invert_yaxis()
        axis.set_title(season_name)
        axis.set_xlabel("Latitude")
        axis.set_ylabel("Icon Height Levels")

    if mesh is not None:
        colorbar_axis = fig.add_axes([0.90, 0.18, 0.02, 0.64])
        fig.colorbar(mesh, cax=colorbar_axis, label="ta (K)")
    fig.suptitle(title)
    fig.subplots_adjust(top=0.92, right=0.88)
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the Fallout zonal-mean temperature/wind plot and save it as PDF."
    )
    parser.add_argument(
        "--input-pattern",
        required=True,
        help="Single NetCDF file or glob pattern matching the 3d monthly output files.",
    )
    parser.add_argument(
        "--output-pdf",
        required=True,
        help="Path of the PDF file to write.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Select one year from a multi-month file and plot the mean over that year.",
    )
    parser.add_argument(
        "--annual-mean",
        action="store_true",
        help="When used with --year, plot the mean zonal temperature and wind over the full year instead of the four seasonal panels.",
    )
    parser.add_argument(
        "--month",
        nargs="+",
        default=None,
        help="Select one month in YYYYMM, YYYY-MM, or split as YYYY MM.",
    )
    parser.add_argument(
        "--title",
        default="Zonal mean temperature with zonal mean wind speed contours",
        help="Figure title.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_pdf = Path(args.output_pdf)
    title = normalize_title(args.title)

    ds = open_dataset_from_pattern(args.input_pattern)
    if args.year is not None:
        if args.annual_mean:
            year_ds = subset_dataset_by_time(ds, args.year, None)
            if year_ds.sizes.get("time", 0) == 0:
                raise ValueError("The selected year returned no data. Check the year argument.")
            temp_zonal_mean, wind_zonal_mean = zonal_mean_fields(year_ds)
            plot_zonal_mean_temperature_with_wind(
                temp_zonal_mean=temp_zonal_mean,
                wind_zonal_mean=wind_zonal_mean,
                title=title,
                output_pdf=output_pdf,
            )
            return

        seasonal_fields = []
        for season_name, _ in SEASONS:
            season_ds = select_season_dataset(ds, args.year, season_name)
            temp_zonal_mean, wind_zonal_mean = zonal_mean_fields(season_ds)
            seasonal_fields.append((season_name, temp_zonal_mean, wind_zonal_mean))

        plot_seasonal_zonal_mean_temperature_with_wind(
            seasonal_fields=seasonal_fields,
            title=title,
            output_pdf=output_pdf,
        )
        return

    ds = subset_dataset_by_time(ds, args.year, args.month)
    if ds.sizes.get("time", 0) == 0:
        raise ValueError("The selected time range returned no data. Check the month or year argument.")
    temp_zonal_mean, wind_zonal_mean = zonal_mean_fields(ds)
    plot_zonal_mean_temperature_with_wind(
        temp_zonal_mean=temp_zonal_mean,
        wind_zonal_mean=wind_zonal_mean,
        title=title,
        output_pdf=output_pdf,
    )


if __name__ == "__main__":
    main()