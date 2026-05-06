# 📦 climate-modeling-lab-fallout

**climate-modelling-lab-fallout** simulates a climate scenario in which a substantial amount of Black Carbon (BC) is injected into the lower stratosphere as a uniform layer.

------------------------------------------------------------------------

## 🚀 Features

------------------------------------------------------------------------

## 📂 Project Structure

------------------------------------------------------------------------

## 🛠️ Getting Started

### Prerequisites

List your prerequisites

### Installation

Login to VSC4 and direct to your personal user space under the `/gpfs`:

``` bash
cd /gpfs/data/fs72044/<icon-XY>
```

Clone the repository:

``` bash
git clone https://github.com/Silas2701/climate-modeling-lab-fallout.git
cd climate-modeling-lab-fallout
```

Direct to the runscript folder:

``` bash
cd /runs/slabctr


```

And change following instances in the runscript to match your user:

``` bash
nano exp.slabctr.run

--------------------

#SBATCH --output=/gpfs/data/fs72044/<icon-XY>/climate-modeling-lab-fallout/runs/slabctr/LOG.exp.slabctr.run.%j.o
#SBATCH --error=/gpfs/data/fs72044/<icon-XY>/climate-modeling-lab-fallout/runs/slabctr/LOG.exp.slabctr.run.%j.o

...

##SBATCH --mail-user=<user-email>

...

ICONFOLDER=/gpfs/data/fs72044/<icon-XY>/icon-esm-univie/build.vsc4.intel-intelmpi_spack    
RUNSCRIPTDIR=/gpfs/data/fs72044/<icon-XY>/runs/${EXP}
PROJECTDIR=/gpfs/data/fs72044/<icon-XY>/climate-modeling-lab-fallout

...

EXPDIR=/gpfs/data/fs72044/<icon-XY>/experiments/s2026/${EXP}

...

preprocessed_data_dir=/gpfs/data/fs72044/<icon-XY>/<path-to-preprocessed-data>
```

The `preprocessed_data_dir` is the directory where the input data files reside that we need to preprocess to accomodate our climate scenario. It can be any arbitrary location in your icon user directory and the only requirement is that the preprocessed data can be found in this directory. We will cover this topic now.

### Input data perturbation

In order to run our climate scenario we will have to modify the black carbon aerosol input files (`bc_aeropt_cmip6_volc_lw_b16_sw_b14_YYYY.nc`). To facilitate this step you only have to run the `preprocess.sh` script located  in the `/climate-modeling-lab-fallout/scripts` folder. For that, run the following command from your icon user directory:

```bash
climate-modeling-lab-fallout/scripts/preprocess.sh --start-year 2000 --end-year 2050  --input-data-dir /gpfs/data/fs72044/avoigt_teach/msc-climodlab-s2026/mscmet-climmodlab-s2023/ICON-inputdata/amip-VSC4  --output-data-dir /gpfs/data/fs72044/<icon-XY>/<path-to-preprocessed-data>
```

**Important note:** `--start-year` is expected to match `y0` variable from the runscript, as well as `--end-year` which should align with `yN` and `--output-data-dir` with `preprocessed_data_dir`.

Afterwards you will see new files appearing in the directory that you specified as `--output-data-dir` containing the perturbed aerosols data.

Install dependencies:

------------------------------------------------------------------------

## ▶️ Usage

------------------------------------------------------------------------

## ⚙️ Configuration


------------------------------------------------------------------------

## 🧪 Running Tests


------------------------------------------------------------------------

## 🤝 Contributing


------------------------------------------------------------------------

## 📝 License

This project is licensed under the MIT License.

------------------------------------------------------------------------

## 🙋 FAQ


------------------------------------------------------------------------

## 📬 Contact

------------------------------------------------------------------------

## ⭐ Acknowledgements