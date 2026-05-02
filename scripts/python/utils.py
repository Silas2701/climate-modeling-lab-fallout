"""Utility functions."""

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

def clear_directory(path: Union[str, Path]) -> None:
    """Clear directoy with all its files and sub-directories.
    
    Args:
        path (Union[str, Path]): The path of the directory to clear.
    """
    path = Path(path)

    if not path.is_dir():
        return

    for item in path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

def sphere_volume(radius: float) -> float:
    """Compute the volume of a sphere.
    
    Args:
        radius (float): The radius of the sphere.

    Returns:
        float: The volume of the sphere.
    """
    return (4/3) * np.pi * radius**3