"""
Passenger Workflow Interface

Defines how passengers execute their journey workflow based on call system type.
"""

from abc import ABC, abstractmethod
from typing import Generator


class IPassengerWorkflow(ABC):
    """
    Interface for passenger workflow execution
    
    Separates workflow execution from passenger entity management.
    Each workflow type (Traditional, DCS) implements this interface.
    
    Design Philosophy:
    - Workflow execution (SimPy processes) is handled here
    - Passenger class manages entity state and metrics
    - Pluggable (easy to add new workflow types)
    
    Usage Examples:
    - TraditionalWorkflow: UP/DOWN buttons, any elevator
    - DCSWorkflow: Destination panels, assigned elevator only
    - VIPWorkflow: Special handling for VIP passengers (future)
    """
    
    @abstractmethod
    def execute(self, passenger, arrival_floor: int, destination_floor: int) -> Generator:
        """
        Execute the workflow for a passenger journey
        
        Args:
            passenger: Passenger object (for accessing broker, behavior, etc.)
            arrival_floor: Floor where passenger starts waiting
            destination_floor: Floor where passenger wants to go
        
        Yields:
            SimPy events (timeout, get, put, etc.)
        
        Note:
            This is a generator function that yields SimPy events.
            It should be called with `yield from workflow.execute(...)`.
        """
        pass

