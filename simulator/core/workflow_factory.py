"""
Workflow Factory

Creates appropriate workflow instances based on call system type.
"""

from simulator.interfaces.passenger_workflow import IPassengerWorkflow
from simulator.interfaces.call_system import ICallSystem
from simulator.implementations.traditional.workflow import TraditionalWorkflow
from simulator.implementations.dcs.workflow import DCSWorkflow


class WorkflowFactory:
    """
    Factory for creating passenger workflows
    
    Determines the appropriate workflow based on call system type at a specific floor.
    
    Usage:
        factory = WorkflowFactory(call_system)
        workflow = factory.create_workflow(floor)
        yield from workflow.execute(passenger, arrival_floor, destination_floor)
    """
    
    def __init__(self, call_system: ICallSystem):
        """
        Initialize workflow factory
        
        Args:
            call_system: ICallSystem instance to determine call type per floor
        """
        self.call_system = call_system
        self._workflow_cache = {}  # Cache workflow instances by call type
    
    def create_workflow(self, floor: int) -> IPassengerWorkflow:
        """
        Create workflow instance for a specific floor
        
        Args:
            floor: Floor number to determine call system type
        
        Returns:
            IPassengerWorkflow instance (TraditionalWorkflow or DCSWorkflow)
        """
        call_type = self.call_system.get_floor_call_type(floor)
        
        # Use cache to avoid creating multiple instances
        if call_type not in self._workflow_cache:
            if call_type == 'TRADITIONAL':
                self._workflow_cache[call_type] = TraditionalWorkflow()
            elif call_type == 'DCS':
                self._workflow_cache[call_type] = DCSWorkflow()
            else:
                raise ValueError(f"Unknown call type: {call_type}")
        
        return self._workflow_cache[call_type]

