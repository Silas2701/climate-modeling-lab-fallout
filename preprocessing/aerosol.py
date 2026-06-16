"""Module for modifying aerosol input data."""

from functools import partial
from pathlib import Path
from typing import Literal

import xarray as xr
import numpy as np
from argparse import Namespace

from config import Config
from maths import gaussian_bin_probs
from utils import compute_atmosphere_layer_volume_between, compute_months_since_1850, compute_years_since_simulation_start_from_month, map_altitude_boundary_indices_to_values

ONE_ALTITUDE_LEVEL: int = 1
"""One altitude level."""

KM_TO_M: int = 1000
"""Conversion from km to m."""

M_TO_KM: int = 0.001
"""Conversion from m to km"""

GAUSSIAN: str = "gaussian"
"""Guassian distribution type."""

UNIFORM: str = "uniform"
"""Uniform distribution type."""

AEROSOL_REF_YEAR: int = 2000
"""Aerosol reference year."""

AEROSOL_DIR_NAME: str = "aerosol"
"""Directoy name for aerosol input data."""

AEROSOL_INPUT_FILE_NAME_TEMPLATE: str = "bc_aeropt_cmip6_volc_lw_b16_sw_b14_{0}.nc"
"""Aerosol file name template for the input aerosol files."""

AEROSOL_REF_FILE_NAME: str = AEROSOL_INPUT_FILE_NAME_TEMPLATE.format(AEROSOL_REF_YEAR)
"""Aerosol file name of the reference aerosol input data."""

AEROSOL_OUTPUT_FILE_NAME_TEMPLATE: str = "bc_aeropt_cmip6_volc_lw_b16_sw_b14_{0}_modified.nc"
"""Aerosol file name template to be used for naming the modified output aerosol files."""

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

def _get_altitude_level_above_highest_tropopause(aerosol_data: xr.Dataset) -> int:
    """Calculate the altitude level above the hightes point of the tropopause.
    
    Args:
        aerosol_data (xr.Dataset): The aerosol dataset.
        bc_layer_width (int): The black carbon layer width expressed in levels.

    Returns:
        int: The altitude level that is above the highest point of the tropopause.
    """
    ext_sun = aerosol_data["ext_sun"]

    mask = ext_sun == 0
    highest_level_tropopause = int(ext_sun["altitude"].where(mask).max(dim=["latitude", "solar_bands", "month"]).argmax("altitude"))

    level_above_highest_tropopause = highest_level_tropopause + ONE_ALTITUDE_LEVEL

    return level_above_highest_tropopause

def _compute_bc_extinction_coefficient(lower_altitude: float, upper_altitude: float, config: Config) -> float:
    """Compute the extinction coefficient for black carbon.
    
    Args:
        lower_altitude (float): The lower altitude level in km.
        upper_altitude (float): The upper altitude level in km.
        config (Config): The configuration object.

    Returns:
        float: The extinction coefficient.
    """
    lower_altitude_in_m = lower_altitude * KM_TO_M
    upper_altitude_in_m = upper_altitude * KM_TO_M

    bc_layer_volume = compute_atmosphere_layer_volume_between(lower_altitude_in_m, upper_altitude_in_m)

    bc_mass = config.get_black_carbon_mass()
    bc_mass_ext_coeff = config.get_black_carbon_mass_extinction_coefficient()

    bc_mass_concentration = bc_mass / bc_layer_volume  # Compute the mass concentration of black carbon in g/m^3
    
    bc_ext_coeff = bc_mass_concentration * bc_mass_ext_coeff / M_TO_KM  # Compute the extinction coefficient in km^-1  

    return bc_ext_coeff

def _get_bc_ext_coeff_distribution(bc_ext_coeff: float, altitudes: xr.DataArray, distribution: Literal["gaussian", "uniform"]) -> xr.DataArray:
    """Compute distribution for the bc_ext_coeff based on the distribution type.
    
    Args:
        bc_ext_coeff (float): The extinction coefficient computed for black carbon.
        altitudes (xr.DataArray): The altitude levels.
        distribution (Literal["gaussian", "uniform"]): The distribution for the black carbon layer.

    Returns:
        xr.DataArray: The modified omega_sun data array.
    """
    # Take the number of altitude levels as number of bins
    n_bins = altitudes.size

    if distribution == GAUSSIAN:
        probs = gaussian_bin_probs(n_bins=n_bins)
    elif distribution == UNIFORM:
        probs = np.full(n_bins, 1 / n_bins)
    else:
        raise ValueError("Invalid value for 'bc_layer_distribution' in config.toml")
    
    # Summing up the bc_ext_coeff for all levels
    bc_ext_coeff_sum = bc_ext_coeff * n_bins

    # Constructing distribution based on probabilities
    distribution = probs * bc_ext_coeff_sum

    # Create data array with distribution and altitude levels
    bc_ext_coeff_distribution = xr.DataArray(
        distribution,
        dims=("altitude"),
        coords={"altitude": altitudes}
    )
    
    return bc_ext_coeff_distribution

def _compute_modified_ext_sun(ext_sun: np.ndarray, ext_sun_bc: np.ndarray, decay_rate: float, x: float) -> np.ndarray:
    """Compute the extinction coefficient as a function of decay toward a target value.

    Args:
        ext_sun (float): The extinction coefficients from the reference dataset.
        ext_sun_bc (np.ndarray): The extinction coefficients computed from bc concentraion.
        decay_rate (float): The decay rate.
        x (float): Time value to pass to the decay function.

    Returns:
        np.ndarray: The extinction coefficient at the given time.
    """
    return ext_sun + ext_sun_bc * np.exp(-decay_rate * x)

def _compute_modified_omega_sun(omega_sun:  np.ndarray, omega_sun_bc: float, ext_sun:  np.ndarray, ext_sun_bc:  np.ndarray) ->  np.ndarray:
    """Compute SSA as a function of decay toward a target value with interpolation between initial and original SSA

    Args:
        omega_sun_original ( np.ndarray): The original SSA from the reference dataset.
        omega_sun_bc (float): The SSA from black carbon.
        ext_sun_original ( np.ndarray): The original extinction coefficients from the reference dataset.
        ext_sun_bc ( np.ndarray): The original extinction coefficients computed from black carbon.

    Returns:
         np.ndarray: The mixed SSA for the given time.
    """
    ssa = (omega_sun_bc * ext_sun_bc + omega_sun * ext_sun) / (ext_sun_bc + ext_sun)

    return ssa


def _modify_ext_sun(ext_sun: xr.DataArray, simulation_start_year: int, bc_ext_coeff: float, bc_layer_distribution: Literal["guassian", "uniform"], bc_decay_rate: float) -> xr.DataArray:
    """Modify the ext_sun variables in the aerosol data for a given month.
    
    Args:
        ext_sun_da (xr.DataArray): The data array of the ext_sun variable for a certain month.
        simulation_start_year (int): The start year of the simulation.
        bc_ext_coeff (float): The extinction coefficient of black carbon in our layer.
        bc_layer_distribution (Literal["guassian", "uniform"]): The type of distribution to choose for the black carbon layer.
        bc_decay_rate (float): The decay rate for black carbon.

    Returns:
        xr.DataArray: The modified ext_sun data array.
    """
    # Compute years since simulation start
    months_since_1850 = int(ext_sun["month"].values[0])    
    x = compute_years_since_simulation_start_from_month(simulation_start_year, months_since_1850)

    # Get the distribution of bc_ext_coeff across altitude levels
    bc_ext_coeff_distribution = _get_bc_ext_coeff_distribution(bc_ext_coeff, ext_sun["altitude"], bc_layer_distribution)

    # Broadcast distribution along ext_sun variable to retrieve intial values for ext_sun from black carbon
    ext_sun_bc = bc_ext_coeff_distribution.broadcast_like(ext_sun)

    modified_ext_sun = xr.apply_ufunc(
        _compute_modified_ext_sun,
        ext_sun,
        ext_sun_bc,
        bc_decay_rate,
        x
    )

    return modified_ext_sun

def _modify_omega_sun(omega_sun: xr.DataArray, omega_sun_bc: float, ext_sun: xr.DataArray, ext_sun_bc: xr.DataArray) -> xr.DataArray:
    """Modify the ext_sun variables in the aerosol data for a given month.
    
    Args:
        omega_sun (xr.DataArray): The data array of the omega_sun variable (SSA) for a certain month.
        omega_sun_bc (float): The static SSA value for bc.
        ext_sun (xr.DataArray): The extinction coefficients of black carbon in the original unmodified data.
        ext_sun_bc (xr.DataArray): The black carbon modified extinction coefficients.

    Returns:
        xr.DataArray: The modified omega_sun data array.
    """
    # Select ext_sun and ext_sun_bc for the given month
    ext_sun = ext_sun.sel(month=omega_sun["month"])
    ext_sun_bc = ext_sun_bc.sel(month=omega_sun["month"])

    modified_omega_sun= xr.apply_ufunc(
        _compute_modified_omega_sun,
        omega_sun,
        omega_sun_bc,
        ext_sun,
        ext_sun_bc
    )

    return modified_omega_sun


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
    bc_layer_width = config.get_black_carbon_layer_width_in_levels()

    bc_layer_level_low = _get_altitude_level_above_highest_tropopause(aerosol_data)
    bc_layer_level_up = bc_layer_level_low + bc_layer_width

    # Compute black carbon extinction coefficient
    lower_altitude = aerosol_data.altitude.isel(altitude=bc_layer_level_low).item()
    upper_altitude = aerosol_data.altitude.isel(altitude=bc_layer_level_up).item()
    
    bc_ext_coeff = _compute_bc_extinction_coefficient(lower_altitude, upper_altitude, config)

    # Get values from config
    bc_decay_rate = config.get_black_carbon_decay_rate()
    bc_ssa = config.get_black_carbon_single_scattering_albedo()
    bc_layer_distribution = config.get_black_carbon_layer_distribution()

    # Create a modified aerosol file for each simulation file
    for year in range(start_year, end_year + 1):
        modified_aerosol_data = aerosol_data.copy(deep=True)

        # Correct months (starting from 1850-01) -> Original month dim uses months from 2000
        corrected_months = compute_months_since_1850(year)
        modified_aerosol_data = modified_aerosol_data.assign_coords(month=corrected_months)

        # Select region of interest for black carbon layer
        altitude_filter = slice(bc_layer_level_low, bc_layer_level_up)
        bc_layer = modified_aerosol_data.isel(altitude=altitude_filter)

        # Remember original ext_sun values for omega_sun computation before modifying
        ext_sun = bc_layer["ext_sun"]

        # Modify ext_sun variable
        bc_layer["ext_sun"] = bc_layer["ext_sun"] \
            .groupby("month") \
            .map(
                _modify_ext_sun,
                simulation_start_year=start_year,
                bc_decay_rate=bc_decay_rate,
                bc_ext_coeff=bc_ext_coeff,
                bc_layer_distribution=bc_layer_distribution,
            )
        
        # Modify omega_sun variable
        bc_layer["omega_sun"] = bc_layer["omega_sun"] \
            .groupby("month") \
            .map(
                _modify_omega_sun,
                omega_sun_bc=bc_ssa,
                ext_sun=ext_sun,
                ext_sun_bc=bc_layer["ext_sun"],
            )
        
        # Update aerosol dataset with black carbon layer
        modified_aerosol_data[["ext_sun", "omega_sun"]].loc[{"altitude": bc_layer["altitude"]}] = bc_layer[["ext_sun", "omega_sun"]]

        # Create aerosol output data directory (if it does not exist)
        aerosol_output_dir = output_data_dir.joinpath(AEROSOL_DIR_NAME)
        aerosol_output_dir.mkdir(parents=True, exist_ok=True)

        # Write out modified data
        output_file_name = AEROSOL_OUTPUT_FILE_NAME_TEMPLATE.format(year)
        output_file = aerosol_output_dir.joinpath(output_file_name)

        # Unlink if existing output file is a symlink
        if output_file.is_symlink():
            output_file.unlink()

        modified_aerosol_data.to_netcdf(output_file)