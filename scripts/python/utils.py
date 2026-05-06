"""Utility functions."""

from datetime import datetime
from pathlib import Path
import shutil
from typing import Union

import numpy as np

ROOT_DIR: Path = Path(__file__).parents[2]
"""The root directory."""

CONFIG_DIR: Path = ROOT_DIR.joinpath("config")
"""The directory where the  default preprocessing config resides."""

DEFAULT_CONFIG_FILE: Path = CONFIG_DIR.joinpath("config.toml")
"""The default config file path."""

EARTH_RADIUS: float = 6371.0e3
"""Average earth radius in meters."""

START_1850: int = 1850
"""Start year 1850 for month computation."""

MONTHS_PER_YEAR: int = 12
"""Number of months in a year."""

SECONDS_PER_YEAR: int = 365.25 * 24 * 60 * 60
"""Amount of seconds in one year (including leap year conditions)."""

def map_altitude_boundary_indices_to_values(altitude_levels: list[float], indices: tuple[int, int]) -> tuple[float, float]:
    """Return the altitude boundaries from the indices.
    
    Args:
        altitude_levels (list[float]): The altitude levels.
        indices (tuple[int, int]): The indices defining the boundary.
    
    Returns:
        float: Altitude boundaries as values.       
    """
    start_idx = indices[0]
    end_idx = indices[1]

    lower_bound = altitude_levels[start_idx]
    upper_bound = altitude_levels[end_idx] 

    return (lower_bound, upper_bound)

def sphere_volume(radius: float) -> float:
    """Compute the volume of a sphere.
    
    Args:
        radius (float): The radius of the sphere.

    Returns:
        float: The volume of the sphere.
    """
    return (4/3) * np.pi * radius**3

def compute_atmosphere_layer_volume_between(lower_altitude: float, upper_altitude: float) -> float:
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

def compute_months_since_1850(year: int) -> np.ndarray:
    """Compute months since the year 1850.
    
    Args:
        year (int): The year for which to compute the month numbers.

    Returns:
        np.ndarray: Array of month numbers.
    """
    months_since_1850 = (year - START_1850) * MONTHS_PER_YEAR
    start_month = months_since_1850 + 1
    end_month = months_since_1850 + MONTHS_PER_YEAR

    months_since_1850_range = np.arange(start_month, end_month + 1)

    return months_since_1850_range

def compute_years_since_simulation_start_from_month(simulation_start_year: int, months_since_1850: int) -> float:
    """Computes the years since the simulation start from the month as floating point number.
    
    Args:
        simulation_start_year (int): The year the simulation starts.
        months_since_1850 (int): The month that has been passed.

    Returns:
        float: Years since simulation start.
    """
    # Subtract 1 to omit off-by-one issue for integer division
    year = START_1850 + ((months_since_1850 - 1) // MONTHS_PER_YEAR)
    month = (months_since_1850 - 1) % MONTHS_PER_YEAR + 1

    # Compute delta of start and current time
    start_time = datetime(simulation_start_year, 1, 1)
    current_time = datetime(year, month, 1)

    delta = current_time - start_time
    x = delta.total_seconds() / SECONDS_PER_YEAR # x in years

    return x