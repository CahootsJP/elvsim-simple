"""
Building - Defines floor structure and properties

This module provides the Building class which manages:
- Floor definitions (control floor numbers, display names, heights)
- Floor number to display name mapping
- Building-wide floor constraints
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class FloorDefinition:
    """
    Defines a single floor in the building.
    
    Attributes:
        control_floor: Internal floor number (positive integer starting from 1)
        display_name: Human-readable floor name (e.g., "B1", "L", "2F", "R")
        floor_height: Height of this floor in meters
    """
    control_floor: int
    display_name: str
    floor_height: float = 3.5
    
    def __post_init__(self):
        if self.control_floor < 1:
            raise ValueError(f"control_floor must be >= 1, got {self.control_floor}")


class Building:
    """
    Represents a building with defined floors.
    
    Manages floor definitions and provides mapping between control floor numbers
    and display names.
    """
    
    def __init__(self, floors: List[FloorDefinition]):
        """
        Initialize building with floor definitions.
        
        Args:
            floors: List of FloorDefinition objects
        """
        if not floors:
            raise ValueError("Building must have at least one floor")
        
        self.floors = sorted(floors, key=lambda f: f.control_floor)
        
        # Validate control floor numbers are sequential
        expected_floor = 1
        for floor in self.floors:
            if floor.control_floor != expected_floor:
                raise ValueError(
                    f"Floor control numbers must be sequential starting from 1. "
                    f"Expected {expected_floor}, got {floor.control_floor}"
                )
            expected_floor += 1
        
        # Create mappings
        self._control_to_display: Dict[int, str] = {
            f.control_floor: f.display_name for f in self.floors
        }
        self._display_to_control: Dict[str, int] = {
            f.display_name: f.control_floor for f in self.floors
        }
        self._control_to_height: Dict[int, float] = {
            f.control_floor: f.floor_height for f in self.floors
        }
        
        self.num_floors = len(self.floors)
        self.all_floors = [f.control_floor for f in self.floors]
        self.min_floor = self.all_floors[0]
        self.max_floor = self.all_floors[-1]
    
    def get_display_name(self, control_floor: int) -> str:
        """
        Get display name for a control floor number.
        
        Args:
            control_floor: Control floor number
            
        Returns:
            Display name (e.g., "B1", "L", "5F")
            
        Raises:
            ValueError: If control_floor is not valid
        """
        if control_floor not in self._control_to_display:
            raise ValueError(f"Invalid control floor: {control_floor}")
        return self._control_to_display[control_floor]
    
    def get_control_floor(self, display_name: str) -> int:
        """
        Get control floor number from display name.
        
        Args:
            display_name: Display name (e.g., "B1", "L", "5F")
            
        Returns:
            Control floor number
            
        Raises:
            ValueError: If display_name is not found
        """
        if display_name not in self._display_to_control:
            raise ValueError(f"Invalid display name: {display_name}")
        return self._display_to_control[display_name]
    
    def get_floor_height(self, control_floor: int) -> float:
        """
        Get floor height for a control floor number.
        
        Args:
            control_floor: Control floor number
            
        Returns:
            Floor height in meters
            
        Raises:
            ValueError: If control_floor is not valid
        """
        if control_floor not in self._control_to_height:
            raise ValueError(f"Invalid control floor: {control_floor}")
        return self._control_to_height[control_floor]
    
    def is_valid_floor(self, control_floor: int) -> bool:
        """
        Check if a control floor number is valid in this building.
        
        Args:
            control_floor: Control floor number to check
            
        Returns:
            True if valid, False otherwise
        """
        return control_floor in self._control_to_display
    
    def __repr__(self) -> str:
        return f"Building(floors={self.num_floors}, range={self.min_floor}-{self.max_floor})"

