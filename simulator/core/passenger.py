import simpy
from .entity import Entity
from ..infrastructure.message_broker import MessageBroker
from .hall_button import HallButton
from ..interfaces.call_system import ICallSystem
from ..interfaces.passenger_behavior import IPassengerBehavior
from .workflow_factory import WorkflowFactory

class Passenger(Entity):
    """
    Passenger who adapts to building's call system (Traditional or DCS)
    
    Design:
    - Uses ICallSystem to determine building's call method per floor
    - Uses IPassengerBehavior to make decisions
    - Workflow execution (SimPy processes) is handled here
    
    Supports:
    - Traditional: UP/DOWN buttons, any elevator
    - DCS: Destination panels, assigned elevator only
    - Hybrid: Mix of both depending on floor
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, 
                 hall_buttons, floor_queues, 
                 call_system: ICallSystem, behavior: IPassengerBehavior,
                 arrival_floor: int = None, destination_floor: int = None, move_speed: float = 1.0,
                 journeys: list = None):
        """
        Initialize passenger
        
        Args:
            env: SimPy environment
            name: Passenger name
            broker: Message broker
            hall_buttons: Hall buttons reference
            floor_queues: Floor queues reference
            call_system: Call system (ICallSystem)
            behavior: Passenger behavior (IPassengerBehavior)
            arrival_floor: First journey arrival floor (for backward compatibility)
            destination_floor: First journey destination floor (for backward compatibility)
            move_speed: Passenger move speed (seconds)
            journeys: List of journeys, each as dict with 'arrival_floor' and 'destination_floor'
                     If None, uses arrival_floor/destination_floor for single journey
        """
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        self.call_system = call_system  # Building's call system configuration
        self.behavior = behavior        # Passenger's decision logic
        
        # Create workflow factory
        self.workflow_factory = WorkflowFactory(call_system)
        
        # Support both single journey (backward compatibility) and multi-stop
        if journeys is not None:
            self.journeys = journeys
        elif arrival_floor is not None and destination_floor is not None:
            # Backward compatibility: single journey
            self.journeys = [{'arrival_floor': arrival_floor, 'destination_floor': destination_floor}]
        else:
            raise ValueError("Either journeys list or arrival_floor/destination_floor must be provided")
        
        # For backward compatibility, set first journey as arrival/destination
        if arrival_floor is None:
            self.arrival_floor = self.journeys[0]['arrival_floor']
        else:
            self.arrival_floor = arrival_floor
        
        if destination_floor is None:
            self.destination_floor = self.journeys[-1]['destination_floor']  # Final destination
        else:
            self.destination_floor = destination_floor
        
        self.move_speed = move_speed

        # To wait for permission from Door
        # Using Store allows receiving "completion reporting event" along with permission
        self.board_permission_event = simpy.Store(env, capacity=1)
        self.exit_permission_event = simpy.Store(env, capacity=1)
        
        # For boarding failure notification
        self.boarding_failed_event = simpy.Store(env, capacity=1)
        
        # Passenger metrics (self-tracking)
        self.waiting_start_time = None
        self.door_open_time = None       # Time when assigned elevator's door opened
        self.boarding_time = None
        self.alighting_time = None
        self.boarded_elevator_name = None
        
        # Print journey information
        if len(self.journeys) == 1:
            print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor} (Move time: {self.move_speed:.1f}s).")
        else:
            journey_str = " -> ".join([f"{j['arrival_floor']}F" for j in self.journeys] + [f"{self.journeys[-1]['destination_floor']}F"])
            print(f"{self.env.now:.2f} [{self.name}] Multi-stop journey: {journey_str} (Move time: {self.move_speed:.1f}s).")

    def is_front_of_queue(self, queue):
        """Check if this passenger is at the front of the queue"""
        if len(queue.items) == 0:
            return False
        return queue.items[0] == self

    def run(self):
        """
        Passenger's main process
        
        Executes all journeys sequentially using workflow strategy pattern.
        Each journey uses the appropriate workflow based on call system type at that floor.
        """
        yield self.env.timeout(1)
        
        # Execute each journey sequentially
        for journey_idx, journey in enumerate(self.journeys):
            arrival_floor = journey['arrival_floor']
            destination_floor = journey['destination_floor']
            
            if len(self.journeys) > 1:
                print(f"{self.env.now:.2f} [{self.name}] Starting journey {journey_idx + 1}/{len(self.journeys)}: {arrival_floor}F -> {destination_floor}F")
            
            # Get appropriate workflow for arrival floor
            workflow = self.workflow_factory.create_workflow(arrival_floor)
            
            # Execute workflow for this journey
            yield from workflow.execute(self, arrival_floor, destination_floor)
            
            # Reset metrics for next journey (except for final journey)
            if journey_idx < len(self.journeys) - 1:
                # Reset waiting/boarding metrics for next journey
                # Keep alighting_time as it represents the end of current journey
                self.waiting_start_time = None
                self.door_open_time = None
                self.boarding_time = None
                self.boarded_elevator_name = None
                
                # Small delay between journeys (passenger moves to next floor)
                yield self.env.timeout(0.5)
        
        if len(self.journeys) > 1:
            print(f"{self.env.now:.2f} [{self.name}] All journeys complete.")
    
    
    # ========================================
    # Passenger Metrics Methods (Self-tracking)
    # ========================================
    
    def get_waiting_time_to_boarding(self):
        """
        Get waiting time from hall arrival to boarding completion.
        
        Returns:
            float: Waiting time in seconds, or None if not applicable
        """
        if self.waiting_start_time is not None and self.boarding_time is not None:
            return self.boarding_time - self.waiting_start_time
        return None
    
    def get_waiting_time_to_door_open(self):
        """
        Get waiting time from hall arrival to door opening.
        
        Special cases:
        - If door was already open when passenger arrived, returns 0
        - If passenger boarded immediately (no wait), returns 0
        
        Returns:
            float: Waiting time in seconds, or None if not applicable
        """
        if self.waiting_start_time is None or self.door_open_time is None:
            return None
        
        # Calculate wait time
        wait_time = self.door_open_time - self.waiting_start_time
        
        # If door opened before passenger arrived (or at same time), return 0
        # This means the door was already open when the passenger arrived
        return max(0, wait_time)
    
    def get_riding_time(self):
        """
        Get riding time from boarding to alighting.
        
        Returns:
            float: Riding time in seconds, or None if not applicable
        """
        if self.boarding_time is not None and self.alighting_time is not None:
            return self.alighting_time - self.boarding_time
        return None
    
    def get_total_journey_time(self):
        """
        Get total journey time from hall arrival to alighting.
        
        Returns:
            float: Total time in seconds, or None if not applicable
        """
        if self.waiting_start_time is not None and self.alighting_time is not None:
            return self.alighting_time - self.waiting_start_time
        return None

