"""
Configuration loader utility

Loads GroupControlConfig and SimulationConfig from YAML files.
"""

import yaml
from pathlib import Path
from typing import Union

from .group_control import GroupControlConfig
from .simulation import SimulationConfig


class ConfigLoader:
    """Utility class for loading configuration files"""
    
    @staticmethod
    def load_group_control(file_path: Union[str, Path]) -> GroupControlConfig:
        """
        Load GroupControlConfig from YAML file
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            GroupControlConfig instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If validation fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = GroupControlConfig.from_dict(data)
        config.validate()
        
        return config
    
    @staticmethod
    def load_simulation(file_path: Union[str, Path]) -> SimulationConfig:
        """
        Load SimulationConfig from YAML file
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            SimulationConfig instance
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If validation fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        config = SimulationConfig.from_dict(data)
        config.validate()
        
        return config
    
    @staticmethod
    def save_group_control(config: GroupControlConfig, file_path: Union[str, Path]):
        """
        Save GroupControlConfig to YAML file
        
        Args:
            config: GroupControlConfig instance
            file_path: Path to save YAML file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = config.to_dict()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    @staticmethod
    def save_simulation(config: SimulationConfig, file_path: Union[str, Path]):
        """
        Save SimulationConfig to YAML file
        
        Args:
            config: SimulationConfig instance
            file_path: Path to save YAML file
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = config.to_dict()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# Convenience functions
def load_group_control_config(file_path: Union[str, Path]) -> GroupControlConfig:
    """Load GroupControlConfig from YAML file"""
    return ConfigLoader.load_group_control(file_path)


def load_simulation_config(file_path: Union[str, Path]) -> SimulationConfig:
    """Load SimulationConfig from YAML file"""
    return ConfigLoader.load_simulation(file_path)


def save_group_control_config(config: GroupControlConfig, file_path: Union[str, Path]):
    """Save GroupControlConfig to YAML file"""
    ConfigLoader.save_group_control(config, file_path)


def save_simulation_config(config: SimulationConfig, file_path: Union[str, Path]):
    """Save SimulationConfig to YAML file"""
    ConfigLoader.save_simulation(config, file_path)

