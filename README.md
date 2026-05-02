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
```

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