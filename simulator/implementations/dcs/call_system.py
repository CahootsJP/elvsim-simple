"""
DCS (Destination Control System) Implementation

All floors have destination registration panels (no UP/DOWN buttons).
"""

from typing import List
from simulator.interfaces.call_system import ICallSystem


class FullDCSCallSystem(ICallSystem):
    """
    Full DCS call system
    
    All floors have destination registration panels.
    No UP/DOWN direction buttons.
    
    Passengers register their destination floor at a panel,
    and the system assigns them to a specific elevator.
    
    Usage:
        call_system = FullDCSCallSystem(num_floors=10)
    """
    
    def __init__(self, num_floors: int):
        """
        Initialize full DCS call system
        
        Args:
            num_floors: Total number of floors in the building
        """
        self.num_floors = num_floors
    
    def get_floor_call_type(self, floor: int) -> str:
        """All floors use DCS"""
        return 'DCS'
    
    def get_available_directions(self, floor: int) -> List[str]:
        """
        No direction buttons in DCS
        
        DCS uses destination panels instead of UP/DOWN buttons.
        """
        return []  # No direction buttons
    
    def has_destination_panel(self, floor: int) -> bool:
        """All floors have destination panels"""
        return True
    
    def get_num_floors(self) -> int:
        """Return total number of floors"""
        return self.num_floors
    
    def has_car_buttons(self) -> bool:
        """
        FULL DCS: No car buttons
        
        In FULL DCS, destinations are registered at hall panels,
        and car calls are automatically registered by photoelectric sensor.
        """
        return False

