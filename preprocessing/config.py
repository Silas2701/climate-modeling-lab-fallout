"""Config module to read in configuration from .toml files."""

from pathlib import Path
import sys
from typing import Any, Literal, Optional, Union

# Python 3.11+ has tomllib in stdlib
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

class Config:
    """Config class to store configuration for the modifications."""

    def __init__(self, path: Union[str, Path]):
        """Initialize Config class.
        
        Args:
            path (Path): The path of the config file.
        """
        self._path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        """Load config file.
        
        Returns:
            dict: A dictionary with all key-value pairs from the config file.
        """
        with open(self._path, "rb") as f:
            return tomllib.load(f)

    def __getitem__(self, key: str) -> Union[dict, Any]:
        """Access item of config with indexing.
        
        Args:
            key (str): The key to access.

        Returns:
            Union[dict, Any]: Value for the requested key.
        """
        return self._data[key]

    def get(self, key: str, default: Optional[str]=None) -> Union[Optional[dict], Optional[Any]]:
        """Access item of config with get method.
        
        Args:
            key (str): The key to access.
            default (Optional[str]): Optional default value if key does not exst.
            
        Returns:
            Union[Optional[dict], Optional[Any]]: Value for the requested key or 'None'.
        """
        return self._data.get(key, default)

    def to_dict(self) -> dict:
        """Convert config to dict.
            
        Returns:
            dict: Returns config as dict.
        """
        return self._data

    def __repr__(self):
        """Generate string representation of config.
            
        Returns:
            str: String representation.
        """
        return f"<Config path={self._path}>\nstr({self._data})"
    
    def get_black_carbon_layer_width_in_levels(self) -> int:
        """Get the width of the black carbon layer in altitude levels.

        Returns:
            int: The black carbon layer width.
        """    
        return int(self["aerosol"]["bc_layer_width_levels"])
    
    def get_black_carbon_layer_distribution(self) -> Literal["gaussian", "uniform"]:
        """Get the value for the distribution type in the black carbon layer.

        Returns:
            str: Distribution type for the black carbon layer.
        """    
        return self["aerosol"]["bc_layer_distribution"]
    
    def get_black_carbon_mass(self) -> float:
        """Get the total black carbon mass.

        Returns:
            float: The black carbon mass.
        """    
        return self["aerosol"]["bc_mass"]
    
    def get_black_carbon_mass_extinction_coefficient(self) -> float:
        """Get the mass extinction coefficient of black carbon.

        Returns:
            float: The black carbon mass extinction coefficient.
        """    
        return self["aerosol"]["bc_mass_ext_coeff"]
    
    def get_black_carbon_decay_rate(self) -> float:
        """Get the decay rate for black carbon.

        Returns:
            float: The decay rate.
        """
        bc_e_folding_time = self["aerosol"]["bc_e_folding_time"]
        bc_decay_rate = 1 / bc_e_folding_time 

        return bc_decay_rate

    def get_black_carbon_single_scattering_albedo(self) -> float:
        """Get the single scattering albedo of black carbon.

        Returns:
            float: The ssa value.
        """    
        return self["aerosol"]["bc_ssa"]