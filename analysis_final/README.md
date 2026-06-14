# Plotting scripts for fallout comparisons

This directory contains two standalone scripts for the fallout model runs `5G2` and `4U10`. Both scripts use a fixed reference dataset, support the derived variable `toanet`, and work with month-length weighted means.

## Scripts

- `plot-fallout-global-variable-timeseries.py`: plots global mean yearly time series for the reference, `5G2`, and `4U10`, with optional side-by-side plots for a second variable.
- `plot-fallout-global-map-diff.py`: plots global difference maps for a run minus the reference, or both runs side by side with one shared colorbar, with optional significance hatching.

## Requirements

- Python 3.8+ (tested with Python 3.11)
- Python packages: `xarray`, `numpy`, `pandas`, `matplotlib`, `cartopy`, `scipy` for significance testing

Recommended install in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install xarray numpy pandas matplotlib cartopy scipy
```

## Timeseries script

The timeseries script computes a global mean for the selected variable and then aggregates it to yearly means using month-length weighting. It compares the fixed reference, `5G2`, and `4U10`.

Example:

```bash
python plot-fallout-global-variable-timeseries.py \
  --variable toanet \
  --mode 2d \
  --start-date 2000-01-01 \
  --end-year 2035 \
  --output ./toanet_timeseries.png \
  --title "Global mean TOA net radiation"
```

Example with two variables:

```bash
python plot-fallout-global-variable-timeseries.py \
  --variable tas \
  --variable-2 pr \
  --mode 2d \
  --end-year 2035 \
  --output ./tas_pr_timeseries.png \
  --title "Global yearly mean 2m temperature and precipitation"
```

Important options:

- `--variable`: variable to plot. `toanet` is a special alias for `rsdt - rsut - rlut`.
- `--mode`: `2d` or `3d`.
- `--start-date`: first date to include.
- `--end-year`: optional final year to include, inclusive.
- `--variable-2`: optional second variable; when set, the script makes side-by-side panels.
- `--output`: output file name.
- `--title`: optional plot title.

## Map difference script

The map script plots run minus reference on a global map. It can average over a single year or an inclusive multi-year period.

Example, single year:

```bash
python plot-fallout-global-map-diff.py \
  --run 5G2 \
  --variable toanet \
  --mode 2d \
  --year 2000 \
  --output ./toanet_diff_2000.pdf
```

Example, multi-year mean:

```bash
python plot-fallout-global-map-diff.py \
  --run 4U10 \
  --variable tas \
  --mode 3d \
  --year 2000 \
  --end-year 2005 \
  --sig \
  --alpha 0.05 \
  --cmap RdBu_r \
  --output ./tas_diff_2000-2005.pdf
```

Example, both runs side by side:

```bash
python plot-fallout-global-map-diff.py \
  --run both \
  --variable toanet \
  --mode 2d \
  --year 2000 \
  --end-year 2012 \
  --sig \
  --cmap Spectral \
  --output ./toanet_both_2000-2012.pdf
```

Important options:

- `--run`: choose `5G2`, `4U10`, or `both`.
- `--variable`: variable to plot. `toanet` is supported as a derived field.
- `--mode`: `2d` or `3d`.
- `--year` and `--end-year`: choose a single year or an inclusive multi-year period.
- `--sig`: add a significance mask based on a one-sample t-test against zero across yearly samples. In `both` mode, each panel gets its own mask.
- `--alpha`: significance threshold, default `0.05`.
- `--cmap`: colormap for the difference field, default `RdBu_r`.
- `--output`: output file name.

## Averaging and significance

- Monthly data are converted to yearly means with month-length weights so that longer months contribute correctly.
- For multi-year map plots, the data are averaged over the selected year range with month-length weights.
- When `--sig` is enabled, the script performs a one-sample t-test on the yearly run-minus-reference differences and hatches the grid cells where the result is not significant. In `both` mode, the test is run separately for `5G2` and `4U10`.

## Data expectations

- The scripts expect coordinate names `lat`, `lon`, and `time`. The 3D datasets also use `height`.
- The run files are mapped internally from the abbreviations `5G2` and `4U10`.
- The reference file is fixed in the script.

## Troubleshooting

- If `toanet` is requested, the component variables `rsdt`, `rsut`, and `rlut` must be present.
- If `--sig` is used, `scipy` must be installed.
- Use `--help` with either script to see the full command line interface.

