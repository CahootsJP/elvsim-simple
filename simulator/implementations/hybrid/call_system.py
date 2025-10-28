"""
Hybrid Call System Implementations

Mix of Traditional (UP/DOWN buttons) and DCS (destination panels).
"""

from typing import List, Set
from simulator.interfaces.call_system import ICallSystem


class LobbyDCSCallSystem(ICallSystem):
    """
    Lobby floor has DCS, other floors have Traditional buttons
    
    This is a common configuration in modern buildings:
    - Ground floor (lobby): DCS panel for efficiency
    - Other floors: Traditional UP/DOWN buttons
    
    Usage:
        call_system = LobbyDCSCallSystem(num_floors=10, lobby_floor=1)
    """
    
    def __init__(self, num_floors: int, lobby_floor: int = 1):
        """
        Initialize lobby DCS call system
        
        Args:
            num_floors: Total number of floors
            lobby_floor: Floor number with DCS panel (default: 1)
        """
        self.num_floors = num_floors
        self.lobby_floor = lobby_floor
    
    def get_floor_call_type(self, floor: int) -> str:
        """Lobby uses DCS, others use Traditional"""
        if floor == self.lobby_floor:
            return 'DCS'
        else:
            return 'TRADITIONAL'
    
    def get_available_directions(self, floor: int) -> List[str]:
        """
        Lobby: No buttons (DCS panel)
        Others: UP/DOWN buttons based on floor position
        """
        if floor == self.lobby_floor:
            return []  # DCS, no direction buttons
        elif floor == 1 and self.lobby_floor != 1:
            return ['UP']  # Ground floor (if not lobby)
        elif floor == self.num_floors:
            return ['DOWN']  # Top floor
        else:
            return ['UP', 'DOWN']  # Middle floors
    
    def has_destination_panel(self, floor: int) -> bool:
        """Only lobby has destination panel"""
        return floor == self.lobby_floor
    
    def get_num_floors(self) -> int:
        """Return total number of floors"""
        return self.num_floors


class ZonedCallSystem(ICallSystem):
    """
    Zoned call system: Some floors DCS, others Traditional
    
    Flexible configuration for any combination of DCS/Traditional floors.
    
    Usage:
        # Low floors DCS, high floors Traditional
        call_system = ZonedCallSystem(
            num_floors=20,
            dcs_floors=[1, 2, 3, 4, 5]
        )
    """
    
    def __init__(self, num_floors: int, dcs_floors: List[int]):
        """
        Initialize zoned call system
        
        Args:
            num_floors: Total number of floors
            dcs_floors: List of floor numbers with DCS panels
        """
        self.num_floors = num_floors
        self.dcs_floors: Set[int] = set(dcs_floors)
    
    def get_floor_call_type(self, floor: int) -> str:
        """Check if floor is in DCS zone"""
        if floor in self.dcs_floors:
            return 'DCS'
        else:
            return 'TRADITIONAL'
    
    def get_available_directions(self, floor: int) -> List[str]:
        """
        DCS floors: No buttons
        Traditional floors: UP/DOWN buttons based on position
        """
        if floor in self.dcs_floors:
            return []  # DCS, no direction buttons
        elif floor == 1:
            return ['UP']  # Ground floor
        elif floor == self.num_floors:
            return ['DOWN']  # Top floor
        else:
            return ['UP', 'DOWN']  # Middle floors
    
    def has_destination_panel(self, floor: int) -> bool:
        """Check if floor has DCS panel"""
        return floor in self.dcs_floors
    
    def get_num_floors(self) -> int:
        """Return total number of floors"""
        return self.num_floors

