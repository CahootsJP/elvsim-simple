"""
Nearest Car Strategy

Simple distance-based elevator allocation algorithm.
Extracted from the original GroupControlSystem implementation.
"""

from typing import Dict, Any
from ..interfaces.allocation_strategy import IAllocationStrategy


class NearestCarStrategy(IAllocationStrategy):
    """
    Nearest car allocation strategy
    
    Selection Logic:
    - IDLE elevators: Simple distance calculation
    - Moving elevators: Consider circular movement
      * UP: Goes to top floor, then reverses to DOWN
      * DOWN: Goes to floor 1, then reverses to UP
    - Door state consideration: Closing/closed door means virtual position is next floor
    - Capacity penalty: Full elevators get large distance penalty
    
    Equipment Support:
    - Traditional: ✅ (current implementation)
    - DCS: ✅ (ignores destination information, treats as Traditional)
    - DoubleDeck: ❌ (future enhancement)
    
    Usage:
        strategy = NearestCarStrategy()
        selected = strategy.select_elevator(call_data, elevator_statuses)
    """
    
    def __init__(self, num_floors: int = 10):
        """
        Initialize strategy
        
        Args:
            num_floors: Total number of floors in the building
        """
        self.num_floors = num_floors
    
    def select_elevator(
        self, 
        call_data: Dict[str, Any],
        elevator_statuses: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Select the nearest available elevator
        
        Args:
            call_data: Hall call information
            elevator_statuses: Current status of all elevators
        
        Returns:
            Name of selected elevator
        """
        call_floor = call_data['floor']
        call_direction = call_data.get('direction', 'UP')  # Default to UP if not specified (DCS case)
        
        best_elevator = None
        best_score = float('inf')
        
        for elev_name, status in elevator_statuses.items():
            if not status:
                continue
            
            physical_floor = status.get('physical_floor', 1)
            advanced_position = status.get('advanced_position', physical_floor)
            state = status.get('state', 'IDLE')
            passengers = status.get('passengers', 0)
            max_capacity = status.get('max_capacity', 10)
            
            # Use advanced_position as virtual floor (GCS already calculates this)
            virtual_floor = advanced_position
            
            # Calculate real distance considering circular movement
            distance = self._calculate_circular_distance(
                virtual_floor, state, call_floor, call_direction
            )
            
            # Penalty if elevator is full
            if passengers >= max_capacity:
                distance += 1000  # Large penalty
            
            # Select elevator with lowest score (shortest travel distance)
            if distance < best_score:
                best_score = distance
                best_elevator = elev_name
            
            # Debug output
            print(f"[GCS] {elev_name}: VirtualFloor={virtual_floor}, State={state}, Distance={distance:.1f}")
        
        # Fallback to first elevator if no valid selection
        if best_elevator is None and elevator_statuses:
            best_elevator = list(elevator_statuses.keys())[0]
        
        if best_elevator:
            print(f"[GCS] Selected {best_elevator} with distance={best_score:.1f}")
        
        return best_elevator
    
    def _calculate_circular_distance(
        self, 
        virtual_floor: int, 
        state: str, 
        call_floor: int, 
        call_direction: str
    ) -> float:
        """
        Calculate travel distance considering circular elevator movement
        
        Circular Movement Logic:
        - UP elevator: Continues to top floor, then reverses to DOWN
        - DOWN elevator: Continues to floor 1, then reverses to UP
        - IDLE elevator: Direct distance
        
        Args:
            virtual_floor: Virtual position of elevator
            state: Elevator state (UP/DOWN/IDLE)
            call_floor: Floor where hall call was made
            call_direction: Direction of hall call (UP/DOWN)
        
        Returns:
            Estimated travel distance in floors
        """
        
        if state == 'IDLE':
            # IDLE: Simple distance
            return abs(call_floor - virtual_floor)
        
        elif state == 'UP':
            # Moving UP
            if call_direction == 'UP' and call_floor >= virtual_floor:
                # Same direction, ahead of elevator -> can pick up on the way
                return call_floor - virtual_floor
            else:
                # Need to complete UP journey, then reverse
                # Distance = (to top) + (from top to call floor)
                distance = (self.num_floors - virtual_floor)  # To top floor
                distance += (self.num_floors - call_floor)     # From top floor down to call floor
                return distance
        
        elif state == 'DOWN':
            # Moving DOWN
            if call_direction == 'DOWN' and call_floor <= virtual_floor:
                # Same direction, ahead of elevator -> can pick up on the way
                return virtual_floor - call_floor
            else:
                # Need to complete DOWN journey, then reverse
                # Distance = (to bottom) + (from bottom to call floor)
                distance = (virtual_floor - 1)      # To floor 1
                distance += (call_floor - 1)        # From floor 1 up to call floor
                return distance
        
        # Fallback
        return abs(call_floor - virtual_floor)
    
    def get_strategy_name(self) -> str:
        """Return strategy name"""
        return "Nearest Car (Circular Distance-based)"

