# 📦 climate-modeling-lab-fallout

This project aims to simulate the effect of a nuclear attack by injecting a substantial amount of Black Carbon (BC) into the lower stratosphere that would result from the combustion of the fires that are ignited after the explosions.

------------------------------------------------------------------------

## 📂 Project Structure

------------------------------------------------------------------------

## 🛠️ Getting Started

### Prerequisites

In order to run this project you need to have access to the **Vienna Scientific Cluster 4** (VSC4) HPC platform and have a compiled version of the **ICON-ESM**.

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

## 📊 Plotting

### Postprocessing


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