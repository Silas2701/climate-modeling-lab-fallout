"""Config module to read in configuration from .toml files."""

from pathlib import Path
import sys
from typing import Any, Optional, Union

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
        """Load confg file.
        
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