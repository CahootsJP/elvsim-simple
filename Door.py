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
        self.state = 'IDLE'  # Door state: IDLE, OPENING, OPEN, CLOSING, CLOSED
        self.sensor_timeout = 1.0  # Photoelectric sensor timeout (seconds to wait after queue becomes empty)
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        This method is no longer used. The door waits for direct calls from the elevator operator.
        """
        yield self.env.timeout(0)  # Idle process

    def _broadcast_door_event(self, event_type: str, current_floor: int = None):
        """Broadcast door event to message broker (generator for yield)."""
        if not self.broker or not self.elevator_name:
            yield self.env.timeout(0)  # Make it a generator even when no-op
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
        yield self.broker.put(door_event_topic, door_event_message)

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

    def handle_boarding_and_alighting_process(self, passengers_to_exit, boarding_queues, has_car_call_here=False):
        """
        Main boarding and alighting process called directly by the elevator operator
        
        Args:
            passengers_to_exit: List of passengers exiting
            boarding_queues: Queues of passengers waiting to board
            has_car_call_here: Whether current floor has a car call (for OFF message timing)
        
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
        self.state = 'OPENING'
        # Send door opening start event
        yield self.env.process(self._broadcast_door_event("DOOR_OPENING_START"))
        
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        self.state = 'OPEN'
        # Send door opening complete event
        yield self.env.process(self._broadcast_door_event("DOOR_OPENING_COMPLETE"))
        
        # Send car call OFF message at door opening complete (if car call exists here)
        if has_car_call_here and self.broker and self.elevator_name:
            car_call_off_message = {
                "timestamp": self.env.now,
                "elevator_name": self.elevator_name,
                "destination": self._current_floor,
                "action": "OFF"
            }
            car_call_off_topic = f"elevator/{self.elevator_name}/car_call_off"
            yield self.broker.put(car_call_off_topic, car_call_off_message)
        
        # 2. Let passengers exit one by one at their own pace
        for p in passengers_to_exit:
            exit_permission_event = self.env.event()
            # Pass elevator name along with permission event (for consistency)
            permission_data = {
                'completion_event': exit_permission_event,
                'elevator_name': self.elevator_name
            }
            yield p.exit_permission_event.put(permission_data)
            yield exit_permission_event
            
            # Real-time update: remove passenger from elevator immediately and report status
            if self.elevator and p in self.elevator.passengers_onboard:
                self.elevator.passengers_onboard.remove(p)
                yield self.env.process(self.elevator._report_status())

        # 3. Let passengers board one by one with photoelectric sensor simulation
        # Calculate current capacity after passengers exit
        actual_current_capacity = current_capacity - len(passengers_to_exit)
        
        for queue in boarding_queues:
            # Continuously monitor queue while door is open (photoelectric sensor simulation)
            while True:
                # Check if anyone is waiting in queue
                if len(queue.items) > 0:
                    # Check capacity before boarding
                    if max_capacity is not None:
                        available_space = max_capacity - (actual_current_capacity + len(boarded_passengers))
                        if available_space <= 0:
                            # Capacity reached - stop boarding from this queue
                            print(f"{self.env.now:.2f} [{elevator_name}] Capacity reached ({max_capacity} passengers). Cannot board more passengers.")
                            break
                    
                    # Board the passenger
                    passenger = yield queue.get()
                    board_permission_event = self.env.event()
                    # Pass elevator name along with permission event
                    permission_data = {
                        'completion_event': board_permission_event,
                        'elevator_name': self.elevator_name
                    }
                    yield passenger.board_permission_event.put(permission_data)
                    yield board_permission_event
                    boarded_passengers.append(passenger)
                    
                    # Real-time update: add passenger to elevator immediately and report status
                    if self.elevator:
                        self.elevator.passengers_onboard.append(passenger)
                        yield self.env.process(self.elevator._report_status())
                else:
                    # Queue is empty - photoelectric sensor detects no one
                    # Wait for sensor_timeout to see if anyone else arrives
                    print(f"{self.env.now:.2f} [{elevator_name}] Queue empty, waiting {self.sensor_timeout}s for more passengers (photoelectric sensor)...")
                    yield self.env.timeout(self.sensor_timeout)
                    
                    # Check again after timeout
                    if len(queue.items) == 0:
                        # Still empty - close door
                        print(f"{self.env.now:.2f} [{elevator_name}] No more passengers detected. Closing door.")
                        break
                    else:
                        # Someone arrived during timeout - continue boarding
                        print(f"{self.env.now:.2f} [{elevator_name}] New passenger detected! Continuing boarding...")

        # 4. Close the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
        self.state = 'CLOSING'
        # Send door closing start event
        yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_START"))
        
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")
        self.state = 'CLOSED'
        # Send door closing complete event
        yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_COMPLETE"))

        # 5. Return completion report directly to the elevator operator
        return {
            "boarded": boarded_passengers,
            "failed_to_board": failed_to_board_passengers
        }

