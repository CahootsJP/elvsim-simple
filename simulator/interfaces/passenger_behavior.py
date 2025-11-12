"""
Passenger Behavior Interface

Defines how passengers make decisions in different situations.
"""

from abc import ABC, abstractmethod
from typing import Optional


class IPassengerBehavior(ABC):
    """
    Interface for passenger decision-making logic
    
    Separates "decision logic" from "workflow execution".
    The Passenger class handles the workflow (SimPy processes),
    while this interface defines the decision rules.
    
    Design Philosophy:
    - Pure decision functions (no SimPy yield)
    - Stateless (decisions based on current state only)
    - Pluggable (easy to swap different behaviors)
    
    Usage Examples:
    - Default behavior: Press button when at front of queue
    - Aggressive behavior: Always press button if it's off
    - VIP behavior: Board assigned elevator only
    """
    
    # ========================================
    # Traditional Call System Methods
    # ========================================
    
    @abstractmethod
    def should_press_button(self, passenger, button, queue) -> bool:
        """
        Decide whether to press the hall button (Traditional only)
        
        Args:
            passenger: Passenger object
            button: HallButton object
            queue: Current waiting queue (simpy.Store)
        
        Returns:
            True if the passenger should press the button
            False otherwise
        
        Example Implementations:
            Polling strategy:
                - Return True if at front of queue AND button is off
            
            Aggressive strategy:
                - Return True if button is off (regardless of position)
        
        Note:
            This method is only called at Traditional floors.
            DCS floors do not have hall buttons.
        """
        pass
    
    @abstractmethod
    def get_check_interval(self) -> float:
        """
        Get the interval for checking button state (seconds)
        
        Returns:
            Check interval in seconds
        
        Example Values:
            Fast polling: 0.1 seconds
            Normal polling: 0.5 seconds
            Slow polling: 1.0 seconds
        
        Trade-off:
            Shorter interval = More responsive but higher CPU overhead
            Longer interval = Less responsive but lower CPU overhead
        """
        pass
    
    # ========================================
    # DCS Call System Methods
    # ========================================
    
    @abstractmethod
    def get_destination_for_dcs(self, passenger) -> int:
        """
        Get the destination floor to register at DCS panel
        
        Args:
            passenger: Passenger object
        
        Returns:
            Destination floor number
        
        Example Implementations:
            Normal passenger:
                - Return passenger.destination_floor
            
            Multi-stop passenger:
                - Return intermediate floor (e.g., for delivery)
        
        Note:
            This method is only called at DCS floors.
        """
        pass
    
    @abstractmethod
    def on_elevator_assigned(self, passenger, elevator_name: str) -> None:
        """
        Handle elevator assignment notification (DCS only)
        
        Args:
            passenger: Passenger object
            elevator_name: Name of assigned elevator (e.g., 'Elevator_1')
        
        Behavior:
            Store the assigned elevator name in the passenger object
            so that it can be checked in should_board_elevator()
        
        Note:
            This method is only called at DCS floors after registration.
        """
        pass
    
    @abstractmethod
    def get_assigned_elevator(self, passenger) -> Optional[str]:
        """
        Get the name of the assigned elevator (DCS only)
        
        Args:
            passenger: Passenger object
        
        Returns:
            Assigned elevator name (e.g., 'Elevator_1')
            None if no elevator is assigned yet
        
        Note:
            Used to determine which elevator to board at DCS floors.
        """
        pass
    
    # ========================================
    # Common Methods (Both Traditional and DCS)
    # ========================================
    
    @abstractmethod
    def select_best_elevator(self, passenger, available_permissions: list) -> dict:
        """
        Select the best elevator from multiple available options
        
        Args:
            passenger: Passenger object
            available_permissions: List of permission_data dicts, each containing:
                {
                    'elevator_name': str,
                    'completion_event': simpy.Event,
                    'door_open_time': float,
                    'passengers_count': int
                }
        
        Returns:
            The selected permission_data dict (from available_permissions list)
            None if all elevators should be rejected
        
        Example Implementations:
            Traditional:
                - Priority 1: Select elevator with fewest passengers
                - Priority 2: Select elevator that opened door first
            
            DCS:
                - Select only the assigned elevator
            
            VIP:
                - Select VIP-designated elevators only
        
        Note:
            This method is called when 1 or more elevators have opened doors.
            For single elevator, the decision is straightforward.
            For multiple elevators, apply selection strategy.
        """
        pass
    
    @abstractmethod
    def should_board_elevator(self, passenger, permission_data: dict) -> bool:
        """
        Decide whether to accept boarding permission
        
        DEPRECATED: This method is kept for backward compatibility.
        New implementations should use select_best_elevator() instead.
        
        Args:
            passenger: Passenger object
            permission_data: {
                'elevator_name': str,
                'completion_event': simpy.Event
            }
        
        Returns:
            True if the passenger should board
            False if the passenger should wait for another elevator
        """
        pass

