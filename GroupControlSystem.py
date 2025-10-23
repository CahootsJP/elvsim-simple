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
        Select the best elevator for a hall call using circular movement algorithm
        
        Key concepts:
        1. IDLE elevators: Simple distance calculation
        2. Moving elevators: Consider circular movement (UP to top, then DOWN; DOWN to bottom, then UP)
        3. Door closing/closed: Virtual position is next floor in movement direction
        """
        call_floor = hall_call['floor']
        call_direction = hall_call['direction']
        
        # Get number of floors from first registered elevator
        num_floors = 10  # Default
        if self.elevators:
            first_elevator = list(self.elevators.values())[0]
            num_floors = first_elevator.num_floors
        
        best_elevator = None
        best_score = float('inf')
        
        for elev_name, status in self.elevator_statuses.items():
            if not status:
                continue
            
            elevator_obj = self.elevators.get(elev_name)
            if not elevator_obj:
                continue
            
            physical_floor = status.get('physical_floor', 1)
            state = status.get('state', 'IDLE')
            passengers = status.get('passengers', 0)
            max_capacity = status.get('max_capacity', 10)
            
            # Get virtual position (considering door state)
            virtual_floor = self._get_virtual_position(elevator_obj, physical_floor, state)
            
            # Calculate real distance considering circular movement
            distance = self._calculate_circular_distance(
                virtual_floor, state, call_floor, call_direction, num_floors
            )
            
            # Penalty if elevator is full
            if passengers >= max_capacity:
                distance += 1000  # Large penalty
            
            # Select elevator with lowest score (shortest travel distance)
            if distance < best_score:
                best_score = distance
                best_elevator = elev_name
            
            print(f"{self.env.now:.2f} [GCS] {elev_name}: VirtualFloor={virtual_floor}, State={state}, Distance={distance:.1f}")
        
        # Fallback to first elevator if no status available
        if best_elevator is None:
            best_elevator = list(self.elevators.keys())[0]
        
        print(f"{self.env.now:.2f} [GCS] Selected {best_elevator} with distance={best_score:.1f}")
        return best_elevator
    
    def _get_virtual_position(self, elevator_obj, physical_floor, state):
        """
        Get virtual position of elevator
        
        If door is closing or closed, virtual position is the next floor in movement direction
        Otherwise, virtual position equals physical position
        """
        if not hasattr(elevator_obj, 'door') or not elevator_obj.door:
            return physical_floor
        
        door_state = getattr(elevator_obj.door, 'state', 'IDLE')
        
        # If door is closing or closed, elevator cannot stop at current floor
        if door_state in ['CLOSING', 'CLOSED']:
            if state == 'UP':
                return physical_floor + 1  # Next floor up
            elif state == 'DOWN':
                return physical_floor - 1  # Next floor down
        
        return physical_floor
    
    def _calculate_circular_distance(self, virtual_floor, state, call_floor, call_direction, num_floors):
        """
        Calculate travel distance considering circular elevator movement
        
        Args:
            virtual_floor: Virtual position of elevator
            state: Elevator state (UP/DOWN/IDLE)
            call_floor: Floor where hall call was made
            call_direction: Direction of hall call (UP/DOWN)
            num_floors: Total number of floors
        
        Returns:
            float: Estimated travel distance in floors
        """
        
        if state == 'IDLE':
            # IDLE: Simple distance
            return abs(call_floor - virtual_floor)
        
        elif state == 'UP':
            # Moving UP
            if call_direction == 'UP' and call_floor >= virtual_floor:
                # Same direction, ahead of elevator -> can pick up on the way
                return call_floor - virtual_floor
            else:
                # Need to complete UP journey, then reverse
                # Distance = (to top) + (from top to call floor)
                distance = (num_floors - virtual_floor)  # To top floor
                distance += (num_floors - call_floor)     # From top floor down to call floor
                return distance
        
        elif state == 'DOWN':
            # Moving DOWN
            if call_direction == 'DOWN' and call_floor <= virtual_floor:
                # Same direction, ahead of elevator -> can pick up on the way
                return virtual_floor - call_floor
            else:
                # Need to complete DOWN journey, then reverse
                # Distance = (to bottom) + (from bottom to call floor)
                distance = (virtual_floor - 1)      # To floor 1
                distance += (call_floor - 1)        # From floor 1 up to call floor
                return distance
        
        # Fallback
        return abs(call_floor - virtual_floor)

