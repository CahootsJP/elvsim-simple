"""
Traditional Passenger Behavior Implementation

Current implementation logic extracted from Passenger.py
"""

from typing import Optional
from simulator.interfaces.passenger_behavior import IPassengerBehavior


class TraditionalPassengerBehavior(IPassengerBehavior):
    """
    Default behavior for traditional elevator systems
    
    Decision Logic:
    - Press button only when at front of queue AND button is OFF
    - Check button state every 0.1 seconds (fast polling)
    - Accept all elevator boarding permissions
    
    Usage:
        behavior = TraditionalPassengerBehavior()
    """
    
    def __init__(self):
        """Initialize traditional passenger behavior"""
        # DCS-related attributes (not used in traditional mode)
        self._assigned_elevator = None
    
    # ========================================
    # Traditional Methods
    # ========================================
    
    def should_press_button(self, passenger, button, queue) -> bool:
        """
        Press button only when at front of queue AND button is OFF
        
        This is the current implementation logic:
        - Prevents multiple passengers from pressing the same button
        - Ensures button is only pressed when needed
        """
        # Check if this passenger is at the front of the queue
        is_front = len(queue.items) > 0 and queue.items[0] == passenger
        
        # Press button only if at front AND button is OFF
        return is_front and not button.is_lit()
    
    def get_check_interval(self) -> float:
        """
        Check button state every 0.1 seconds
        
        This is the current CHECK_INTERVAL value.
        Fast polling provides responsive button press behavior.
        """
        return 0.1
    
    # ========================================
    # DCS Methods (Not used in Traditional, but required by interface)
    # ========================================
    
    def get_destination_for_dcs(self, passenger) -> int:
        """
        DCS not used in traditional mode
        
        Returns passenger's destination floor as default.
        """
        return passenger.destination_floor
    
    def on_elevator_assigned(self, passenger, elevator_name: str) -> None:
        """
        DCS not used in traditional mode
        
        Store assignment anyway (for potential future hybrid use).
        """
        self._assigned_elevator = elevator_name
    
    def get_assigned_elevator(self, passenger) -> Optional[str]:
        """
        DCS not used in traditional mode
        
        Returns None in traditional mode (no assignment).
        """
        return self._assigned_elevator
    
    # ========================================
    # Common Methods
    # ========================================
    
    def select_best_elevator(self, passenger, available_permissions: list) -> dict:
        """
        Select the best elevator from available options
        
        Priority 1: Fewest passengers (空いている方)
        Priority 2: Earliest door open time (早く到着した方)
        """
        if not available_permissions:
            return None
        
        if len(available_permissions) == 1:
            # Only one elevator - board immediately
            return available_permissions[0]
        
        # Multiple elevators - apply selection strategy
        # Priority 1: Fewest passengers
        min_passengers = min(p.get('passengers_count', 0) for p in available_permissions)
        candidates = [p for p in available_permissions if p.get('passengers_count', 0) == min_passengers]
        
        # Priority 2: Earliest door open time
        selected = min(candidates, key=lambda p: p.get('door_open_time', float('inf')))
        
        return selected
    
    def should_board_elevator(self, passenger, permission_data: dict) -> bool:
        """
        DEPRECATED: Kept for backward compatibility
        
        Accept all boarding permissions in traditional mode.
        """
        return True


class AdaptivePassengerBehavior(TraditionalPassengerBehavior):
    """
    Adaptive passenger that works with both Traditional and DCS
    
    Inherits traditional behavior but also supports DCS assignment.
    This is the recommended behavior for hybrid systems.
    
    Usage:
        behavior = AdaptivePassengerBehavior()
    """
    
    def select_best_elevator(self, passenger, available_permissions: list) -> dict:
        """
        Select the best elevator considering DCS assignment
        
        If DCS assignment exists, only select the assigned elevator.
        Otherwise, use traditional selection strategy.
        """
        # Check for DCS assignment
        assigned = self.get_assigned_elevator(passenger)
        if assigned is not None:
            # Only select the assigned elevator
            for perm in available_permissions:
                if perm.get('elevator_name') == assigned:
                    return perm
            # Assigned elevator not available
            return None
        
        # No DCS assignment - use traditional selection
        return super().select_best_elevator(passenger, available_permissions)

