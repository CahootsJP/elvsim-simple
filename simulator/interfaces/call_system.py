"""
Call System Interface

Defines how passengers call elevators in different building configurations.
"""

from abc import ABC, abstractmethod
from typing import List


class ICallSystem(ABC):
    """
    Interface for elevator call systems
    
    Defines which floors use which call methods (Traditional vs DCS).
    This represents the physical equipment installed in the building.
    
    Design Philosophy:
    - Building-level configuration (not passenger behavior)
    - Determines available interfaces at each floor
    - Supports hybrid systems (mixed Traditional/DCS)
    
    Usage Examples:
    - Traditional: All floors have UP/DOWN buttons
    - Full DCS: All floors have destination panels
    - Hybrid: Lobby has DCS, other floors have buttons
    """
    
    @abstractmethod
    def get_floor_call_type(self, floor: int) -> str:
        """
        Get the call system type for a specific floor
        
        Args:
            floor: Floor number
        
        Returns:
            'TRADITIONAL' - UP/DOWN buttons
            'DCS' - Destination Control System (destination panel)
        
        Example:
            Lobby DCS system:
                floor 1 -> 'DCS'
                floor 2-10 -> 'TRADITIONAL'
        """
        pass
    
    @abstractmethod
    def get_available_directions(self, floor: int) -> List[str]:
        """
        Get available direction buttons at a specific floor
        
        Args:
            floor: Floor number
        
        Returns:
            Traditional floors: ['UP', 'DOWN'] or ['UP'] or ['DOWN']
            DCS floors: [] (no direction buttons)
        
        Example:
            10-floor building:
                floor 1 -> ['UP']         # Ground floor, only UP
                floor 2-9 -> ['UP', 'DOWN']
                floor 10 -> ['DOWN']       # Top floor, only DOWN
        """
        pass
    
    @abstractmethod
    def has_destination_panel(self, floor: int) -> bool:
        """
        Check if a floor has a destination registration panel
        
        Args:
            floor: Floor number
        
        Returns:
            True if the floor has a DCS panel
            False if the floor uses traditional buttons
        
        Example:
            Lobby DCS system:
                floor 1 -> True   # DCS panel
                floor 2-10 -> False
        """
        pass
    
    @abstractmethod
    def get_num_floors(self) -> int:
        """
        Get the total number of floors in the building
        
        Returns:
            Total number of floors
        """
        pass
    
    def is_dcs_floor(self, floor: int) -> bool:
        """
        Check if a floor uses DCS (Destination Control System)
        
        Default implementation uses get_floor_call_type().
        Can be overridden for performance optimization.
        
        Args:
            floor: Floor number
        
        Returns:
            True if the floor uses DCS, False if Traditional
        """
        return self.get_floor_call_type(floor) == 'DCS'
    
    def has_car_buttons(self) -> bool:
        """
        Check if elevators have car buttons (destination buttons inside elevator)
        
        FULL DCS: No car buttons (destinations registered at hall panel)
        Hybrid DCS: Has car buttons (for traditional floors)
        Traditional: Has car buttons
        
        Default implementation: Returns True (assumes car buttons exist)
        Override in FullDCSCallSystem to return False
        
        Returns:
            True if elevators have car buttons, False otherwise
        """
        return True

