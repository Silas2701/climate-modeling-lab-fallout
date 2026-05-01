"""Module for modifying aerosol input data."""

from functools import partial
from pathlib import Path
import tomllib
from typing import Any

import xarray as xr
import numpy as np
from argparse import Namespace
from datetime import datetime

from config import Config
from utils import clear_directory, sphere_volume

KM_TO_M: int = 1000
"""Conversion from km to m."""

M_TO_KM: int = 0.001
"""Conversion from m to km"""

START_1850: int = 1850
"""Start year 1850 for month computation."""

MONTHS_PER_YEAR: int = 12
"""Number of months in a year."""

AEROSOL_REF_YEAR: int = 2000
"""Aerosol reference year."""

AEROSOL_DIR_NAME: str = "aerosol"
"""Directoy name for aerosol input data."""

AEROSOL_FILE_NAME_TEMPLATE: str = "bc_aeropt_cmip6_volc_lw_b16_sw_b14_{0}.nc"
"""Aerosol file name template to be used for naming the modified aerosol files."""

AEROSOL_REF_FILE_NAME: str = AEROSOL_FILE_NAME_TEMPLATE.format(AEROSOL_REF_YEAR)
"""Aerosol file name of the reference aerosol input data ."""

SECONDS_PER_YEAR: int = 365.25 * 24 * 60 * 60
"""Amount of seconds in one year (including leap year conditions)."""

EARTH_RADIUS: float = 6371.0e3
"""Average earth radius in meters."""

BC_LAYER_DELTA_ALTITUDE_LEVELS: int = 2
"""The number of altitude levels to select for our black carbon layer (1 level = 500m)."""

def _get_ref_aerosol_data(input_data_dir: Path) -> xr.Dataset:
    """Load reference aerosol dataset.
    
    Args:
        input_data_dir (Path): The directory where input data is located.

    Returns:
        xr.Dataset: The aerosol dataset.
    """

    aerosol_dir = input_data_dir / AEROSOL_DIR_NAME
    aerosol_file = aerosol_dir / AEROSOL_REF_FILE_NAME

    return xr.open_dataset(aerosol_file)

def _calculate_bc_layer_altitude_boundaries(aerosol_data: xr.Dataset) -> tuple[float, float]:
    """Calculate the altitude boundaries for the black carbon layer.
    
    Args:
        aerosol_data (xr.Dataset): The aerosol dataset.

    Returns:
        tuple[float, float]: Lower and upper altitude boundaries for the black carbon layer.
    """
    ext_sun = aerosol_data["ext_sun"]

    mask = ext_sun == 0
    max_altitude_idx = int(ext_sun["altitude"].where(mask).max(dim=["latitude", "solar_bands", "month"]).argmax("altitude"))

    start_idx = max_altitude_idx + 1
    end_idx = start_idx + BC_LAYER_DELTA_ALTITUDE_LEVELS

    altitudes = aerosol_data["altitude"].values

    bc_lower_altitude = float(altitudes[start_idx])
    bc_upper_altitude = float(altitudes[end_idx])

    return (bc_lower_altitude, bc_upper_altitude)

def _compute_atmosphere_layer_volume_between(lower_altitude: float, upper_altitude: float) -> float:
    """Compute the volume of the black carbon layer in atmosphere between lower and upper level.
    
    Args:
        lower_altitude (float): The lower altitude boundary in meters.
        upper_altitude (float): The upper altitude boundary in meters.

    Returns:
        float: The volume of the atmospheric layer.
    """
    lower_from_earth = EARTH_RADIUS + lower_altitude
    upper_from_earth = EARTH_RADIUS + upper_altitude

    return sphere_volume(upper_from_earth) - sphere_volume(lower_from_earth)

def _get_bc_decay_rate(config: Config) -> float:
    """Get the decay rate for black carbon.
    
    Args:
        config (Config): The configuration object.

    Returns:
        float: The decay rate.
    """
    bc_e_folding_time = config["aerosol"]["bc_e_folding_time"]
    bc_decay_rate = 1 / bc_e_folding_time 

    return bc_decay_rate

def _compute_bc_extinction_coefficient(altitude_boundaries: tuple[float, float], config: Config) -> float:
    """Compute the extinction coefficient for black carbon.
    
    Args:
        altitude_boundaries (tuple[float, float]): Lower and upper altitude boundaries.
        config (Config): The configuration object.

    Returns:
        float: The extinction coefficient.
    """
    lower_altitude = altitude_boundaries[0] * KM_TO_M
    upper_altitude = altitude_boundaries[1] * KM_TO_M

    bc_layer_volume = _compute_atmosphere_layer_volume_between(lower_altitude, upper_altitude)

    bc_mass = config["aerosol"]["bc_mass"]
    bc_mass_ext_coeff = config["aerosol"]["bc_mass_ext_coeff"]

    bc_mass_concentration = bc_mass / bc_layer_volume  # Compute the mass concentration of black carbon in g/m^3
    
    bc_ext_coeff = bc_mass_concentration * bc_mass_ext_coeff / M_TO_KM  # Compute the extinction coefficient in km^-1  

    return bc_ext_coeff

def _compute_average_ext_sun(aerosol_data: xr.Dataset, altitude_boundaries: tuple[float, float]) -> float:
    """Compute the average ext_sun within the altitude boundaries.
    
    Args:
        aerosol_data (xr.Dataset): The aerosol dataset.
        altitude_boundaries (tuple[float, float]): Lower and upper altitude boundaries.

    Returns:
        float: The average ext_sun value.
    """
    ext_sun = aerosol_data["ext_sun"]
    ext_sun_bc_layer = ext_sun.sel(altitude=slice(*altitude_boundaries))

    return float(ext_sun_bc_layer.mean(skipna=True))

def _compute_exp_decay(initial_amount: float, decay_rate: float, x: float) -> float:
    """Exponential decay function.
    
    Args:
        initial_amount (float): The initial amount.
        decay_rate_per_year (float): The decay rate.
        x (float): Value to pass to the decay function.

    Returns:
        float: The decayed amount.
    """
    return initial_amount * np.exp(-decay_rate * x)

def _modify_ext_sun(da: xr.DataArray, simulation_start_year: int, altitude_boundaries: tuple[float, float], bc_ext_coeff_initial: float, bc_decay_rate: float, bc_ext_coeff_threshold: float) -> xr.DataArray:
    """Modify the ext_sun data array based on black carbon decay.
    
    Args:
        da (xr.DataArray): The ext_sun data array.
        simulation_start_year (int): The start year of the simulation.
        altitude_boundaries (tuple[float, float]): Lower and upper altitude boundaries.
        bc_ext_coeff_initial (float): Initial extinction coefficient.
        bc_decay_rate (float): Decay rate.
        bc_ext_coeff_threshold (float): Threshold for extinction coefficient.

    Returns:
        xr.DataArray: The modified data array.
    """
    months_since_1850 = int(da["month"][0])

    # Subtract 1 to omit off-by-one issue for integer division
    year = START_1850 + ((months_since_1850 - 1) // MONTHS_PER_YEAR)
    month = (months_since_1850 - 1) % MONTHS_PER_YEAR + 1

    # Compute delta of start and current time
    start_time = datetime(simulation_start_year, 1, 1)
    current_time = datetime(year, month, 1)

    delta = current_time - start_time
    x = delta.total_seconds() / SECONDS_PER_YEAR # x in years

    bc_ext_coeff = _compute_exp_decay(bc_ext_coeff_initial, bc_decay_rate, x)

    # If computed bc extinction coefficient exceeds threshold, set ext_sun with selected altitude boundaries to the computed value
    if bc_ext_coeff > bc_ext_coeff_threshold:
        da = da.where((da["altitude"] < altitude_boundaries[0]) | (da["altitude"] >= altitude_boundaries[1]), other=bc_ext_coeff)

    return da

def modify_aerosols(args: Namespace) -> None:
    """Modify the aerosols input data.
    
    Args:
        args (Namespace): The arguments passed to the program.
    """
    # Unpack args from cmd
    input_data_dir = Path(args.input_data_dir).resolve()
    output_data_dir = Path(args.output_data_dir).resolve()
    config_file = Path(args.config_file).resolve()

    start_year = int(args.start_year)
    end_year = int(args.end_year)

    # Load config with parameters
    config = Config(config_file)
    
    # Get aerosol data
    aerosol_data = _get_ref_aerosol_data(input_data_dir)

    # Calculate the altitude boundaries of the bc layer
    bc_layer_altitude_boundaries = _calculate_bc_layer_altitude_boundaries(aerosol_data)
    
    # Compute properties for black carbon decay simulation (initial quantity N0 and decay rate λ)
    bc_ext_coeff_initial = _compute_bc_extinction_coefficient(bc_layer_altitude_boundaries, config)
    bc_decay_rate = _get_bc_decay_rate(config)

    # Compute average ext_sun within altitude boundaries as reference value for the threshold
    bc_ext_coeff_threshold = _compute_average_ext_sun(aerosol_data, bc_layer_altitude_boundaries)

    # Partially parametrize _modify_ext_sun function with already available parameters
    modify_ext_sun = partial(
        _modify_ext_sun,
        simulation_start_year=start_year,
        altitude_boundaries=bc_layer_altitude_boundaries,
        bc_ext_coeff_initial=bc_ext_coeff_initial,
        bc_decay_rate=bc_decay_rate,
        bc_ext_coeff_threshold=bc_ext_coeff_threshold
    )

    # Create a modified aerosol file for each simulation file 
    for year in range(start_year, end_year + 1):
        modified_aerosol_data = aerosol_data.copy()

        # Adjust months (starting from 1850-01) -> Original month dim uses year 2000 from reference dataset
        months_since_1850 = (year - START_1850) * MONTHS_PER_YEAR
        start_month = months_since_1850 + 1
        end_month = months_since_1850 + MONTHS_PER_YEAR

        modified_aerosol_data["month"] = np.arange(start_month, end_month + 1)

        # Modify ext_sun
        modified_aerosol_data["ext_sun"] = modified_aerosol_data["ext_sun"].groupby("month").map(modify_ext_sun)

        # Write out modified data
        output_file_name = AEROSOL_FILE_NAME_TEMPLATE.format(year)
        output_file = output_data_dir.joinpath(output_file_name)

        # Unlink if existing output file is a symlink
        if output_file.is_symlink():
            output_file.unlink()

        modified_aerosol_data.to_netcdf(output_file)