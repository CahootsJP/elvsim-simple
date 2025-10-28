"""
Allocation Strategy Interface

Defines how elevators are selected for hall calls.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class IAllocationStrategy(ABC):
    """
    Interface for elevator allocation strategies
    
    Defines how to select the best elevator for a given hall call.
    
    Design Philosophy:
    - Equipment-agnostic (works with Traditional/DCS/Hybrid)
    - Elevator-type aware (can handle standard/double-deck)
    - Algorithm decides optimization based on call_data
    
    Usage Examples:
    - NearestCar: Simple distance-based selection
    - ACA: Advanced algorithm for Traditional/DCS
    - DoubleDeKACA: Optimized for double-deck elevators
    """
    
    @abstractmethod
    def select_elevator(
        self, 
        call_data: Dict[str, Any],
        elevator_statuses: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Select the best elevator for a hall call
        
        Args:
            call_data: Hall call information
                {
                    'floor': int,              # Call floor
                    'direction': str,          # 'UP' or 'DOWN' (Traditional)
                    'destination': int,        # Destination floor (DCS)
                    'call_type': str,          # 'TRADITIONAL' or 'DCS'
                    'timestamp': float         # Simulation time
                }
            
            elevator_statuses: Current status of all elevators
                {
                    'Elevator_1': {
                        'floor': int,              # Current floor
                        'advanced_position': int,  # Virtual position
                        'state': str,              # 'IDLE', 'UP', 'DOWN'
                        'passengers': int,         # Current passenger count
                        'max_capacity': int,
                        'hall_calls_up': List[int],
                        'hall_calls_down': List[int],
                        'type': str,               # 'STANDARD' or 'DOUBLE_DECK' (future)
                        ...
                    },
                    ...
                }
        
        Returns:
            str: Name of selected elevator (e.g., 'Elevator_1')
        
        Design Notes:
            - Algorithm can use call_type to apply different logic:
              * Traditional: optimize for direction and distance
              * DCS: optimize using destination information
            
            - Algorithm can detect elevator_type:
              * Standard: normal single-car logic
              * DoubleDeck: optimize upper/lower car simultaneously
            
            - Must return a valid elevator name from elevator_statuses keys
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """
        Get the name of this strategy
        
        Returns:
            str: Strategy name (for logging and debugging)
        
        Examples:
            - "Nearest Car (Distance-based)"
            - "ACA (Advanced Control Algorithm)"
            - "DoubleDeck ACA"
        """
        pass

