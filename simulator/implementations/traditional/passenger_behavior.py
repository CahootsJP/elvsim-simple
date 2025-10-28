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
    
    def should_board_elevator(self, passenger, permission_data: dict) -> bool:
        """
        Accept all boarding permissions in traditional mode
        
        Traditional passengers board any elevator that opens at their floor.
        No elevator assignment, so accept all permissions.
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
    
    def should_board_elevator(self, passenger, permission_data: dict) -> bool:
        """
        Board elevator based on assignment (if any)
        
        Traditional floor:
            - Accept all elevators (no assignment)
        
        DCS floor:
            - Only board assigned elevator
        """
        # If no elevator is assigned (Traditional), accept all
        assigned = self.get_assigned_elevator(passenger)
        if assigned is None:
            return True
        
        # If assigned (DCS), only board the assigned elevator
        elevator_name = permission_data.get('elevator_name')
        return elevator_name == assigned

