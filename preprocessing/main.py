"""Entry point module for preprocessing."""

import argparse
import os
from aerosol import modify_aerosols
from utils import DEFAULT_CONFIG_FILE

def main() -> None:
    """Parse arguments from cmd and call successive steps to preprocess data.
    
    Raises:
        ValueError: Invalid combination of arguments.    
    """
    parser = argparse.ArgumentParser(description="Example script")

    parser.add_argument("-s", "--start-year", required=True, help="Start year of the simulation")
    parser.add_argument("-e", "--end-year", required=True, help="End yer of the simulation")
    parser.add_argument("-i", "--input-data-dir", required=True, help="The data directory in which the input data is located")
    parser.add_argument("-o", "--output-data-dir", default=os.getcwd(), help="The data directory in which the preprocessed input data is supposed to be stored")
    parser.add_argument("-c", "--config-file", default=DEFAULT_CONFIG_FILE, help="The config.toml file for input data modification")

    args = parser.parse_args()

    modify_aerosols(args)

if __name__ == "__main__":
    main()