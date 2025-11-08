import simpy
from simulator.infrastructure.message_broker import MessageBroker
from simulator.core.elevator import Elevator
from .interfaces.allocation_strategy import IAllocationStrategy

class GroupControlSystem:
    """
    Group Control System that monitors each elevator's status in real-time
    
    This is a controller, not a simulated entity. It manages elevator allocation
    using pluggable allocation strategies.
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, 
                 strategy: IAllocationStrategy):
        self.env = env
        self.name = name
        self.broker = broker
        self.strategy = strategy  # Allocation strategy
        self.elevators = {}
        # Operation board to store the latest status of each elevator
        self.elevator_statuses = {}
        
        print(f"{self.env.now:.2f} [GCS] Using strategy: {self.strategy.get_strategy_name()}")
        
        # Start GCS process manually (not using Entity base class)
        self.process = self.env.process(self.run())

    def register_elevator(self, elevator: Elevator):
        """
        Register an elevator under GCS management and start monitoring its status
        """
        self.elevators[elevator.name] = elevator
        print(f"{self.env.now:.2f} [GCS] Elevator '{elevator.name}' registered.")
        # Start a dedicated status report listener for this elevator
        self.env.process(self._status_listener(elevator.name))

    def _status_listener(self, elevator_name: str):
        """Process that listens for status reports from a specific elevator"""
        status_topic = f"elevator/{elevator_name}/status"
        while True:
            status_message = yield self.broker.get(status_topic)
            self.elevator_statuses[elevator_name] = status_message
            
            # Log to confirm that GCS has understood the situation
            adv_pos = status_message.get('advanced_position')
            state = status_message.get('state')
            phys_pos = status_message.get('physical_floor')
            print(f"{self.env.now:.2f} [GCS] Status Update for {elevator_name}: Adv.Pos={adv_pos}F, State={state}, Phys.Pos={phys_pos}F")


    def run(self):
        """
        Main process of GCS. Listens for hall calls
        """
        print(f"{self.env.now:.2f} [GCS] GCS is operational. Waiting for hall calls...")
        
        hall_call_topic = 'gcs/hall_call'
        while True:
            message = yield self.broker.get(hall_call_topic)
            print(f"{self.env.now:.2f} [GCS] Received hall call: {message}")

            # Select the best elevator for this hall call using strategy
            if self.elevators:
                # Prepare call_data with additional context
                call_data = {
                    'floor': message['floor'],
                    'direction': message.get('direction'),
                    'destination': message.get('destination'),  # For DCS (future)
                    'call_type': 'TRADITIONAL',  # TODO: get from ICallSystem
                    'timestamp': self.env.now
                }
                
                # Delegate selection to strategy
                selected_elevator = self.strategy.select_elevator(call_data, self.elevator_statuses)
                
                task_message = {
                    "task_type": "ASSIGN_HALL_CALL",
                    "details": message
                }
                
                task_topic = f"elevator/{selected_elevator}/task"
                self.broker.put(task_topic, task_message)
                print(f"{self.env.now:.2f} [GCS] Assigned hall call to {selected_elevator}")
                
                # Broadcast assignment information for visualization
                assignment_message = {
                    "timestamp": self.env.now,
                    "floor": message['floor'],
                    "direction": message['direction'],
                    "assigned_elevator": selected_elevator
                }
                self.broker.put('gcs/hall_call_assignment', assignment_message)

