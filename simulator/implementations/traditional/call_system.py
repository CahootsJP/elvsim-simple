"""
Traditional Call System Implementation

All floors have UP/DOWN buttons (no destination panels).
"""

from typing import List
from simulator.interfaces.call_system import ICallSystem


class TraditionalCallSystem(ICallSystem):
    """
    Traditional elevator call system
    
    All floors have UP/DOWN direction buttons.
    No destination registration panels.
    
    Usage:
        call_system = TraditionalCallSystem(num_floors=10)
    """
    
    def __init__(self, num_floors: int):
        """
        Initialize traditional call system
        
        Args:
            num_floors: Total number of floors in the building
        """
        self.num_floors = num_floors
    
    def get_floor_call_type(self, floor: int) -> str:
        """All floors use traditional UP/DOWN buttons"""
        return 'TRADITIONAL'
    
    def get_available_directions(self, floor: int) -> List[str]:
        """
        Get available direction buttons at each floor
        
        Ground floor: UP only
        Top floor: DOWN only
        Middle floors: UP and DOWN
        """
        if floor == 1:
            # Ground floor: only UP button
            return ['UP']
        elif floor == self.num_floors:
            # Top floor: only DOWN button
            return ['DOWN']
        else:
            # Middle floors: both buttons
            return ['UP', 'DOWN']
    
    def has_destination_panel(self, floor: int) -> bool:
        """Traditional system has no destination panels"""
        return False
    
    def get_num_floors(self) -> int:
        """Return total number of floors"""
        return self.num_floors

