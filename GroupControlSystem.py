import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Elevator import Elevator

class GroupControlSystem(Entity):
    """
    Group Control System that monitors each elevator's status in real-time
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker):
        super().__init__(env, name)
        self.broker = broker
        self.elevators = {}
        # Operation board to store the latest status of each elevator
        self.elevator_statuses = {}

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

            # Select the best elevator for this hall call
            if self.elevators:
                selected_elevator = self._select_best_elevator(message)
                
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
    
    def _select_best_elevator(self, hall_call):
        """
        Select the best elevator for a hall call using simple nearest-car algorithm
        """
        call_floor = hall_call['floor']
        call_direction = hall_call['direction']
        
        best_elevator = None
        best_score = float('inf')
        
        for elev_name, status in self.elevator_statuses.items():
            if not status:
                continue
            
            current_floor = status.get('physical_floor', 1)
            state = status.get('state', 'IDLE')
            passengers = status.get('passengers', 0)
            max_capacity = status.get('max_capacity', 10)
            
            # Calculate distance-based score
            distance = abs(call_floor - current_floor)
            
            # Penalty if elevator is full
            if passengers >= max_capacity:
                distance += 100  # Large penalty
            
            # Bonus if elevator is IDLE
            if state == 'IDLE':
                distance -= 2  # Small bonus
            
            # Bonus if elevator is moving in same direction towards the call
            if state == 'UP' and call_direction == 'UP' and current_floor < call_floor:
                distance -= 1  # On the way bonus
            elif state == 'DOWN' and call_direction == 'DOWN' and current_floor > call_floor:
                distance -= 1  # On the way bonus
            
            # Select elevator with lowest score (closest)
            if distance < best_score:
                best_score = distance
                best_elevator = elev_name
        
        # Fallback to first elevator if no status available
        if best_elevator is None:
            best_elevator = list(self.elevators.keys())[0]
        
        return best_elevator

