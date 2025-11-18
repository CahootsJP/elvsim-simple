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
            direction = status.get('direction', 'NO_DIRECTION')
            passengers = status.get('passengers', 0)
            max_capacity = status.get('max_capacity', 10)
            
            # Use advanced_position as virtual floor (GCS already calculates this)
            virtual_floor = advanced_position
            
            # Calculate real distance considering circular movement
            distance = self._calculate_circular_distance(
                virtual_floor, state, direction, call_floor, call_direction
            )
            
            # Penalty if elevator is full
            if passengers >= max_capacity:
                distance += 1000  # Large penalty
            
            # Select elevator with lowest score (shortest travel distance)
            if distance < best_score:
                best_score = distance
                best_elevator = elev_name
            
            # Debug output
            print(f"[GCS] {elev_name}: VirtualFloor={virtual_floor}, State={state}, Direction={direction}, Distance={distance:.1f}")
        
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
        direction: str,
        call_floor: int, 
        call_direction: str
    ) -> float:
        """
        Calculate travel distance considering circular elevator movement
        
        Circular Movement Logic:
        - UP elevator: Continues to top floor, then reverses to DOWN
        - DOWN elevator: Continues to floor 1, then reverses to UP
        - IDLE/NO_DIRECTION: Simple distance
        
        Args:
            virtual_floor: Virtual position of elevator
            state: Elevator state (IDLE/MOVING/DECELERATING/STOPPING)
            direction: Elevator direction (UP/DOWN/NO_DIRECTION)
            call_floor: Floor where hall call was made
            call_direction: Direction of hall call (UP/DOWN)
        
        Returns:
            Estimated travel distance in floors
        """
        
        # If elevator has no direction (IDLE or just finished), use simple distance
        if direction == 'NO_DIRECTION':
            return abs(call_floor - virtual_floor)
        
        elif direction == 'UP':
            # Elevator is moving UP
            if call_direction == 'UP' and call_floor > virtual_floor:
                # Same direction, call is AHEAD of elevator -> can pick up on the way
                return call_floor - virtual_floor
            else:
                # Call is BEHIND elevator (or opposite direction)
                # Must complete circular journey: current -> top -> call_floor
                distance_to_top = (self.num_floors - virtual_floor)
                distance_from_top = (self.num_floors - call_floor)
                return distance_to_top + distance_from_top
        
        elif direction == 'DOWN':
            # Elevator is moving DOWN
            if call_direction == 'DOWN' and call_floor < virtual_floor:
                # Same direction, call is AHEAD of elevator -> can pick up on the way
                return virtual_floor - call_floor
            else:
                # Call is BEHIND elevator (or opposite direction)
                # Must complete circular journey: current -> bottom -> call_floor
                distance_to_bottom = (virtual_floor - 1)
                distance_from_bottom = (call_floor - 1)
                return distance_to_bottom + distance_from_bottom
        
        # Fallback
        return abs(call_floor - virtual_floor)
    
    def get_strategy_name(self) -> str:
        """Return strategy name"""
        return "Nearest Car (Circular Distance-based)"

