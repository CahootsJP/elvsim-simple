import simpy
from Entity import Entity

class Door(Entity):
    """
    Door that operates via direct communication from the elevator operator
    """
    def __init__(self, env: simpy.Environment, name: str, open_time=1.5, close_time=1.5, broker=None, elevator_name: str = None, elevator=None):
        super().__init__(env, name)
        self.open_time = open_time
        self.close_time = close_time
        self.broker = broker
        self.elevator_name: str = elevator_name
        self.elevator = elevator  # Reference to parent elevator
        self._current_floor: int = 1  # Default floor
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        This method is no longer used. The door waits for direct calls from the elevator operator.
        """
        yield self.env.timeout(0)  # Idle process

    def _broadcast_door_event(self, event_type: str, current_floor: int = None):
        """Broadcast door event to message broker."""
        if not self.broker or not self.elevator_name:
            return
        
        # Use internal _current_floor if current_floor is not specified
        floor = current_floor if current_floor is not None else self._current_floor
        
        door_event_message = {
            "timestamp": self.env.now,
            "elevator_name": self.elevator_name,
            "door_id": self.name,
            "event_type": event_type,
            "floor": floor
        }
        door_event_topic = f"elevator/{self.elevator_name}/door_events"
        self.env.process(self._send_message(door_event_topic, door_event_message))

    def _send_message(self, topic: str, message: dict):
        """Process to send message to broker."""
        if self.broker:
            yield self.broker.put(topic, message)

    def set_broker_and_elevator(self, broker, elevator_name: str, elevator=None):
        """Set MessageBroker, elevator name, and elevator reference after initialization."""
        self.broker = broker
        self.elevator_name = elevator_name
        if elevator is not None:
            self.elevator = elevator

    def set_current_floor(self, floor: int):
        """Set current floor number."""
        self._current_floor = floor

    def handle_boarding_and_alighting_process(self, passengers_to_exit, boarding_queues):
        """
        Main boarding and alighting process called directly by the elevator operator
        
        Args:
            passengers_to_exit: List of passengers exiting
            boarding_queues: Queues of passengers waiting to board
        
        Returns:
            dict: Report containing boarded and failed_to_board passengers
        """
        boarded_passengers = []
        failed_to_board_passengers = []  # List of passengers who failed to board
        
        # Get capacity information from elevator
        current_capacity = self.elevator.get_current_capacity() if self.elevator else 0
        max_capacity = self.elevator.get_max_capacity() if self.elevator else None
        elevator_name = self.elevator_name or "Unknown"

        # 1. Open the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opening...")
        # Send door opening start event
        self._broadcast_door_event("DOOR_OPENING_START")
        
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        # Send door opening complete event
        self._broadcast_door_event("DOOR_OPENING_COMPLETE")
        
        # 2. Let passengers exit one by one at their own pace
        for p in passengers_to_exit:
            exit_permission_event = self.env.event()
            yield p.exit_permission_event.put(exit_permission_event)
            yield exit_permission_event

        # 3. Let passengers board one by one at their own pace (with capacity check)
        # Calculate current capacity after passengers exit
        actual_current_capacity = current_capacity - len(passengers_to_exit)
        
        for queue in boarding_queues:
            while len(queue.items) > 0:
                # Check capacity (including already boarded passengers)
                if max_capacity is not None:
                    available_space = max_capacity - (actual_current_capacity + len(boarded_passengers))
                    if available_space <= 0:
                        # Capacity reached - record remaining passengers
                        print(f"{self.env.now:.2f} [{elevator_name}] Capacity reached ({max_capacity} passengers). Cannot board more passengers.")
                        # Extract all remaining passengers from queue and record them
                        while len(queue.items) > 0:
                            failed_passenger = yield queue.get()
                            failed_to_board_passengers.append(failed_passenger)
                        break
                
                passenger = yield queue.get()
                board_permission_event = self.env.event()
                yield passenger.board_permission_event.put(board_permission_event)
                yield board_permission_event
                boarded_passengers.append(passenger)

        # 4. Close the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
        # Send door closing start event
        self._broadcast_door_event("DOOR_CLOSING_START")
        
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")
        # Send door closing complete event
        self._broadcast_door_event("DOOR_CLOSING_COMPLETE")

        # 5. Return completion report directly to the elevator operator
        return {
            "boarded": boarded_passengers,
            "failed_to_board": failed_to_board_passengers
        }

