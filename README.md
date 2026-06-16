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

Next, stratospheric aerosol data needs to be perturbed to simulate a black carbon layer in the lower stratosphere.
A simple shell script `.preprocessing/preprocess.sh` facilitates the preprocessing step and creates modified aerosol files.
Before execution, you will want to make sure to have a look at `./config/config.toml` which controls how the black carbon layer is constructed and how black carbon decays over time. Feel free to adjust it to your needs.
For specific configuration setup of our simulation runs have a look at the [⚙️ Configuration](#️-configuration) section.

The script can then be invoked in the following way:

```bash
./preprocessing/preprocessing.sh --start-year 2000 --end-year 2050  --input-data-dir /gpfs/data/fs72044/avoigt_teach/msc-climodlab-s2026/mscmet-climmodlab-s2023/ICON-inputdata/amip-VSC4  --output-data-dir <output-data-dir>
```

**Important note:** `--start-year` is the start year of the simulation and expected to match the year that is mentioned in the `initial_date` variable of the runscript `./runscripts/exp.slabctr.run`. As well as `--end-year` which represents the final year of the simulation that is supposed to align with the year expressed in the `final_date` variable in the given runscript.

After execution you will observe that the modified aerosol files have been saved to the directory specified by the `--output-data-dir` argument.

### Runscript execution

Before submitting the slab-ocean simulation, we need to ensure that the runscript finds our modified aerosol files and that the experiment output is written to the correct directoy. Therefore, head to the runscript `./runscripts/exp.slabctr.run` and edit and replace the following lines where we have inserted tag placeholders.

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

modified_aerosols_dir=<path-to-your-modified-aerosols-data> # This should match the --output-data-dir argument, provided to the prior execution of the preprocessing script
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

The configuration file at `./config/config.toml` allows to adjust the parameters for the modification of the aerosol files.  
We will give a brief overview over the available parameters for the `[aerosol]` table which controls the aerosol modification.

- **bc_layer_width_levels**: The width of the black carbon layer, expressed in levels (1 level ≙ 0.5km).
- **bc_layer_distribution**: The distribution in the black carbon layer. "uniform" will apply equal concentration of black carbon anywhere in the black carbon layer, "guassian" will result in a gaussian distribution in the vertical to have lower concentrations at the upper and lower bounds and higher concentration around the center.
- **bc_mass**: The total black carbon mass emitted, measured in g.
- **bc_mass_ext_coeff**: The mass extinction coefficient of black carbon that is assumed, measured in m^2/kg.
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

Furthermore we also require grid remapping from cell-grid to lat-lon-grid which will later then be processed in our plot scripts:

```bash
cdo remapcon,r360x180 slabctr_atm_2d_ml_ALL.nc slabctr_atm_2d_ml_ALL.r360x180.nc # For 2D output

cdo remapcon,r360x180 slabctr_atm_3d_ml_ALL.nc slabctr_atm_3d_ml_ALL.r360x180.nc # For 2D output
```

------------------------------------------------------------------------

## 📊 Plotting

The `./analysis` directory contains two standalone scripts for the fallout model runs `5G2` and `4U10`. Both scripts use a fixed reference dataset, support the derived variable `toanet`, and work with month-length weighted means.

### Requirements

- Python 3.8+ (tested with Python 3.11)
- Python packages: `xarray`, `numpy`, `pandas`, `matplotlib`

Recommended install in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install xarray numpy pandas matplotlib cartopy scipy
```

Or with conda environment manager:

```bash
module load miniforge3
conda create -n climate-modeling-lab-fallout python==3.11
pip install xarray numpy pandas matplotlib cartopy scipy
```

### Scripts

- **Timeseries script**: `plot-fallout-global-variable-timeseries.py`: plots global mean yearly time series for the reference, `5G2`, and `4U10`, with optional side-by-side plots for a second variable.

### Timeseries script

The `plot-fallout-global-variable-timeseries.py` timeseries script computes a global mean for the selected variable and then aggregates it to yearly means using month-length weighting. It compares the fixed reference, `5G2`, and `4U10`.

Example:

```bash
python plot-fallout-global-variable-timeseries.py \
  --variable toanet \
  --mode 2d \
  --start-date 2000-01-01 \
  --end-year 2035 \
  --output ./toanet_timeseries.pdf \
  --title "Global mean TOA net radiation"
```

Example with two variables:

```bash
python plot-fallout-global-variable-timeseries.py \
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
- `--start-date`: first date to include.
- `--end-year`: optional final year to include, inclusive.
- `--variable-2`: optional second variable; when set, the script makes side-by-side panels.
- `--output`: output file name.
- `--title`: optional plot title.

#### Averaging and significance

- Monthly data are converted to yearly means with month-length weights so that longer months contribute correctly.
- For multi-year map plots, the data are averaged over the selected year range with month-length weights.

#### Data expectations

- The scripts expect coordinate names `lat`, `lon`, and `time`. The 3D datasets also use `height`.
- The run files are mapped internally from the abbreviations `5G2` and `4U10`.
- The reference file is fixed in the script.

#### Troubleshooting

- If `toanet` is requested, the component variables `rsdt`, `rsut`, and `rlut` must be present.
- Use `--help` with either script to see the full command line interface.

cdo yearmean -zonmean -expr,'wind_speed=sqrt(ua*ua+va*va); pfull=pfull' -selvar,ua,va,pfull /gpfs/data/fs72044/icon17/anal
ysis/slabctr_atm_3d_ml_1979-2035_remap.nc slabctr-full-sample.nc


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