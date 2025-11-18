from abc import ABC, abstractmethod
from typing import List, Dict

class IRepositioningStrategy(ABC):
    """
    Interface for elevator repositioning strategies
    
    Repositioning strategies decide when and where to reposition idle elevators
    using move_command or forced_move_command. This allows different strategies
    for different building types, time periods, or traffic patterns.
    
    Examples:
        - Test strategies for verification
        - Lobby return strategy for office buildings
        - Floor distribution strategy for residential buildings
        - Peak-time optimization strategies
    """
    
    @abstractmethod
    def evaluate(self, elevator_name: str, status: dict, all_statuses: dict) -> List[dict]:
        """
        Evaluate if repositioning is needed for this elevator
        
        Called whenever an elevator's status is updated. The strategy examines
        the elevator's current state and decides if any repositioning commands
        should be issued.
        
        Args:
            elevator_name: Name of the elevator whose status was updated
            status: Current status of this elevator (includes state, floor, direction, etc.)
            all_statuses: Status dictionary of all elevators in the system
        
        Returns:
            List of command dictionaries. Empty list if no action needed.
            
            Command format:
            - Forced move: {'type': 'forced_move', 'elevator': 'Elevator_1', 'floor': 1, 'direction': 'UP'}
            - Move: {'type': 'move', 'elevator': 'Elevator_2', 'floor': 5}
        
        Note:
            This method is called event-driven (on every status update), so it should
            be efficient and avoid redundant command generation.
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Return strategy name for logging and identification
        
        Returns:
            Human-readable strategy name
        """
        pass

