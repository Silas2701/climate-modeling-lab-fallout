"""Module for modifying aerosol input data."""

from functools import partial
from pathlib import Path

import xarray as xr
import numpy as np
from argparse import Namespace

from config import Config
from utils import compute_atmosphere_layer_volume_between, compute_months_since_1850, compute_years_since_simulation_start_from_month, map_altitude_boundary_indices_to_values

KM_TO_M: int = 1000
"""Conversion from km to m."""

M_TO_KM: int = 0.001
"""Conversion from m to km"""

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

def _get_bc_layer_boundary_indices(aerosol_data: xr.Dataset) -> tuple[int, int]:
    """Calculate the altitude boundary indices based on ext_sun for the black carbon layer.
    
    Args:
        aerosol_data (xr.Dataset): The aerosol dataset.

    Returns:
        tuple[int, int]: The indices of lower and upper altitude boundaries for the black carbon layer.
    """
    ext_sun = aerosol_data["ext_sun"]

    mask = ext_sun == 0
    max_altitude_idx = int(ext_sun["altitude"].where(mask).max(dim=["latitude", "solar_bands", "month"]).argmax("altitude"))

    start_idx = max_altitude_idx + 1
    end_idx = start_idx + BC_LAYER_DELTA_ALTITUDE_LEVELS

    return (start_idx, end_idx)

def _compute_bc_extinction_coefficient(altitude_levels: list[int], bc_layer_boundary_indices: tuple[int, int], config: Config) -> float:
    """Compute the extinction coefficient for black carbon.
    
    Args:
        altitude_levels (list[float]): Altitude levels from the reference dataset.
        bc_layer_boundary_indices (tuple[int, int]): Index of lower and upper altitude of black carbon layer.
        config (Config): The configuration object.

    Returns:
        float: The extinction coefficient.
    """
    lower_altitude_in_km, upper_altitude_in_km = map_altitude_boundary_indices_to_values(altitude_levels, bc_layer_boundary_indices)

    lower_altitude = lower_altitude_in_km * KM_TO_M
    upper_altitude = upper_altitude_in_km * KM_TO_M

    bc_layer_volume = compute_atmosphere_layer_volume_between(lower_altitude, upper_altitude)

    bc_mass = config.get_black_carbon_mass()
    bc_mass_ext_coeff = config.get_black_carbon_mass_extinction_coefficient()

    bc_mass_concentration = bc_mass / bc_layer_volume  # Compute the mass concentration of black carbon in g/m^3
    
    bc_ext_coeff = bc_mass_concentration * bc_mass_ext_coeff / M_TO_KM  # Compute the extinction coefficient in km^-1  

    return bc_ext_coeff

def _compute_ext_sun(ext_sun_initial: float, ext_sun_original: np.ndarray, decay_rate: float, x: float) -> np.ndarray:
    """Compute the extinction coefficient as a function of decay toward a target value.

    Args:
        ext_sun_initial (float): The initial extinction coefficient that we want to start with.
        ext_sun_original (np.ndarray): The original extinction coefficients from the reference dataset.
        decay_rate_per_year (float): The decay rate.
        x (float): Time value to pass to the decay function.

    Returns:
        np.ndarray: The extinction coefficient at the given time.
    """
    return ext_sun_original + (ext_sun_initial - ext_sun_original) * np.exp(-decay_rate * x)

def _compute_omega_sun(omega_sun_initial: float, omega_sun_original: float, decay_rate: float, x: float) -> np.ndarray:
    """Compute SSA as a function of decay toward a target value with interpolation between initial and original SSA

    Args:
        omega_sun_initial (float): The initial SSA that we want to start with.
        omega_sun_original (float): The original SSA from the reference dataset.
        decay_rate_per_year (float): The decay rate.
        x (float): Time value to pass to the decay function.

    Returns:
        np.ndarray: The SSA at the given time.
    """
    return omega_sun_original * (1 - np.exp(-decay_rate * x)) + omega_sun_initial * np.exp(-decay_rate * x)  


def _modify_data(ds: xr.Dataset, simulation_start_year: int, bc_layer_boundary_indices: tuple[int, int], bc_ext_coeff: float, bc_ssa: float,  bc_decay_rate: float) -> xr.Dataset:
    """Modify the data variables in the aerosol data for a given month.
    
    Args:
        ds (xr.Dataset): The dataset for one specific month.
        simulation_start_year (int): The start year of the simulation.
        bc_layer_boundary_indices (tuple[int, int]): Index of lower and upper altitude of black carbon layer.
        bc_ext_coeff (float): The extinction coefficient of black carbon in our layer.
        bc_ssa: SSA of black carbon.
        bc_decay_rate (float): Decay rate of balck carbon.

    Returns:
        xr.Dataset: The modified dataset.
    """
    # Compute years since simulation start
    months_since_1850 = int(ds["month"][0])    
    x = compute_years_since_simulation_start_from_month(simulation_start_year, months_since_1850)

    # Select the bc layer of interest
    layer = ds.isel(altitude=slice(*bc_layer_boundary_indices))

    # Extract each data variable
    ext_sun_original = layer["ext_sun"]
    omega_sun_original = layer["omega_sun"]

    # Compute new ext_sun
    compute_ext_sun = partial(
        _compute_ext_sun,
        ext_sun_initial=bc_ext_coeff,
        decay_rate=bc_decay_rate,
        x=x
    )

    ext_sun_new = xr.apply_ufunc(lambda original: compute_ext_sun(ext_sun_original=original), ext_sun_original)

    # Compute new omega_sun

    # Compute weighted initial SSA weighted by extinction coefficient based on the following formula:
    # ssa = (ssa_smoke*ext_coeff_smoke + ssa_prior*ext_coeff_prior)/(extcoeff_smoke + ext_coeff_prior)
    omega_sun_initial = (bc_ssa * ext_sun_new + omega_sun_original * ext_sun_original) / (ext_sun_new + ext_sun_original)

    compute_omega_sun = partial(
        _compute_omega_sun,
        decay_rate=bc_decay_rate,
        x=x
    )
    omega_sun_new = xr.apply_ufunc(lambda initial, original: compute_omega_sun(omega_sun_initial=initial, omega_sun_original=original), omega_sun_initial, omega_sun_original)


    # Update data variables adn return updated dataset

    # Extract start and end index of altitude boundaries.
    # Subtract 1 from end_idx, because for slicing with actual values the upper bound is included
    # unlike in the case of indexing where the upper bound is excluded
    start_idx = bc_layer_boundary_indices[0]
    end_idx = bc_layer_boundary_indices[1] - 1

    altitude_levels = ds["altitude"].values

    altitude_boundaries = map_altitude_boundary_indices_to_values(altitude_levels, (start_idx, end_idx))

    ds["ext_sun"].loc[dict(altitude=slice(*altitude_boundaries))] = ext_sun_new
    ds["omega_sun"].loc[dict(altitude=slice(*altitude_boundaries))]  = omega_sun_new

    return ds


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
    bc_layer_boundary_indices = _get_bc_layer_boundary_indices(aerosol_data)

    altitude_levels = aerosol_data["altitude"].values
    
    # Compute properties for black carbon decay simulation (initial quantity N0 and decay rate λ)
    bc_ext_coeff = _compute_bc_extinction_coefficient(altitude_levels, bc_layer_boundary_indices, config)

    # Extract other variables from config, such as ssa and the decay rate
    bc_ssa = config.get_black_carbon_single_scattering_albedo()
    bc_decay_rate = config.get_black_carbon_decay_rate()

    # Partial initialized _modify_data function
    modify_data = partial(
        _modify_data,
        simulation_start_year=start_year,
        bc_layer_boundary_indices=bc_layer_boundary_indices,
        bc_ext_coeff=bc_ext_coeff,
        bc_ssa=bc_ssa,
        bc_decay_rate=bc_decay_rate,
    )

    # Create a modified aerosol file for each simulation file
    for year in range(start_year, end_year + 1):
        modified_aerosol_data = aerosol_data.copy(deep=True)

        # Correct months (starting from 1850-01) -> Original month dim uses months from 2000
        modified_aerosol_data["month"] = compute_months_since_1850(year)

        # Modify data variables
        modified_aerosol_data = modified_aerosol_data.groupby("month").apply(modify_data)

        # Write out modified data
        output_file_name = AEROSOL_OUTPUT_FILE_NAME_TEMPLATE.format(year)
        output_file = output_data_dir.joinpath(output_file_name)

        # Unlink if existing output file is a symlink
        if output_file.is_symlink():
            output_file.unlink()

        modified_aerosol_data.to_netcdf(output_file)