#!/usr/bin/env python3
"""Plot a global difference map to the fixed reference run."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

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

LAT_NAME = "lat"
LON_NAME = "lon"
TIME_NAME = "time"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a global difference map for 5G2 or 4U10 against the fixed reference run."
    )
    parser.add_argument(
        "--run",
        choices=("5G2", "4U10", "both"),
        required=True,
        help="Run abbreviation to compare against the reference, or 'both' to plot 5G2 and 4U10 side by side.",
    )
    parser.add_argument(
        "--variable",
        required=True,
        help="NetCDF variable to plot.",
    )
    parser.add_argument(
        "--mode",
        choices=("2d", "3d"),
        default="2d",
        help="Select the 2D or 3D file set.",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Start year to plot.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Optional end year for a multi-year mean. Defaults to --year.",
    )
    parser.add_argument(
        "--output",
        default="global_variable_diff.pdf",
        help="Output PDF path.",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Optional label for the run in the title.",
    )
    parser.add_argument(
        "--reference-label",
        default="slabctr reference",
        help="Label for the reference run in the title.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional figure title.",
    )
    parser.add_argument(
        "--sig",
        action="store_true",
        help="Perform a t-test across yearly samples and overlay significance (popmean=0).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold for the t-test (default: 0.05).",
    )
    parser.add_argument(
        "--cmap",
        default="RdBu_r",
        help="Colormap name for the difference plot (default: RdBu_r).",
    )
    return parser.parse_args()


def find_coord_name(ds: xr.Dataset, candidates: Sequence[str]) -> str:
    for name in candidates:
        if name in ds.coords:
            return name
    for name in candidates:
        if name in ds.dims:
            return name
    raise ValueError(f"Could not find a coordinate from {candidates}. Available coords: {', '.join(ds.coords)}")


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


def period_month_weighted_mean(
    da: xr.DataArray,
    time_name: str,
    start_year: int,
    end_year: int,
) -> xr.DataArray:
    time_slice = slice(f"{start_year}-01-01", f"{end_year}-12-31")
    da = da.sel({time_name: time_slice})
    if time_name not in da.dims:
        return da

    time_index = pd.DatetimeIndex(da[time_name].values)
    month_weights = xr.DataArray(
        time_index.days_in_month.astype(float),
        coords={time_name: da[time_name]},
        dims=(time_name,),
    )

    weighted_sum = (da * month_weights).sum(dim=time_name)
    weight_sum = month_weights.sum(dim=time_name)
    return weighted_sum / weight_sum


def prepare_map_field(ds: xr.Dataset, variable: str, start_year: int, end_year: int) -> xr.DataArray:
    lat_name = LAT_NAME
    lon_name = LON_NAME
    time_name = TIME_NAME

    ds = ds.assign_coords({time_name: parse_time_coord(ds[time_name])})
    da = build_variable_field(ds, variable)

    if lat_name not in da.dims or lon_name not in da.dims:
        raise ValueError(
            f"Variable {variable} does not have both latitude and longitude dimensions. Found dims {da.dims}."
        )

    da = period_month_weighted_mean(da, time_name, start_year, end_year)
    da = collapse_extra_dims(da, keep_dims={lat_name, lon_name})
    da = da.transpose(lat_name, lon_name)
    return da


def prepare_annual_series(ds: xr.Dataset, variable: str, start_year: int, end_year: int) -> xr.DataArray:
    """Return annual month-weighted means across the inclusive year range as a DataArray with a time dim."""
    lat_name = LAT_NAME
    lon_name = LON_NAME
    time_name = TIME_NAME

    ds = ds.assign_coords({time_name: parse_time_coord(ds[time_name])})
    da = build_variable_field(ds, variable)
    if time_name not in da.dims:
        raise ValueError("Data does not contain a time dimension for annual series calculation.")

    annual = annual_month_weighted_mean(da, time_name)
    # select the inclusive year range
    start = f"{start_year}-01-01"
    end = f"{end_year}-12-31"
    annual = annual.sel({time_name: slice(start, end)})
    # Collapse other dims (e.g., vertical) but keep lat/lon
    annual = collapse_extra_dims(annual, keep_dims={lat_name, lon_name, time_name})
    # Ensure ordering time, lat, lon
    annual = annual.transpose(time_name, lat_name, lon_name)
    return annual


def add_cyclic_longitude(data_array: xr.DataArray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from cartopy.util import add_cyclic_point

    data_cyclic, lon_cyclic = add_cyclic_point(data_array.values, coord=data_array["lon"].values)
    lat_values = data_array["lat"].values
    return data_cyclic, lon_cyclic, lat_values


def plot_difference_map(
    diff_field: xr.DataArray,
    title: str,
    output_pdf: Path,
    run_label: str,
    reference_label: str,
    variable: str,
    cmap: str = "RdBu_r",
    sig_mask: Optional[xr.DataArray] = None,
) -> None:
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError as exc:
        raise ImportError(
            "cartopy is required for this plot. Install cartopy to render the Robinson projection and coastlines."
        ) from exc

    diff_data, diff_lon, diff_lat = add_cyclic_longitude(diff_field)
    diff_limit = float(np.nanmax(np.abs(diff_data)))
    diff_limit = diff_limit if np.isfinite(diff_limit) and diff_limit > 0 else 1.0
    units = diff_field.attrs.get("units", "")

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
        cmap=cmap,
        vmin=-diff_limit,
        vmax=diff_limit,
        interpolation="nearest",
    )
    axis.add_feature(cfeature.LAND, facecolor="none", edgecolor="black", linewidth=0.7, zorder=3)
    axis.coastlines(linewidth=0.9, color="black", zorder=4)
    axis.set_global()
    axis.set_title(f"{run_label} minus {reference_label}")

    colorbar = fig.colorbar(mesh, ax=axis, orientation="horizontal", fraction=0.05, pad=0.07, extend="both")
    if units:
        colorbar.set_label(f"{variable} difference ({units})")
    else:
        colorbar.set_label(f"{variable} difference")
    fig.suptitle(title)
    # Overlay significance hatching if provided
    if sig_mask is not None:
        try:
            import cartopy.crs as ccrs  # noqa: F401
        except Exception:
            pass

        # Convert sig_mask to cyclic and plot hatching where True
        sig_cyclic, sig_lon, sig_lat = add_cyclic_longitude(sig_mask.astype(float))
        lon2d, lat2d = np.meshgrid(sig_lon, sig_lat)
        # contourf with hatching; colors='none' keeps underlying colormap
        axis.contourf(
            lon2d,
            lat2d,
            sig_cyclic,
            levels=[0.5, 1.5],
            transform=ccrs.PlateCarree(),
            hatches=["...."],
            colors="none",
            zorder=6,
        )

    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def plot_difference_maps_side_by_side(
    diff_field_1: xr.DataArray,
    diff_field_2: xr.DataArray,
    run_label_1: str,
    run_label_2: str,
    reference_label: str,
    title: str,
    output_pdf: Path,
    variable: str,
    cmap: str = "RdBu_r",
    sig_mask_1: Optional[xr.DataArray] = None,
    sig_mask_2: Optional[xr.DataArray] = None,
) -> None:
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError as exc:
        raise ImportError(
            "cartopy is required for this plot. Install cartopy to render the Robinson projection and coastlines."
        ) from exc

    # Prepare data for both fields
    diff_data_1, diff_lon_1, diff_lat_1 = add_cyclic_longitude(diff_field_1)
    diff_data_2, diff_lon_2, diff_lat_2 = add_cyclic_longitude(diff_field_2)

    # Compute shared limits based on both fields
    diff_limit = float(np.nanmax(np.abs([np.nanmax(np.abs(diff_data_1)), np.nanmax(np.abs(diff_data_2))])))
    diff_limit = diff_limit if np.isfinite(diff_limit) and diff_limit > 0 else 1.0
    units = diff_field_1.attrs.get("units", "")

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(18, 6.5),
        subplot_kw={"projection": ccrs.Robinson()},
        constrained_layout=True,
    )

    # Plot first difference map
    mesh1 = axes[0].imshow(
        diff_data_1,
        transform=ccrs.PlateCarree(),
        origin="lower",
        extent=(float(diff_lon_1[0]), float(diff_lon_1[-1]), float(diff_lat_1[0]), float(diff_lat_1[-1])),
        cmap=cmap,
        vmin=-diff_limit,
        vmax=diff_limit,
        interpolation="nearest",
    )
    axes[0].add_feature(cfeature.LAND, facecolor="none", edgecolor="black", linewidth=0.7, zorder=3)
    axes[0].coastlines(linewidth=0.9, color="black", zorder=4)
    axes[0].set_global()
    axes[0].set_title(f"{run_label_1} minus {reference_label}")

    # Overlay significance hatching on first map if provided
    if sig_mask_1 is not None:
        try:
            import cartopy.crs as ccrs  # noqa: F401
        except Exception:
            pass
        sig_cyclic_1, sig_lon_1, sig_lat_1 = add_cyclic_longitude(sig_mask_1.astype(float))
        lon2d_1, lat2d_1 = np.meshgrid(sig_lon_1, sig_lat_1)
        axes[0].contourf(
            lon2d_1,
            lat2d_1,
            sig_cyclic_1,
            levels=[0.5, 1.5],
            transform=ccrs.PlateCarree(),
            hatches=["...."],
            colors="none",
            zorder=6,
        )

    # Plot second difference map
    mesh2 = axes[1].imshow(
        diff_data_2,
        transform=ccrs.PlateCarree(),
        origin="lower",
        extent=(float(diff_lon_2[0]), float(diff_lon_2[-1]), float(diff_lat_2[0]), float(diff_lat_2[-1])),
        cmap=cmap,
        vmin=-diff_limit,
        vmax=diff_limit,
        interpolation="nearest",
    )
    axes[1].add_feature(cfeature.LAND, facecolor="none", edgecolor="black", linewidth=0.7, zorder=3)
    axes[1].coastlines(linewidth=0.9, color="black", zorder=4)
    axes[1].set_global()
    axes[1].set_title(f"{run_label_2} minus {reference_label}")

    # Overlay significance hatching on second map if provided
    if sig_mask_2 is not None:
        try:
            import cartopy.crs as ccrs  # noqa: F401
        except Exception:
            pass
        sig_cyclic_2, sig_lon_2, sig_lat_2 = add_cyclic_longitude(sig_mask_2.astype(float))
        lon2d_2, lat2d_2 = np.meshgrid(sig_lon_2, sig_lat_2)
        axes[1].contourf(
            lon2d_2,
            lat2d_2,
            sig_cyclic_2,
            levels=[0.5, 1.5],
            transform=ccrs.PlateCarree(),
            hatches=["...."],
            colors="none",
            zorder=6,
        )

    # Add shared colorbar
    colorbar = fig.colorbar(mesh1, ax=axes, orientation="horizontal", fraction=0.04, pad=0.07, extend="both")
    if units:
        colorbar.set_label(f"{variable} difference ({units})")
    else:
        colorbar.set_label(f"{variable} difference")

    fig.suptitle(title)
    fig.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_pdf = Path(args.output)
    end_year = args.end_year if args.end_year is not None else args.year
    if end_year < args.year:
        raise ValueError("--end-year must be greater than or equal to --year.")

    reference_path = REFERENCE_FILES[args.mode]
    reference_dataset = open_dataset(reference_path)
    reference_field = prepare_map_field(reference_dataset, args.variable, args.year, end_year)

    # Handle "both" mode separately
    if args.run == "both":
        run_5g2_path = RUN_FILES["5G2"][args.mode]
        run_4u10_path = RUN_FILES["4U10"][args.mode]
        run_5g2_dataset = open_dataset(run_5g2_path)
        run_4u10_dataset = open_dataset(run_4u10_path)

        run_5g2_field = prepare_map_field(run_5g2_dataset, args.variable, args.year, end_year)
        run_4u10_field = prepare_map_field(run_4u10_dataset, args.variable, args.year, end_year)

        run_5g2_field, reference_field = xr.align(run_5g2_field, reference_field, join="inner")
        run_4u10_field, reference_field = xr.align(run_4u10_field, reference_field, join="inner")

        if run_5g2_field.size == 0 or run_4u10_field.size == 0 or reference_field.size == 0:
            raise ValueError("No overlapping data available after aligning run and reference fields.")

        diff_5g2 = run_5g2_field - reference_field
        diff_4u10 = run_4u10_field - reference_field

        if args.variable == "toanet":
            diff_5g2.attrs["units"] = "W/m²"
            diff_4u10.attrs["units"] = "W/m²"
        else:
            diff_5g2.attrs["units"] = run_5g2_dataset[args.variable].attrs.get("units", "")
            diff_4u10.attrs["units"] = run_4u10_dataset[args.variable].attrs.get("units", "")

        if args.year == end_year:
            period_label = f"{args.year}"
        else:
            period_label = f"{args.year}-{end_year}"
        title = args.title or f"Global mean {args.variable} difference ({period_label})"

        sig_mask_5g2 = None
        sig_mask_4u10 = None
        if args.sig:
            try:
                import scipy.stats as stats
            except Exception as exc:  # pragma: no cover
                raise ImportError("scipy is required for significance testing. Install scipy to use --sig.") from exc

            # Build and compute significance for 5G2
            run_5g2_annual = prepare_annual_series(run_5g2_dataset, args.variable, args.year, end_year)
            ref_annual_5g2 = prepare_annual_series(reference_dataset, args.variable, args.year, end_year)
            run_5g2_annual, ref_annual_5g2 = xr.align(run_5g2_annual, ref_annual_5g2, join="inner")
            if run_5g2_annual.sizes.get(TIME_NAME, 0) < 2:
                raise ValueError("Not enough years available for t-test. Need at least two years.")
            diff_annual_5g2 = run_5g2_annual - ref_annual_5g2
            tstat_5g2, pvals_5g2 = stats.ttest_1samp(diff_annual_5g2.values, popmean=0.0, axis=0, nan_policy="omit")
            sig_bool_5g2 = (pvals_5g2 < args.alpha)
            non_sig_5g2 = (~sig_bool_5g2) | np.isnan(pvals_5g2)
            sig_mask_5g2 = xr.DataArray(non_sig_5g2.astype(float), coords={LAT_NAME: diff_annual_5g2[LAT_NAME].values, LON_NAME: diff_annual_5g2[LON_NAME].values}, dims=(LAT_NAME, LON_NAME))

            # Build and compute significance for 4U10
            run_4u10_annual = prepare_annual_series(run_4u10_dataset, args.variable, args.year, end_year)
            ref_annual_4u10 = prepare_annual_series(reference_dataset, args.variable, args.year, end_year)
            run_4u10_annual, ref_annual_4u10 = xr.align(run_4u10_annual, ref_annual_4u10, join="inner")
            if run_4u10_annual.sizes.get(TIME_NAME, 0) < 2:
                raise ValueError("Not enough years available for t-test. Need at least two years.")
            diff_annual_4u10 = run_4u10_annual - ref_annual_4u10
            tstat_4u10, pvals_4u10 = stats.ttest_1samp(diff_annual_4u10.values, popmean=0.0, axis=0, nan_policy="omit")
            sig_bool_4u10 = (pvals_4u10 < args.alpha)
            non_sig_4u10 = (~sig_bool_4u10) | np.isnan(pvals_4u10)
            sig_mask_4u10 = xr.DataArray(non_sig_4u10.astype(float), coords={LAT_NAME: diff_annual_4u10[LAT_NAME].values, LON_NAME: diff_annual_4u10[LON_NAME].values}, dims=(LAT_NAME, LON_NAME))

        plot_difference_maps_side_by_side(
            diff_field_1=diff_5g2,
            diff_field_2=diff_4u10,
            run_label_1="5G2",
            run_label_2="4U10",
            reference_label=args.reference_label,
            title=title,
            output_pdf=output_pdf,
            variable=args.variable,
            cmap=args.cmap,
            sig_mask_1=sig_mask_5g2,
            sig_mask_2=sig_mask_4u10,
        )
        print(f"Saved side-by-side difference map to {output_pdf}")
        return

    # Single run mode
    run_path = RUN_FILES[args.run][args.mode]
    run_dataset = open_dataset(run_path)

    run_field = prepare_map_field(run_dataset, args.variable, args.year, end_year)
    run_field, reference_field = xr.align(run_field, reference_field, join="inner")

    if run_field.size == 0 or reference_field.size == 0:
        raise ValueError("No overlapping data available after aligning run and reference fields.")

    diff_field = run_field - reference_field
    if args.variable == "toanet":
        diff_field.attrs["units"] = "W/m²"
    else:
        diff_field.attrs["units"] = run_dataset[args.variable].attrs.get("units", "")

    run_label = args.run_label or args.run
    if args.year == end_year:
        period_label = f"{args.year}"
    else:
        period_label = f"{args.year}-{end_year}"
    title = args.title or f"Global mean {args.variable} difference ({period_label})"

    sig_mask = None
    if args.sig:
        try:
            import scipy.stats as stats
        except Exception as exc:  # pragma: no cover - informative error
            raise ImportError("scipy is required for significance testing. Install scipy to use --sig.") from exc

        # build annual series for both datasets and compute per-year differences
        run_annual = prepare_annual_series(run_dataset, args.variable, args.year, end_year)
        ref_annual = prepare_annual_series(reference_dataset, args.variable, args.year, end_year)
        # align annual series
        run_annual, ref_annual = xr.align(run_annual, ref_annual, join="inner")
        if run_annual.sizes.get(TIME_NAME, 0) < 2:
            raise ValueError("Not enough years available to perform a t-test. Need at least two years in the selected period.")

        diff_annual = run_annual - ref_annual
        # perform t-test along the time axis (popmean=0)
        tstat, pvals = stats.ttest_1samp(diff_annual.values, popmean=0.0, axis=0, nan_policy="omit")

        # pvals shape should match lat x lon; create DataArray with coords
        sig_bool = (pvals < args.alpha)
        # hatch where NOT significant (including NaNs)
        non_sig = (~sig_bool) | np.isnan(pvals)
        sig_mask = xr.DataArray(non_sig.astype(float), coords={LAT_NAME: diff_annual[LAT_NAME].values, LON_NAME: diff_annual[LON_NAME].values}, dims=(LAT_NAME, LON_NAME))

    plot_difference_map(
        diff_field=diff_field,
        title=title,
        output_pdf=output_pdf,
        run_label=run_label,
        reference_label=args.reference_label,
        variable=args.variable,
        cmap=args.cmap,
        sig_mask=sig_mask,
    )
    print(f"Saved difference map to {output_pdf}")


if __name__ == "__main__":
    main()