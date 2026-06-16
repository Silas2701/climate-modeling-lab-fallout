# 📦 climate-modeling-lab-fallout

This project attempts to simulate the consequences of a nuclear conflict by injecting an amount of Black Carbon (BC) into the lower stratosphere. The BC results from the combustion of the fires that are ignited after the explosions.

------------------------------------------------------------------------

## 📂 Project Structure

The repository is divided into the following directories:

- **analysis**: scripts for analysing the simulation output and generating plots for the paper.
- **config**: includes a configuration file for defining characteristics of the black carbon layer and the aerosol modifications. More information in the [⚙️ Configuration](#️-configuration) section.
- **preprocessing**: python scripts for creating the modified aerosol files.
- **runscripts**: contains the runscript for submitting and executing the simulation run.

------------------------------------------------------------------------

## 🛠️ Getting Started

### Prerequisites

In order to run this project you need to have access to the **Vienna Scientific Cluster 4** (VSC4) HPC platform and an VSC account. Secondly, a compiled version of the **ICON-ESM** must be available.

### Cloning the repo

Head to your personal user space located under `$DATA` and clone the repository:

```bash
cd $DATA

git clone https://github.com/Silas2701/climate-modeling-lab-fallout.git
cd climate-modeling-lab-fallout
```

### Preprocessing

Next, stratospheric aerosol data need to be perturbed to simulate a black carbon layer in the lower stratosphere.
A simple shell script `./preprocessing/preprocess.sh` facilitates the preprocessing step and creates modified aerosol files.
Before execution, you will want to make sure to have a look at `./config/config.toml` which controls how the black carbon layer is constructed and how black carbon decays over time. Feel free to adjust it to your needs.
For specific configuration setup of our simulation runs have a look at the [⚙️ Configuration](#️-configuration) section.

The script can then be invoked in the following way:

```bash
bash ./preprocessing/preprocessing.sh --start-year 2000 --end-year 2050  --input-data-dir /gpfs/data/fs72044/avoigt_teach/msc-climodlab-s2026/mscmet-climmodlab-s2023/ICON-inputdata/amip-VSC4  --output-data-dir <output-data-dir>
```

Important options:

- `--start-year`: The start year of the simulation.
- `--end-year`: The end year of the simulation (inclusive).
- `--input-data-dir`: The directory where the input data is stored that we would like to modify.
- `--output-data-dir`: Optional output directory for the modified input data (default is the current working directory of the script execution).
- `--config-file`: Optional path to the TOML config file used for modification (default `./config/config.toml`).

**Important note:** `--start-year` is expected to match the year that is mentioned in the `initial_date` variable of the `./runscripts/exp.slabctr.run` runscript. `--end-year` is supposed to align with the year expressed in the `final_date` variable in the same runscript.

After execution you will observe that the modified aerosol files have been saved to the directory specified by the `--output-data-dir` argument.

### Runscript execution

Before submitting the slab-ocean simulation, we need to ensure that the runscript finds our modified aerosol files and that the experiment output is written to the correct directoy. Therefore, head to the runscript `./runscripts/exp.slabctr.run` and edit and replace the following lines where \<tag\> placeholders have been inserted.

``` bash
#SBATCH --output=/gpfs/data/fs72044/<icon-XY>/climate-modeling-lab-fallout/runs/slabctr/LOG.exp.slabctr.run.%j.o
#SBATCH --error=/gpfs/data/fs72044/<icon-XY>/climate-modeling-lab-fallout/runs/slabctr/LOG.exp.slabctr.run.%j.o
##SBATCH --mail-user=<your-email>
...


...

ICONFOLDER=/gpfs/data/fs72044/<icon-XY>/icon-esm-univie/build.vsc4.intel-intelmpi_spack    
RUNSCRIPTDIR=/gpfs/data/fs72044/<icon-XY>/runs/${EXP}

...

EXPDIR=/gpfs/data/fs72044/<icon-XY>/experiments/s2026/${EXP}

...

modified_aerosols_dir=<path-to-your-modified-aerosols-data> # This should match the --output-data-dir argument, provided to the prior execution of the preprocessing script.
```

Of course you can also change the experiment name and directory etc.. The above just shows the absolute minimum that needs to be adjusted to ensure successful execution of the simulation with our modified aerosol files.

Afterwards, it is time to submit the simulation:

```bash
sbatch exp.amip.run
```

We can view information about our jobs using the following command:

```bash
squeue -u $USER
```

------------------------------------------------------------------------

## ⚙️ Configuration

The configuration file at `./config/config.toml` allows you to adjust the parameters for the modification of the aerosol files.  
We will give a brief overview of the available parameters for the `[aerosol]` table which controls the aerosol modification.

- **bc_layer_width_levels**: The width of the black carbon layer, expressed in levels (1 level ≙ 0.5km).
- **bc_layer_distribution**: The distribution in the black carbon layer. `uniform` will apply equal concentration of black carbon anywhere in the black carbon layer, `guassian` will result in a gaussian distribution in the vertical to have lower concentration at the upper and lower bounds and higher concentration around the center.
- **bc_mass**: The total black carbon mass emitted, measured in g.
- **bc_mass_ext_coeff**: The presumed mass extinction coefficient of black carbon, measured in m^2/kg.
- **bc_e_folding_time**: Black carbon e-folding time, measured in years.
- **bc_ssa**: The single scattering albedo of black carbon. This attribute can take any value in the range between 0 and 1. 0 means purely absorbing and 1 is purely scattering.

### Simulations

We have focussed on two simulations for the black carbon band that we injected at the lower stratosphere. To be able to reproduce our results the configuration setups for the modification of the aerosol files are presented below.

1. Black carbon band of 10km width, 4 Tg of black carbon and uniform distribution:

```toml
[aerosol]
bc_layer_width_levels = 20
bc_layer_distribution = "uniform"
bc_mass = 4.0e12
bc_mass_ext_coeff = 9.0
bc_e_folding_time = 5.5
bc_ssa = 0.31
```

2. Black carbon band of 2km width, 5 Tg of black carbon and gaussian distribution:
   
```toml
[aerosol]
bc_layer_width_levels = 4
bc_layer_distribution = "gaussian"
bc_mass = 5.0e12
bc_mass_ext_coeff = 9.0
bc_e_folding_time = 5.5
bc_ssa = 0.31
```

------------------------------------------------------------------------

## 🔄 Postprocessing

To facilitate plotting, we first merge all 2D/3D outputs into a single NetCDF file, using CDO.
Therefore, move to the directory where the experiment output is written to (it is the directory specified as `EXPDIR` in the runscript) and load the cdo module.

```bash
cd <EXPDIR> # Move to the EXPDIR 
module load cdo # Load CDO module

cdo -mergetime slabctr_atm_2d_ml_*.nc slabctr_atm_2d_ml_ALL.nc # For 2D output

cdo -mergetime slabctr_atm_3d_ml_*.nc slabctr_atm_3d_ml_ALL.nc # For 3D output
```

Furthermore we also need to remap the grid from cell-grid to lat-lon-grid which will later then be processed in our plot scripts:

```bash
cdo remapcon,r360x180 slabctr_atm_2d_ml_ALL.nc slabctr_atm_2d_ml_ALL.r360x180.nc # For 2D output

cdo remapcon,r360x180 slabctr_atm_3d_ml_ALL.nc slabctr_atm_3d_ml_ALL.r360x180.nc # For 2D output
```

The postprocessed files are used in the plot scripts in the `./analysis` directory where they are provided as static references inside the script. If you want to plot your own runs, e.g. for global variable time series in the [plot-global-variable-timeseries.py](./analysis/plot-global-variable-timeseries.py) you can modify the `RUN_FILES` constant and replace the paths with the 2D and 3D remapped output.

------------------------------------------------------------------------

## 📊 Plotting

The `./analysis` directory contains three standalone scripts for the plotting, two of them running plots for the `5G2` and `4U10` simulation runs and the slbctr reference run.

### Requirements

- Python 3.11+ (tested with Python 3.11)
- Python packages: `xarray`, `numpy`, `pandas`, `matplotlib`

Recommended install in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install xarray numpy pandas matplotlib cartopy scipy
```

Or with conda environment manager using the `./environment-plotting.yml` file:

```bash
module load miniforge3
conda env create -f environment-plotting.yml
conda activate climate-modeling-lab-plotting
```

### Global variable time series

The [`plot-global-variable-timeseries.py`](./analysis/plot-global-variable-timeseries.py) script computes a global mean for the selected variable and then aggregates it to yearly means using month-length weighting. It compares the fixed slabctr reference run, `5G2`, and `4U10`.
Additionally, the script supports the derived variable `toanet` and works with month-length weighted means.

Example with one variable, e.g. plotting `toanet` time series:

```bash
python ./analysis/plot-global-variable-timeseries.py \
  --variable toanet \
  --mode 2d \
  --start-date 2000-01-01 \
  --end-year 2035 \
  --output ./toanet_timeseries.pdf \
  --title "Global mean TOA net radiation"
```

Example with two variables, e.g. plotting `tas` and `pr` time series next to each other:

```bash
python ./analysis/plot-global-variable-timeseries.py \
  --variable tas \
  --variable-2 pr \
  --mode 2d \
  --end-year 2035 \
  --output ./tas_pr_timeseries.pdf \
  --title "Global yearly mean 2m temperature and precipitation"
```

Important options:

- `--variable`: variable to plot. `toanet` is a special alias for `rsdt - rsut - rlut`.
- `--mode`: `2d` or `3d`.
- `--start-date`: first date to include (default `2000-01-01`).
- `--end-year`: optional final year to include, inclusive.
- `--variable-2`: optional second variable; when set, the script makes side-by-side panels.
- `--output`: output file name (default `global_variable_timeseries.pdf`).
- `--title`: optional plot title.

Averaging:

- Monthly data are converted to yearly means with month-length weights so that longer months contribute correctly.
- For multi-year map plots, the data are averaged over the selected year range with month-length weights.

### Maximum jet wind speed time series

The [`plot-jet.py`](./analysis/plot-jet.py) script plots maximum zonal-mean wind speed over latitude and pressure level for a given latitude range and pressure level range, visualizing slabctr reference run, `4U10`, and `5G2`.

Additionally, it can also plot other simulation runs, for which you need to provide the respective input data.
The script expects the input data to contain yearly meaned zonal mean wind speed `wind_speed` and pressure level `pfull` values. The following CDO command can help you achieve this data format from the postprocessed remapped data described in the [🔄 Postprocessing](#-postprocessing) section.

```bash
cdo yearmean -zonmean -expr,'wind_speed=sqrt(ua*ua+va*va); pfull=pfull' -selvar,ua,va,pfull <remapped-3d-output.nc> <output-file.nc>
```

Example:

```bash
python ./analysis/plot-jet.py \
  --lat-min 20.0 \
  --lat-max 80.0 \
  --pmin 100.0 \
  --pmax 400.0 \
  --output ./jet_max_time_series.pdf
```

Important options:

- `lat-min` and `lat-max` specify the latitude range to investigate (default values 20.0 and 80.0).
- `pmin` and `pmax` specify the pressure level range in hPa to restrict to (default values 100.0 and 400.0).
- `--input`: optional input dataset file that can be provided to plot the jet stream wind speed for other simulation runs. You must ensure your data is in the right format as described above.
- `--output`: optional output file name (default `jet_max_time_series.pdf`).

### Single scattering albedo and extinction coefficient time series

The [`plot-ssa-ext.py`](./analysis/plot-ssa-ext.py) script plots the evolvement of single scattering albedo and extinction coefficent for the `4U10` run over time.

Example:

```bash
python ./analysis/plot-ssa-ext.py \
  --output ./ssa_and_ext.pdf.pdf
```

Important options:

- `--output`: optional output file name (default `ssa_and_ext.pdf`).

### Data expectations

- The scripts expect coordinate names `lat`, `lon`, and `time`. The 3D datasets also use `height`.
- The run files are mapped internally from the abbreviations `5G2` and `4U10`.
- The slabctr reference run file is fixed in the script.

### Troubleshooting

- If `toanet` is requested, the component variables `rsdt`, `rsut`, and `rlut` must be present in the output dataset of the simulation run.
- Use `--help` with either script to see the full command line interface.

------------------------------------------------------------------------

## 📝 License

This project is licensed under the Creative Commons License.

------------------------------------------------------------------------

## 📬 Contact

For further questions contact:

- [Matej Paul](https://github.com/mtjPL)
- [Daniel Reiterer](https://github.com/daniel353535)
- [Sebastian Legat](https://github.com/lorenz1917)
- [Silas Meister](https://github.com/Silas2701)
- [Maximilian van der Werf](https://github.com/maxvdw1101)

------------------------------------------------------------------------

## ⭐ Acknowledgements

This project was developed as part of the Climate Modeling Lab course at the Department of Meteorology of the University of Vienna.

The authors would like to thank the course instructor for designing the course and their guidance, feedback, and support throughout the course.