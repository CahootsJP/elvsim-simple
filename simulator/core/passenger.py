import simpy
from .entity import Entity
from ..infrastructure.message_broker import MessageBroker
from .hall_button import HallButton
from ..interfaces.call_system import ICallSystem
from ..interfaces.passenger_behavior import IPassengerBehavior

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
                 arrival_floor: int, destination_floor: int, move_speed: float):
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        self.call_system = call_system  # Building's call system configuration
        self.behavior = behavior        # Passenger's decision logic
        
        self.arrival_floor = arrival_floor
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
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor} (Move time: {self.move_speed:.1f}s).")

    def is_front_of_queue(self, queue):
        """Check if this passenger is at the front of the queue"""
        if len(queue.items) == 0:
            return False
        return queue.items[0] == self

    def run(self):
        """
        Passenger's main process
        
        Adapts workflow based on call system type at arrival floor.
        """
        yield self.env.timeout(1)
        
        # Determine call system type at arrival floor
        call_type = self.call_system.get_floor_call_type(self.arrival_floor)
        
        # Branch workflow based on call system
        if call_type == 'TRADITIONAL':
            yield from self._traditional_workflow()
        elif call_type == 'DCS':
            yield from self._dcs_workflow()
        else:
            raise ValueError(f"Unknown call type: {call_type}")
    
    def _traditional_workflow(self):
        """Traditional elevator workflow (current implementation)"""
        print(f"{self.env.now:.2f} [{self.name}] Using TRADITIONAL at floor {self.arrival_floor}.")
        
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button = self.hall_buttons[self.arrival_floor][direction]
        
        boarded_successfully = False
        
        # 1. Press hall button (with duplicate check functionality)
        if button.is_lit():
            print(f"{self.env.now:.2f} [{self.name}] Hall button at floor {self.arrival_floor} ({direction}) already lit. No need to press.")
        else:
            button.press(passenger_name=self.name)

        # 2. Join the queue in the correct direction
        current_queue = self.floor_queues[self.arrival_floor][direction]
        print(f"{self.env.now:.2f} [{self.name}] Now waiting in '{direction}' queue at floor {self.arrival_floor}.")
        
        # Record waiting start time (self-tracking)
        self.waiting_start_time = self.env.now
        
        # Notify Statistics that a passenger is waiting
        waiting_message = {
            "floor": self.arrival_floor,
            "direction": direction,
            "passenger_name": self.name
        }
        self.broker.put("passenger/waiting", waiting_message)
        
        yield current_queue.put(self)

        # 3. Periodic check loop: monitor queue position, button state, and boarding events
        # 
        # DESIGN NOTE: Trade-off between responsiveness and computational overhead
        # 
        # Current: CHECK_INTERVAL = 0.1 second (polling-only approach)
        #   Pros: Simple, debuggable, works for all cases
        #   Cons: Max 0.1s delay on boarding, ~40% overhead vs event-driven
        # 
        # Alternative: Hybrid approach (polling + event-driven)
        #   yield check_timeout | board_get | fail_get
        #   Pros: Immediate response to boarding events, lower overhead
        #   Cons: More complex, SimPy event management issues (board_get must be 
        #         recreated each loop, which can miss events from Door)
        # 
        # Decision: Polling-only is preferred for now due to simplicity and reliability.
        #           0.1s delay is acceptable (faster than human reaction time ~0.2-0.5s).
        #           If performance becomes critical, consider hybrid approach with
        #           careful event lifecycle management.
        #
        CHECK_INTERVAL = self.behavior.get_check_interval()  # Use behavior's check interval
        
        while not boarded_successfully:
            # Wait for next check interval
            yield self.env.timeout(CHECK_INTERVAL)
            
            # Check 1: Use behavior to decide if should press button
            if self.behavior.should_press_button(self, button, current_queue):
                print(f"{self.env.now:.2f} [{self.name}] I'm at front and button is OFF. Pressing button!")
                button.press(passenger_name=self.name)
            
            # Check 2: Has boarding permission arrived?
            if len(self.board_permission_event.items) > 0:
                # Get permission data
                permission_data = yield self.board_permission_event.get()
                completion_event = permission_data['completion_event']
                elevator_name = permission_data.get('elevator_name', None)
                door_open_time = permission_data.get('door_open_time', None)
                
                # Check 3: Use behavior to decide if should board this elevator
                if not self.behavior.should_board_elevator(self, permission_data):
                    print(f"{self.env.now:.2f} [{self.name}] Rejecting elevator {elevator_name} (not assigned to me).")
                    completion_event.succeed()  # Notify door anyway
                    continue  # Wait for correct elevator
                
                print(f"{self.env.now:.2f} [{self.name}] Boarding elevator.")
                
                # Record door open time (self-tracking)
                if door_open_time is not None:
                    self.door_open_time = door_open_time
                
                # Publish passenger boarding event
                self.broker.put('passenger/boarding', {
                    'passenger_name': self.name,
                    'floor': self.arrival_floor,
                    'direction': direction,
                    'elevator_name': elevator_name,
                    'timestamp': self.env.now,
                    'wait_time': self.get_waiting_time_to_door_open(),
                    'wait_time_to_boarding': self.get_waiting_time_to_boarding()
                })
                
                yield self.env.timeout(self.move_speed)

                # Record boarding time (self-tracking)
                self.boarding_time = self.env.now
                self.boarded_elevator_name = elevator_name

                # Board the elevator and press destination button
                print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
                car_call_topic = f"elevator/{elevator_name}/car_call"
                self.broker.put(car_call_topic, {'destination': self.destination_floor, 'passenger_name': self.name})

                # Report to Door that "boarding is complete"
                completion_event.succeed()
                
                boarded_successfully = True
            
            # Check 4: Has boarding failed?
            elif len(self.boarding_failed_event.items) > 0:
                # Get failure notification and discard it
                yield self.boarding_failed_event.get()
                print(f"{self.env.now:.2f} [{self.name}] Failed to board (capacity full). Will keep waiting and monitoring...")

        # 7. Wait for "please exit" permission from Door at destination
        permission_data = yield self.exit_permission_event.get()
        completion_event = permission_data['completion_event']

        # 8. Exit the elevator at own pace
        print(f"{self.env.now:.2f} [{self.name}] Exiting elevator.")
        yield self.env.timeout(self.move_speed)
        
        # Record alighting time (self-tracking)
        self.alighting_time = self.env.now
        
        # 9. Report to Door that "exiting is complete"
        completion_event.succeed()
        
        # 10. Publish passenger alighting event (for metrics)
        self.broker.put('passenger/alighting', {
            'timestamp': self.env.now,
            'passenger_name': self.name,
            'floor': self.destination_floor,
            'elevator_name': getattr(self, 'boarded_elevator_name', None),
            'riding_time': self.get_riding_time(),
            'total_journey_time': self.get_total_journey_time(),
            'wait_time': self.get_waiting_time_to_door_open()
        })
        
        print(f"{self.env.now:.2f} [{self.name}] Journey complete.")
    
    def _dcs_workflow(self):
        """DCS workflow (future implementation)"""
        print(f"{self.env.now:.2f} [{self.name}] Using DCS at floor {self.arrival_floor}.")
        
        # TODO: DCS implementation
        # 1. Register destination at panel
        destination = self.behavior.get_destination_for_dcs(self)
        print(f"{self.env.now:.2f} [{self.name}] Registering destination: {destination} at DCS panel.")
        
        # 2. Wait for elevator assignment from DCS Controller
        # TODO: Listen for assignment message from broker
        # self.broker.subscribe(f'dcs/assignment/{self.name}', ...)
        
        # 3. Board assigned elevator only
        # TODO: Use behavior.should_board_elevator() to check assignment
        
        # For now, just timeout (stub implementation)
        yield self.env.timeout(1.0)
        print(f"{self.env.now:.2f} [{self.name}] DCS workflow not fully implemented yet.")
    
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

