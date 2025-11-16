import simpy
from .entity import Entity

class Door(Entity):
    """
    Door that operates via direct communication from the elevator operator
    """
    def __init__(self, env: simpy.Environment, name: str, open_time=1.5, close_time=1.5, broker=None, elevator_name: str = None, elevator=None, max_reopens_per_stop=None):
        super().__init__(env, name)
        self.open_time = open_time
        self.close_time = close_time
        self.broker = broker
        self.elevator_name: str = elevator_name
        self.elevator = elevator  # Reference to parent elevator
        self._current_floor: int = 1  # Default floor
        self.call_system = None  # Call system (ICallSystem) for DCS detection
        self.set_state('IDLE')  # Door state: IDLE, OPENING, OPEN, CLOSING, CLOSED
        self.sensor_timeout = 1.0  # Photoelectric sensor timeout (seconds to wait after queue becomes empty)
        
        # Reopen control
        self.max_reopens_per_stop = max_reopens_per_stop  # None = unlimited, number = limit
        self.reopen_count_this_stop = 0
        self.closing_process = None  # Handle to current closing process (for interruption)
        
        print(f"{self.env.now:.2f} [{self.name}] Door entity created.")

    def run(self):
        """
        This method is no longer used. The door waits for direct calls from the elevator operator.
        """
        yield self.env.timeout(0)  # Idle process

    def _broadcast_door_event(self, event_type: str, current_floor: int = None, waiting_passengers: list = None):
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
        
        # Add waiting passengers list if provided (for metrics)
        if waiting_passengers is not None:
            door_event_message['waiting_passengers'] = waiting_passengers
        
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

    def set_call_system(self, call_system):
        """Set call system (ICallSystem) for DCS detection"""
        self.call_system = call_system
    
    def reset_reopen_count(self):
        """Reset reopen count (called when starting a new stop)"""
        self.reopen_count_this_stop = 0
    
    def request_reopen(self) -> bool:
        """
        Request door to reopen during closing (called by Elevator)
        
        Returns:
            bool: True if reopen request accepted, False if denied
        """
        # Only reopen if currently closing
        if self.state != "CLOSING":
            return False
        
        # Check reopen limit
        if self.max_reopens_per_stop is not None:
            if self.reopen_count_this_stop >= self.max_reopens_per_stop:
                print(f"{self.env.now:.2f} [{self.elevator_name}Door] Reopen limit reached ({self.max_reopens_per_stop}), request denied")
                return False
        
        # Accept reopen request
        print(f"{self.env.now:.2f} [{self.elevator_name}Door] Reopen request accepted (reopen count: {self.reopen_count_this_stop + 1})")
        self.reopen_count_this_stop += 1
        
        # Interrupt closing process
        if self.closing_process and self.closing_process.is_alive:
            self.closing_process.interrupt()
        
        return True

    def handle_boarding_and_alighting_process(self, passengers_to_exit, boarding_queues, has_car_call_here=False, is_dcs_floor=False, current_floor=None):
        """
        Main boarding and alighting process called directly by the elevator operator
        
        Args:
            passengers_to_exit: List of passengers exiting
            boarding_queues: Queues of passengers waiting to board
            has_car_call_here: Whether current floor has a car call (for OFF message timing)
            is_dcs_floor: Whether current floor is a DCS floor
            current_floor: Current floor number (to prevent registering car call for current floor)
        
        Returns:
            dict: Report containing boarded, failed_to_board passengers, and reopen_limit_reached flag
        """
        boarded_passengers = []
        failed_to_board_passengers = []  # List of passengers who failed to board
        reopen_limit_reached = False  # Flag to indicate if reopen limit was reached
        
        # Get capacity information from elevator
        current_capacity = self.elevator.get_current_capacity() if self.elevator else 0
        max_capacity = self.elevator.get_max_capacity() if self.elevator else None
        elevator_name = self.elevator_name or "Unknown"
        
        # Get current floor from elevator if not provided
        if current_floor is None and self.elevator:
            current_floor = self.elevator.current_floor

        # 1. Open the door
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opening...")
        self.set_state('OPENING')
        
        # Collect waiting passenger names from all boarding queues (for metrics)
        # IMPORTANT: Must collect BEFORE door opens to capture the correct "door open" time
        # Also collect waiting passengers for DCS auto-registration
        waiting_passenger_names = []
        waiting_passengers_for_dcs = []  # Store passenger objects for DCS auto-registration
        for queue in boarding_queues:
            queue_passengers = [p for p in queue.items]
            waiting_passenger_names.extend([p.name for p in queue_passengers])
            waiting_passengers_for_dcs.extend(queue_passengers)
        
        # Send door opening start event with waiting passengers list
        yield self.env.process(self._broadcast_door_event("DOOR_OPENING_START", 
                                                          waiting_passengers=waiting_passenger_names))
        
        # Send car call OFF message at door opening start (if car call exists here)
        if has_car_call_here and self.broker and self.elevator_name:
            car_call_off_message = {
                "timestamp": self.env.now,
                "elevator_name": self.elevator_name,
                "destination": self._current_floor,
                "action": "OFF"
            }
            car_call_off_topic = f"elevator/{self.elevator_name}/car_call_off"
            yield self.broker.put(car_call_off_topic, car_call_off_message)
        
        # Record door open start time (for passenger metrics)
        door_open_start_time = self.env.now
        
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [{elevator_name}] Door Opened.")
        self.set_state('OPEN')
        
        # Send door opening complete event
        yield self.env.process(self._broadcast_door_event("DOOR_OPENING_COMPLETE"))
        
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
                            
                            # Notify remaining passengers in queue that they were left behind
                            # (Important for DCS: passengers must re-register)
                            remaining_passengers = list(queue.items)  # Copy list to avoid modification during iteration
                            for passenger in remaining_passengers:
                                if passenger not in boarded_passengers:
                                    print(f"{self.env.now:.2f} [{elevator_name}] Notifying {passenger.name} that boarding failed (capacity full).")
                                    failed_notification = self.env.event()
                                    failed_notification.succeed()
                                    yield passenger.boarding_failed_event.put(failed_notification)
                                    failed_to_board_passengers.append(passenger)
                            
                            break
                    
                    # Board the passenger
                    passenger = yield queue.get()
                    board_permission_event = self.env.event()
                    # Pass elevator name, door open time, and real-time passenger count
                    permission_data = {
                        'completion_event': board_permission_event,
                        'elevator_name': self.elevator_name,
                        'door_open_time': door_open_start_time,  # Pass door open time for passenger metrics
                        'passengers_count': actual_current_capacity + len(boarded_passengers)  # Real-time count
                    }
                    yield passenger.board_permission_event.put(permission_data)
                    yield board_permission_event
                    boarded_passengers.append(passenger)
                    
                    # DCS: Photoelectric sensor detects first passenger boarding
                    # Automatically register car calls for all waiting passengers at this floor
                    if is_dcs_floor and len(boarded_passengers) == 1:
                        # First passenger boarded - register car calls for:
                        # 1. This passenger (who just boarded)
                        # 2. All other waiting passengers that were in queues when door opened
                        # Note: We use waiting_passengers_for_dcs which was captured before door opened
                        self._register_dcs_car_calls_for_waiting_passengers(
                            waiting_passengers_for_dcs, elevator_name, first_passenger=passenger, current_floor=current_floor
                        )
                    
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

        # 4. Close the door (with reopen capability)
        try:
            print(f"{self.env.now:.2f} [{elevator_name}] Door Closing...")
            self.set_state('CLOSING')
            # Send door closing start event
            yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_START"))
            
            # Store closing process handle for potential interruption
            self.closing_process = self.env.process(self._do_closing(elevator_name))
            yield self.closing_process
            
            print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")
            self.set_state('CLOSED')
            # Send door closing complete event
            yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_COMPLETE"))
            
        except simpy.Interrupt:
            # Door closing was interrupted for reopen
            print(f"{self.env.now:.2f} [{elevator_name}Door] Door closing interrupted for reopen")
            
            # Check if reopen limit has been reached
            if self.max_reopens_per_stop is not None and self.reopen_count_this_stop > self.max_reopens_per_stop:
                # This shouldn't happen (request_reopen should prevent it), but just in case
                reopen_limit_reached = True
                print(f"{self.env.now:.2f} [{elevator_name}Door] Reopen limit exceeded, completing closing")
                
                # Complete the closing
                self.set_state('CLOSED')
                yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_COMPLETE"))
            else:
                # Reopen the door
                print(f"{self.env.now:.2f} [{elevator_name}Door] Reopening door...")
                yield self.env.process(self._do_reopening(elevator_name))
                
                # Continue boarding process (recursive call to handle additional passengers)
                # Note: We don't exit passengers again, only continue boarding
                additional_report = yield self.env.process(
                    self._continue_boarding_after_reopen(boarding_queues, boarded_passengers, 
                                                         failed_to_board_passengers, is_dcs_floor, 
                                                         current_floor, elevator_name, max_capacity)
                )
                
                # Merge reports
                boarded_passengers = additional_report["boarded"]
                failed_to_board_passengers = additional_report["failed_to_board"]
                reopen_limit_reached = additional_report.get("reopen_limit_reached", False)
                
                # Return after successful reopen handling
                return {
                    "boarded": boarded_passengers,
                    "failed_to_board": failed_to_board_passengers,
                    "reopen_limit_reached": reopen_limit_reached
                }

        # 5. Return completion report directly to the elevator operator
        return {
            "boarded": boarded_passengers,
            "failed_to_board": failed_to_board_passengers,
            "reopen_limit_reached": reopen_limit_reached
        }
    
    def _register_dcs_car_calls_for_waiting_passengers(self, waiting_passengers_list, elevator_name: str, first_passenger=None, current_floor=None):
        """
        Register car calls automatically for all waiting passengers at DCS floor
        
        This simulates the photoelectric sensor detecting the first passenger boarding,
        which triggers automatic registration of all waiting passengers' destinations.
        
        Args:
            waiting_passengers_list: List of passenger objects that were waiting when door opened
            elevator_name: Name of the elevator
            first_passenger: The first passenger who just boarded (to include their destination)
            current_floor: Current floor number (to prevent registering car call for current floor)
        """
        if not self.broker or not self.elevator:
            return
        
        # Start with passengers that were waiting when door opened
        waiting_passengers = list(waiting_passengers_list)
        
        # Include the first passenger who just boarded
        if first_passenger:
            waiting_passengers.append(first_passenger)
        
        if not waiting_passengers:
            return
        
        # Get current floor from elevator if not provided
        if current_floor is None:
            current_floor = self.elevator.current_floor if self.elevator else None
        
        # Register car calls for all waiting passengers (including first passenger)
        destinations_registered = set()
        skipped_current_floor = 0
        for passenger in waiting_passengers:
            destination = passenger.destination_floor
            
            # Skip registering car call for current floor (passenger is already at destination)
            if current_floor is not None and destination == current_floor:
                skipped_current_floor += 1
                print(f"{self.env.now:.2f} [{elevator_name}] Photoelectric sensor: Skipping car call for current floor {destination} (passenger: {passenger.name} is already at destination)")
                continue
            
            if destination not in destinations_registered:
                # Register car call
                car_call_topic = f"elevator/{elevator_name}/car_call"
                car_call_message = {
                    'destination': destination,
                    'passenger_name': passenger.name,
                    'auto_registered': True  # Flag to indicate automatic registration
                }
                self.broker.put(car_call_topic, car_call_message)
                destinations_registered.add(destination)
                print(f"{self.env.now:.2f} [{elevator_name}] Photoelectric sensor: Auto-registered car call for floor {destination} (passenger: {passenger.name})")
        
        if skipped_current_floor > 0:
            print(f"{self.env.now:.2f} [{elevator_name}] Photoelectric sensor: Skipped {skipped_current_floor} car call(s) for current floor")
    
    def _do_closing(self, elevator_name):
        """
        Door closing process (can be interrupted for reopen)
        
        Args:
            elevator_name: Name of elevator for logging
        """
        yield self.env.timeout(self.close_time)
    
    def _do_reopening(self, elevator_name):
        """
        Door reopening process (after interruption during closing)
        
        Args:
            elevator_name: Name of elevator for logging
        """
        self.set_state('OPENING')
        yield self.env.process(self._broadcast_door_event("DOOR_REOPENING"))
        yield self.env.timeout(self.open_time)
        self.set_state('OPEN')
        print(f"{self.env.now:.2f} [{elevator_name}Door] Door reopened")
        yield self.env.process(self._broadcast_door_event("DOOR_REOPEN_COMPLETE"))
    
    def _continue_boarding_after_reopen(self, boarding_queues, boarded_passengers, 
                                       failed_to_board_passengers, is_dcs_floor, 
                                       current_floor, elevator_name, max_capacity):
        """
        Continue boarding process after door reopen
        
        Args:
            boarding_queues: Queues of passengers waiting to board
            boarded_passengers: List of already boarded passengers (will be updated)
            failed_to_board_passengers: List of passengers who failed to board (will be updated)
            is_dcs_floor: Whether current floor is a DCS floor
            current_floor: Current floor number
            elevator_name: Name of elevator for logging
            max_capacity: Maximum capacity of elevator
        
        Returns:
            dict: Updated report with boarded, failed_to_board, and reopen_limit_reached
        """
        # Continue boarding process (similar to step 3 in main process)
        actual_current_capacity = len(self.elevator.passengers_onboard) if self.elevator else 0
        
        for queue in boarding_queues:
            # Continuously monitor queue while door is open
            while True:
                if len(queue.items) > 0:
                    # Check capacity
                    if max_capacity is not None:
                        available_space = max_capacity - actual_current_capacity
                        if available_space <= 0:
                            print(f"{self.env.now:.2f} [{elevator_name}] Capacity reached after reopen. Cannot board more.")
                            remaining_passengers = list(queue.items)
                            for p in remaining_passengers:
                                failed_notification = self.env.event()
                                failed_notification.succeed()
                                yield p.boarding_failed_event.put(failed_notification)
                                failed_to_board_passengers.append(p)
                            break
                    
                    # Board next passenger
                    passenger = yield queue.get()
                    boarding_permission_event = self.env.event()
                    permission_data = {
                        'completion_event': boarding_permission_event,
                        'elevator_name': self.elevator_name
                    }
                    yield passenger.board_permission_event.put(permission_data)
                    yield boarding_permission_event
                    
                    boarded_passengers.append(passenger)
                    
                    # Real-time update
                    if self.elevator:
                        self.elevator.passengers_onboard.append(passenger)
                        yield self.env.process(self.elevator._report_status())
                        actual_current_capacity = len(self.elevator.passengers_onboard)
                else:
                    # Queue empty - wait for sensor timeout
                    print(f"{self.env.now:.2f} [{elevator_name}] Queue empty after reopen, waiting {self.sensor_timeout}s...")
                    yield self.env.timeout(self.sensor_timeout)
                    
                    if len(queue.items) == 0:
                        print(f"{self.env.now:.2f} [{elevator_name}] No more passengers after reopen. Closing door.")
                        break
                    else:
                        print(f"{self.env.now:.2f} [{elevator_name}] New passenger detected after reopen! Continuing...")
        
        # Now try to close door again (with possibility of another reopen)
        try:
            print(f"{self.env.now:.2f} [{elevator_name}] Door Closing after reopen...")
            self.set_state('CLOSING')
            yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_START"))
            
            self.closing_process = self.env.process(self._do_closing(elevator_name))
            yield self.closing_process
            
            print(f"{self.env.now:.2f} [{elevator_name}] Door Closed.")
            self.set_state('CLOSED')
            yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_COMPLETE"))
            
            return {
                "boarded": boarded_passengers,
                "failed_to_board": failed_to_board_passengers,
                "reopen_limit_reached": False
            }
            
        except simpy.Interrupt:
            # Another reopen requested
            print(f"{self.env.now:.2f} [{elevator_name}Door] Door closing interrupted again for reopen")
            
            # Check reopen limit
            if self.max_reopens_per_stop is not None and self.reopen_count_this_stop > self.max_reopens_per_stop:
                print(f"{self.env.now:.2f} [{elevator_name}Door] Reopen limit exceeded, completing closing")
                self.set_state('CLOSED')
                yield self.env.process(self._broadcast_door_event("DOOR_CLOSING_COMPLETE"))
                
                return {
                    "boarded": boarded_passengers,
                    "failed_to_board": failed_to_board_passengers,
                    "reopen_limit_reached": True
                }
            else:
                # Reopen again (recursive)
                print(f"{self.env.now:.2f} [{elevator_name}Door] Reopening door again...")
                yield self.env.process(self._do_reopening(elevator_name))
                
                # Continue boarding recursively
                report = yield self.env.process(
                    self._continue_boarding_after_reopen(boarding_queues, boarded_passengers,
                                                        failed_to_board_passengers, is_dcs_floor,
                                                        current_floor, elevator_name, max_capacity)
                )
                return report
