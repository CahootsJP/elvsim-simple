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

            # TODO: Look at self.elevator_statuses to select the optimal elevator
            # For now, simply assign to the first elevator
            if self.elevators:
                first_elevator_name = list(self.elevators.keys())[0]
                
                task_message = {
                    "task_type": "ASSIGN_HALL_CALL",
                    "details": message
                }
                
                task_topic = f"elevator/{first_elevator_name}/task"
                self.broker.put(task_topic, task_message)

