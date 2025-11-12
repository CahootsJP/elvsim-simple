from simulator.infrastructure.message_broker import MessageBroker
from simulator.core.elevator import Elevator
from .interfaces.allocation_strategy import IAllocationStrategy
from .interfaces.repositioning_strategy import IRepositioningStrategy

class GroupControlSystem:
    """
    Group Control System that monitors each elevator's status in real-time
    
    This is a controller, not a simulated entity. It manages elevator allocation
    using pluggable allocation strategies and repositioning strategies.
    
    Architecture: GCS is completely independent from simulator. All communication
    happens through MessageBroker, which provides interface abstraction.
    """
    def __init__(self, name: str, broker: MessageBroker, 
                 strategy: IAllocationStrategy,
                 repositioning_strategy: IRepositioningStrategy = None):
        self.name = name
        self.broker = broker
        self.strategy = strategy  # Allocation strategy
        self.repositioning_strategy = repositioning_strategy  # Repositioning strategy (optional)
        self.elevators = {}
        # Operation board to store the latest status of each elevator
        self.elevator_statuses = {}
        
        print(f"{self.broker.get_current_time():.2f} [GCS] Using strategy: {self.strategy.get_strategy_name()}")
        if self.repositioning_strategy:
            print(f"{self.broker.get_current_time():.2f} [GCS] Repositioning strategy: {self.repositioning_strategy.get_strategy_name()}")

    def register_elevator(self, elevator: Elevator):
        """
        Register an elevator under GCS management
        
        Note: Status listener process must be started externally by calling
        start_status_listener() after registration.
        """
        self.elevators[elevator.name] = elevator
        print(f"{self.broker.get_current_time():.2f} [GCS] Elevator '{elevator.name}' registered.")
    
    def start_status_listener(self, elevator_name: str):
        """
        Start status listener process for a registered elevator
        
        This method returns a generator that should be passed to env.process()
        by the simulator initialization code.
        
        Args:
            elevator_name: Name of the elevator to monitor
        
        Returns:
            Generator for status listener process
        """
        return self._status_listener(elevator_name)
    
    def send_move_command(self, elevator_name: str, target_floor: int):
        """
        Send move command to idle elevator for repositioning
        
        Move command is used to reposition idle elevators to strategic locations
        (e.g., lobby floor, high-traffic floors). The elevator will move to the
        target floor without opening doors. The command is cancelled if a real
        hall call is assigned.
        
        Args:
            elevator_name: Target elevator name
            target_floor: Floor to reposition to
        """
        if elevator_name not in self.elevators:
            print(f"{self.broker.get_current_time():.2f} [GCS] ERROR: Elevator '{elevator_name}' not found")
            return
        
        command = {
            'floor': target_floor,
            'timestamp': self.broker.get_current_time()
        }
        move_command_topic = f"elevator/{elevator_name}/move_command"
        self.broker.put(move_command_topic, command)
        print(f"{self.broker.get_current_time():.2f} [GCS] Sent move command to {elevator_name}: target floor {target_floor}")
    
    def send_forced_move_command(self, elevator_name: str, floor: int, direction: str):
        """
        Send forced move command to elevator for anticipated demand
        
        Forced move command is used when the system anticipates demand at a specific
        floor and direction (e.g., lobby floor during morning rush). The elevator
        will treat this as a real hall call, apply selective collective response,
        and open doors upon arrival.
        
        Args:
            elevator_name: Target elevator name
            floor: Target floor
            direction: Expected passenger direction ("UP" or "DOWN")
        """
        if elevator_name not in self.elevators:
            print(f"{self.broker.get_current_time():.2f} [GCS] ERROR: Elevator '{elevator_name}' not found")
            return
        
        if direction not in ["UP", "DOWN"]:
            print(f"{self.broker.get_current_time():.2f} [GCS] ERROR: Invalid direction '{direction}'. Must be 'UP' or 'DOWN'")
            return
        
        command = {
            'floor': floor,
            'direction': direction,
            'timestamp': self.broker.get_current_time()
        }
        forced_command_topic = f"elevator/{elevator_name}/forced_move_command"
        self.broker.put(forced_command_topic, command)
        print(f"{self.broker.get_current_time():.2f} [GCS] Sent forced move command to {elevator_name}: floor {floor} {direction}")

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
            print(f"{self.broker.get_current_time():.2f} [GCS] Status Update for {elevator_name}: Adv.Pos={adv_pos}F, State={state}, Phys.Pos={phys_pos}F")
            
            # Evaluate repositioning strategy (event-driven)
            if self.repositioning_strategy:
                commands = self.repositioning_strategy.evaluate(
                    elevator_name, status_message, self.elevator_statuses)
                
                # Execute repositioning commands
                for cmd in commands:
                    if cmd['type'] == 'forced_move':
                        print(f"{self.broker.get_current_time():.2f} [GCS] Repositioning: forced_move_command to {cmd['elevator']}")
                        self.send_forced_move_command(
                            cmd['elevator'], cmd['floor'], cmd['direction'])
                    elif cmd['type'] == 'move':
                        print(f"{self.broker.get_current_time():.2f} [GCS] Repositioning: move_command to {cmd['elevator']}")
                        self.send_move_command(
                            cmd['elevator'], cmd['floor'])


    def run(self):
        """
        Main process of GCS. Listens for hall calls
        """
        print(f"{self.broker.get_current_time():.2f} [GCS] GCS is operational. Waiting for hall calls...")
        
        hall_call_topic = 'gcs/hall_call'
        while True:
            message = yield self.broker.get(hall_call_topic)
            print(f"{self.broker.get_current_time():.2f} [GCS] Received hall call: {message}")

            # Select the best elevator for this hall call using strategy
            if self.elevators:
                # Prepare call_data with additional context
                call_data = {
                    'floor': message['floor'],
                    'direction': message.get('direction'),
                    'destination': message.get('destination'),  # For DCS (future)
                    'call_type': 'TRADITIONAL',  # TODO: get from ICallSystem
                    'timestamp': self.broker.get_current_time()
                }
                
                # Filter elevators that can service this floor
                call_floor = call_data['floor']
                serviceable_statuses = {
                    elev_name: status 
                    for elev_name, status in self.elevator_statuses.items()
                    if call_floor in status.get('service_floors', [])
                }
                
                if not serviceable_statuses:
                    print(f"{self.broker.get_current_time():.2f} [GCS] WARNING: No elevator can service floor {call_floor}. Hall call dropped.")
                    continue
                
                # Delegate selection to strategy (only with serviceable elevators)
                selected_elevator = self.strategy.select_elevator(call_data, serviceable_statuses)
                
                task_message = {
                    "task_type": "ASSIGN_HALL_CALL",
                    "details": message
                }
                
                task_topic = f"elevator/{selected_elevator}/task"
                self.broker.put(task_topic, task_message)
                print(f"{self.broker.get_current_time():.2f} [GCS] Assigned hall call to {selected_elevator}")
                
                # Broadcast assignment information for visualization
                assignment_message = {
                    "timestamp": self.broker.get_current_time(),
                    "floor": message['floor'],
                    "direction": message['direction'],
                    "assigned_elevator": selected_elevator
                }
                self.broker.put('gcs/hall_call_assignment', assignment_message)

