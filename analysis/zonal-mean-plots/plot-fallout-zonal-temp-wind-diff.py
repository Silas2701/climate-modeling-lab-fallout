#!/gpfs/data/fs72044/icon17/.venv/bin/python
"""Create Fallout temperature/wind difference plots as PDFs.

This mirrors the single-run zonal-mean plotter, but compares a user-supplied
run against the fixed slabctr reference run:

The reference data live in /gpfs/data/fs72044/avoigt_teach/experiments/s2026/
slabctr and are stored as monthly files with the same variables as the user
run.
For year plots, the script creates a 2x2 seasonal difference plot
(DJF/MAM/JJA/SON) for the chosen year.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

REFERENCE_INPUT_PATTERN = "/gpfs/data/fs72044/icon17/analysis/slabctr_atm_3d_ml_1979-2035_remap.nc"

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

    # Use explicit options to avoid expensive in-memory comparisons and to
    # ensure dask-backed arrays are created with reasonable chunking. This
    # prevents xarray/dask from attempting to hash/compare huge arrays which
    # can trigger large memory allocations during combine/merge.
    return xr.open_mfdataset(
        matched_files,
        combine="by_coords",
        data_vars="minimal",
        coords="minimal",
        compat="override",
        join="outer",
        chunks={"time": 1},
    )


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
    # Handle cell-based meshes (e.g. 'ncells' with coordinate 'clat') by
    # binning cell latitudes into regular latitude bins and averaging over
    # cells to produce a `lat` dimension suitable for plotting.
    if "ncells" in reduced.dims and "clat" in reduced.coords:
        # Bring the reduced array into memory for grouping — the per-year
        # reduced field is small enough to fit in memory (ncells x height).
        reduced = reduced.compute()
        lat_edges = np.linspace(-90.0, 90.0, 181)  # 1-degree bins
        binned = reduced.groupby_bins(reduced["clat"], lat_edges).mean()
        # groupby_bins creates a new dimension like 'clat_bins'
        # rename it to 'lat' and set bin centers as coordinate values
        bin_centers = 0.5 * (lat_edges[:-1] + lat_edges[1:])
        # find the name of the bin dimension (it ends with '_bins')
        bin_dim = [d for d in binned.dims if d.endswith("_bins")]
        if bin_dim:
            bin_dim = bin_dim[0]
            binned = binned.rename({bin_dim: "lat"})
            binned = binned.assign_coords({"lat": ("lat", bin_centers)})
            reduced = binned
    else:
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


def difference_fields(ds_a: xr.Dataset, ds_b: xr.Dataset) -> tuple[xr.DataArray, xr.DataArray]:
    """Compute run-b minus run-a zonal-mean differences."""
    temp_a, wind_a = zonal_mean_fields(ds_a)
    temp_b, wind_b = zonal_mean_fields(ds_b)
    return temp_b - temp_a, wind_b - wind_a


def plot_zonal_mean_difference(
    temp_difference: xr.DataArray,
    wind_difference: xr.DataArray,
    title: str,
    output_pdf: Path,
) -> None:
    """Create the difference plot and save it as a PDF."""
    fig, ax = plt.subplots(figsize=(10, 6))

    temp_extent = float(np.nanmax(np.abs(temp_difference.values)))
    wind_extent = float(np.nanmax(np.abs(wind_difference.values)))
    temp_limit = temp_extent if np.isfinite(temp_extent) and temp_extent > 0 else 1.0
    wind_limit = wind_extent if np.isfinite(wind_extent) and wind_extent > 0 else 1.0

    # Trim to latitudes that actually contain data so a narrow regional
    # reference (e.g. slabctr near the equator) doesn't plot as a single
    # vertical line on a global latitude axis.
    lat_vals = temp_difference["lat"].values
    valid_mask = (
        np.any(np.isfinite(temp_difference.values), axis=0)
        | np.any(np.isfinite(wind_difference.values), axis=0)
    )
    if valid_mask.sum() == 0:
        raise ValueError("No valid data to plot after trimming latitude range.")
    if valid_mask.sum() < valid_mask.size:
        lat_vals = lat_vals[valid_mask]
        temp_difference = temp_difference.sel(lat=lat_vals)
        wind_difference = wind_difference.sel(lat=lat_vals)

    mesh = ax.pcolormesh(
        temp_difference["lat"],
        temp_difference["height"],
        temp_difference,
        shading="auto",
        cmap="RdBu_r",
        vmin=-temp_limit,
        vmax=temp_limit,
    )

    contour_levels = np.linspace(-wind_limit, wind_limit, 9)
    contour_levels = contour_levels[np.abs(contour_levels) > 0]
    contours = ax.contour(
        wind_difference["lat"],
        wind_difference["height"],
        wind_difference,
        levels=contour_levels,
        colors="black",
        linewidths=0.7,
    )
    ax.clabel(contours, inline=True, fontsize=8, fmt="%.1f")

    ax.invert_yaxis()
    ax.set_xlabel("Latitude")
    ax.set_ylabel("Icon Height Levels")
    ax.set_title(title)
    fig.colorbar(mesh, ax=ax, label="ta difference (K)")
    fig.tight_layout()
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def plot_seasonal_zonal_mean_difference(
    seasonal_fields: list[tuple[str, xr.DataArray, xr.DataArray]],
    title: str,
    output_pdf: Path,
) -> None:
    """Create a 2x2 seasonal difference plot and save it as a PDF."""
    temp_stack = np.stack([field.values for _, field, _ in seasonal_fields])
    wind_stack = np.stack([field.values for _, _, field in seasonal_fields])
    temp_extent = float(np.nanmax(np.abs(temp_stack)))
    wind_extent = float(np.nanmax(np.abs(wind_stack)))
    temp_limit = temp_extent if np.isfinite(temp_extent) and temp_extent > 0 else 1.0
    wind_limit = wind_extent if np.isfinite(wind_extent) and wind_extent > 0 else 1.0

    contour_levels = np.linspace(-wind_limit, wind_limit, 9)
    contour_levels = contour_levels[np.abs(contour_levels) > 0]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    mesh = None

    # Determine union of latitudes that contain data across all seasons so
    # the 2x2 plot zooms to the region with actual values.
    all_lat_masks = []
    for _, temp_difference, wind_difference in seasonal_fields:
        mask = (
            np.any(np.isfinite(temp_difference.values), axis=0)
            | np.any(np.isfinite(wind_difference.values), axis=0)
        )
        all_lat_masks.append(mask)
    # Align masks to the latitude coordinate of the first seasonal field
    ref_lat = seasonal_fields[0][1]["lat"].values
    union_mask = np.zeros_like(ref_lat, dtype=bool)
    for mask in all_lat_masks:
        # If mask length differs, attempt to align by coordinate labels; else assume same
        if mask.size == union_mask.size:
            union_mask |= mask
        else:
            # fallback: mark any lat that appears finite in the data arrays
            # by interpolating mask indices to ref_lat where possible
            union_mask |= np.any(~np.isnan(seasonal_fields[0][1].values), axis=0)

    if not union_mask.any():
        raise ValueError("No valid latitude data found for seasonal plots.")

    selected_lats = ref_lat[union_mask]

    for axis, (season_name, temp_difference, wind_difference) in zip(axes_flat, seasonal_fields):
        # Subset each seasonal field to the selected latitudes (if present)
        if "lat" in temp_difference.dims and temp_difference["lat"].size != selected_lats.size:
            temp_difference = temp_difference.sel(lat=selected_lats, method="nearest")
        if "lat" in wind_difference.dims and wind_difference["lat"].size != selected_lats.size:
            wind_difference = wind_difference.sel(lat=selected_lats, method="nearest")

        height_levels = temp_difference["height"] - 1
        mesh = axis.pcolormesh(
            temp_difference["lat"],
            height_levels,
            temp_difference,
            shading="auto",
            cmap="RdBu_r",
            vmin=-temp_limit,
            vmax=temp_limit,
        )

        contours = axis.contour(
            wind_difference["lat"],
            height_levels,
            wind_difference,
            levels=contour_levels,
            colors="black",
            linewidths=0.7,
        )
        axis.clabel(contours, inline=True, fontsize=7, fmt="%.1f")
        axis.set_ylim(height_levels.max(), height_levels.min())
        axis.set_title(season_name)
        axis.set_xlabel("Latitude")
        axis.set_ylabel("Icon Height Levels")

    if mesh is not None:
        colorbar_axis = fig.add_axes([0.90, 0.18, 0.02, 0.64])
        fig.colorbar(mesh, cax=colorbar_axis, label="ta difference (K)")
    fig.suptitle(title)
    fig.subplots_adjust(top=0.92, right=0.88)
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def build_comparison_title(base_title: str, label_run: str | None) -> str:
    """Create a readable title for the comparison plot."""
    if label_run:
        return f"{base_title} ({label_run} - slabctr reference)"
    return f"{base_title} (run - slabctr reference)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Fallout zonal-mean temperature/wind difference plots against the fixed slabctr reference run and save them as PDF."
    )
    parser.add_argument(
        "--input-pattern",
        required=True,
        help="Single NetCDF file or glob pattern for the run to compare against the fixed reference.",
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
        help="Select one year from multi-month files and plot seasonal (DJF/MAM/JJA/SON) differences for that year.",
    )
    parser.add_argument(
        "--month",
        nargs="+",
        default=None,
        help="Select one month in YYYYMM, YYYY-MM, or split as YYYY MM.",
    )
    parser.add_argument(
        "--title",
        default="Zonal mean temperature difference with zonal mean wind speed difference contours",
        help="Figure title.",
    )
    parser.add_argument(
        "--label-run",
        default=None,
        help="Optional label for the user run to show in the title.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_pdf = Path(args.output_pdf)

    ds_run = open_dataset_from_pattern(args.input_pattern)
    ds_reference = open_dataset_from_pattern(REFERENCE_INPUT_PATTERN)

    if args.year is not None:
        seasonal_fields = []
        for season_name, _ in SEASONS:
            season_ds_run = select_season_dataset(ds_run, args.year, season_name)
            season_ds_reference = select_season_dataset(ds_reference, args.year, season_name)
            temp_difference, wind_difference = difference_fields(season_ds_reference, season_ds_run)
            seasonal_fields.append((season_name, temp_difference, wind_difference))

        plot_seasonal_zonal_mean_difference(
            seasonal_fields=seasonal_fields,
            title=build_comparison_title(args.title, args.label_run),
            output_pdf=output_pdf,
        )
        return

    ds_run = subset_dataset_by_time(ds_run, args.year, args.month)
    ds_reference = subset_dataset_by_time(ds_reference, args.year, args.month)
    if ds_run.sizes.get("time", 0) == 0 or ds_reference.sizes.get("time", 0) == 0:
        raise ValueError("The selected time range returned no data. Check the month or year argument.")
    temp_difference, wind_difference = difference_fields(ds_reference, ds_run)
    plot_zonal_mean_difference(
        temp_difference=temp_difference,
        wind_difference=wind_difference,
        title=build_comparison_title(args.title, args.label_run),
        output_pdf=output_pdf,
    )


if __name__ == "__main__":
    main()