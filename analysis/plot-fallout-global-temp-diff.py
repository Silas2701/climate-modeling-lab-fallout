#!/gpfs/data/fs72044/icon17/.venv/bin/python
"""Create a global yearly mean surface temperature difference map as a PDF.

The script compares a user-supplied run against the fixed slabctr reference run,
computes the yearly mean tas difference, and plots it on a Robinson projection.

The reference data live in /gpfs/data/fs72044/avoigt_teach/experiments/s2026/
slabctr and are stored as monthly files with the same variables as the user
run.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

REFERENCE_INPUT_PATTERN = "/gpfs/data/fs72044/avoigt_teach/experiments/s2026/slabctr/slabctr_atm_2d_ml_1979-2035.remapcon-r360x180.nc"


def open_dataset_from_pattern(pattern: str) -> xr.Dataset:
    """Open one NetCDF file or many files matched by a glob pattern."""
    matched_files = sorted(glob.glob(pattern))

    if not matched_files:
        raise FileNotFoundError(f"No files matched pattern: {pattern}")

    if len(matched_files) == 1:
        return xr.open_dataset(matched_files[0])

    return xr.open_mfdataset(matched_files, combine="by_coords")


def select_year_dataset(ds: xr.Dataset, year: int) -> xr.Dataset:
    """Select a calendar year from the dataset."""
    return ds.sel(time=slice(year * 10000 + 101, year * 10000 + 1231))


def prepare_temperature_map(ds: xr.Dataset) -> xr.DataArray:
    """Compute the yearly mean surface temperature map from tas."""
    data_array = ds["rlds"] 

    if "time" in data_array.dims:
        data_array = data_array.mean(dim="time")

    plot_dims = [dim for dim in ("lat", "lon") if dim in data_array.dims]
    if plot_dims:
        data_array = data_array.transpose(*plot_dims)

    if not all(dim in data_array.dims for dim in ("lat", "lon")):
        raise ValueError("Temperature data must have lat/lon dimensions after averaging.")

    return data_array


def add_cyclic_longitude(data_array: xr.DataArray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Add a cyclic point in longitude to avoid seams on global map plots."""
    from cartopy.util import add_cyclic_point

    data_cyclic, lon_cyclic = add_cyclic_point(data_array.values, coord=data_array["lon"].values)
    lat_values = data_array["lat"].values
    return data_cyclic, lon_cyclic, lat_values


def plot_robinson_temperature_difference(
    temperature_difference: xr.DataArray,
    title: str,
    output_pdf: Path,
    run_label: str,
    reference_label: str,
) -> None:
    """Plot a global difference map on a Robinson projection and save it as a PDF."""
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError as exc:
        raise ImportError(
            "cartopy is required for this plot. Install cartopy to render the Robinson projection and continent outlines."
        ) from exc

    diff_data, diff_lon, diff_lat = add_cyclic_longitude(temperature_difference)
    diff_limit = float(np.nanmax(np.abs(diff_data)))
    diff_limit = diff_limit if np.isfinite(diff_limit) and diff_limit > 0 else 1.0

    fig, axis = plt.subplots(
        1,
        1,
        figsize=(12, 6.5),
        subplot_kw={"projection": ccrs.Robinson()},
        constrained_layout=True,
    )

    mesh = axis.imshow(
        diff_data,
        transform=ccrs.PlateCarree(),
        origin="lower",
        extent=(float(diff_lon[0]), float(diff_lon[-1]), float(diff_lat[0]), float(diff_lat[-1])),
        cmap="viridis", # RdBu_r for temperature # viridis for radiation difference #bwr_r for sea ice concentration difference
        vmin=-diff_limit,
        vmax=diff_limit,
        interpolation="nearest",
    )
    axis.add_feature(
        cfeature.LAND,
        facecolor="none",
        edgecolor="black",
        linewidth=0.7,
        zorder=3,
    )
    axis.coastlines(linewidth=0.9, color="black", zorder=4)
    axis.set_global()
    axis.set_title(f"{run_label} minus {reference_label}")

    colorbar = fig.colorbar(mesh, ax=axis, orientation="horizontal", fraction=0.05, pad=0.07, extend="both")
    colorbar.set_label("radiation difference (W/m²)") # radiation difference (W/m²) # tas difference (K) # sea ice concentration (1)
    fig.suptitle(title)
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a global yearly mean temperature difference plot and save it as a PDF."
    )
    parser.add_argument(
        "--input-pattern",
        required=True,
        help="Single NetCDF file or glob pattern for the run to compare.",
    )
    parser.add_argument(
        "--output-pdf",
        required=True,
        help="Path of the PDF file to write.",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Calendar year to plot.",
    )
    parser.add_argument(
        "--run-label",
        default="new data",
        help="Label for the user run shown in the title.",
    )
    parser.add_argument(
        "--reference-label",
        default="slabctr reference",
        help="Label for the reference run shown in the title.",
    )
    parser.add_argument(
        "--title",
        default="Global yearly mean temperature difference",
        help="Figure title.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_pdf = Path(args.output_pdf)

    run_dataset = open_dataset_from_pattern(args.input_pattern)
    reference_dataset = open_dataset_from_pattern(REFERENCE_INPUT_PATTERN)

    run_year = select_year_dataset(run_dataset, args.year)
    reference_year = select_year_dataset(reference_dataset, args.year)

    run_temperature = prepare_temperature_map(run_year)
    reference_temperature = prepare_temperature_map(reference_year)
    run_temperature, reference_temperature = xr.align(run_temperature, reference_temperature, join="inner")

    if run_temperature.size == 0 or reference_temperature.size == 0:
        raise ValueError("No overlapping temperature data available after aligning run and reference fields.")

    temperature_difference = run_temperature - reference_temperature

    plot_robinson_temperature_difference(
        temperature_difference=temperature_difference,
        title=f"{args.title} ({args.year})",
        output_pdf=output_pdf,
        run_label=args.run_label,
        reference_label=args.reference_label,
    )


if __name__ == "__main__":
    main()