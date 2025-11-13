import simpy
from simpy.events import Interrupt
from .entity import Entity
from ..infrastructure.message_broker import MessageBroker
from .passenger import Passenger
from .door import Door
import math

class Elevator(Entity):
    """
    Elevator that can handle interruptions during movement
    """

    # Physics constants
    MIN_BRAKE_TIME_THRESHOLD = 0.05  # Minimum brake time to trigger DECELERATING state (seconds)

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_queues, door: Door, flight_profiles: dict, physics_engine=None, hall_buttons=None, max_capacity: int = 10, full_load_bypass: bool = True, home_floor: int = 1, main_direction: str = "UP", service_floors=None, building=None, call_system=None):
        # Initialize direction before calling super().__init__
        self.direction = "NO_DIRECTION"
        
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        self.floor_queues = floor_queues
        self.door = door
        self.flight_profiles = flight_profiles
        self.physics_engine = physics_engine  # Access to PhysicsEngine
        self.hall_buttons = hall_buttons  # Reference to hall buttons
        self.max_capacity = max_capacity  # Maximum number of passengers
        self.full_load_bypass = full_load_bypass  # True: bypass when full, False: stop even when full
        
        # Building characteristics
        self.home_floor = home_floor  # Home floor (typically lobby where elevator returns when idle)
        self.main_direction = main_direction  # Main traffic direction ("UP" or "DOWN", typically "UP" for office buildings)
        self.building = building  # Building object for floor name mapping
        self.call_system = call_system  # Call system (ICallSystem) for DCS detection
        
        # Service floors: floors this elevator can stop at
        # If None, elevator services all floors
        if service_floors is None:
            self.service_floors = list(range(1, num_floors + 1))
        else:
            self.service_floors = sorted(service_floors)
            # Validate service floors
            for floor in self.service_floors:
                if floor < 1 or floor > num_floors:
                    raise ValueError(f"Invalid service floor {floor} for elevator {name}. Must be between 1 and {num_floors}.")

        self.current_floor = 1
        
        # Set MessageBroker, elevator name, and reference to this elevator in Door object
        if hasattr(self.door, 'set_broker_and_elevator'):
            self.door.set_broker_and_elevator(self.broker, self.name, self)
        # Set current floor to Door object
        if hasattr(self.door, 'set_current_floor'):
            self.door.set_current_floor(self.current_floor)
        # Set call_system to Door object (for DCS auto-registration)
        if hasattr(self.door, 'set_call_system'):
            self.door.set_call_system(self.call_system)
        self.advanced_position = 1
        self.current_destination = None  # Current final destination
        self.last_advanced_position = None  # Previous advanced_position
        self.current_move_process = None  # Track current movement process
        
        # Table method enable flag (default: practical timeline method)
        self.use_table_method = True

        self.car_calls = set()
        self.hall_calls_up = set()
        self.hall_calls_down = set()
        self.passengers_onboard = []
        
        # Move command support (repositioning when idle)
        self.move_command_target_floor = None  # Target floor for move command
        
        # Forced move commands (kept separate from real hall calls for tracking)
        self.forced_calls_up = set()
        self.forced_calls_down = set()
        
        self.new_call_event = self.env.event()
        self.status_topic = f"elevator/{self.name}/status"
        
        # Set initial state and direction
        self.set_state("IDLE")
        
        self.env.process(self._hall_call_listener())
        self.env.process(self._car_call_listener())
        self.env.process(self._move_command_listener())
        self.env.process(self._forced_move_command_listener())

    def _on_state_changed(self, old_state: str, new_state: str):
        """
        Hook method called when state changes.
        Overrides Entity's _on_state_changed to add Elevator-specific behavior.
        """
        # Call parent's hook (for logging)
        super()._on_state_changed(old_state, new_state)
        
        # Report status after state change (Elevator-specific)
        self.env.process(self._report_status())
    
    def _update_direction(self, new_direction: str):
        """
        Update direction (Elevator-specific method).
        
        Args:
            new_direction: New direction ("UP", "DOWN", or "NO_DIRECTION")
        """
        if self.direction != new_direction:
            old_direction = self.direction
            self.direction = new_direction
            print(f"{self.env.now:.2f}: [{self.name}] Direction: {old_direction} -> {new_direction}")
            self.env.process(self._report_status())
    
    def set_state_and_direction(self, new_state: str, new_direction: str = None):
        """
        Convenience method to update both state and direction.
        
        Args:
            new_state: New state
            new_direction: New direction (if None, keeps current direction)
        """
        if new_direction is not None and self.direction != new_direction:
            self._update_direction(new_direction)
        self.set_state(new_state)
    
    def _report_status(self):
        status_message = {
            "timestamp": self.env.now,
            "physical_floor": self.current_floor,
            "current_floor": self.current_floor,  # For WebSocket visualization
            "advanced_position": self.advanced_position,
            "state": self.state,
            "direction": self.direction,  # Add direction to status report
            "passengers": len(self.passengers_onboard),
            "passengers_count": len(self.passengers_onboard),  # For WebSocket visualization
            "max_capacity": self.max_capacity,  # For WebSocket visualization
            "num_floors": self.num_floors,  # For WebSocket visualization
            "home_floor": self.home_floor,  # Home floor (for repositioning strategies)
            "main_direction": self.main_direction,  # Main traffic direction (for optimization)
            "move_command_target_floor": self.move_command_target_floor,  # For visualization
            "forced_calls_up": list(self.forced_calls_up),  # For visualization
            "forced_calls_down": list(self.forced_calls_down),  # For visualization
            "service_floors": self.service_floors  # Service floors (floors this elevator can stop at)
        }
        yield self.broker.put(self.status_topic, status_message)

    def _broadcast_hall_calls_status(self):
        """Send hall_calls status"""
        hall_calls_message = {
            "timestamp": self.env.now,
            "elevator_name": self.name,
            "hall_calls_up": list(self.hall_calls_up),
            "hall_calls_down": list(self.hall_calls_down),
            "current_floor": self.current_floor
        }
        hall_calls_topic = f"elevator/{self.name}/hall_calls"
        yield self.broker.put(hall_calls_topic, hall_calls_message)
    
    def _broadcast_forced_calls_status(self):
        """Send forced_calls status (kept separate from hall_calls for tracking)"""
        forced_calls_message = {
            "timestamp": self.env.now,
            "elevator_name": self.name,
            "forced_calls_up": list(self.forced_calls_up),
            "forced_calls_down": list(self.forced_calls_down),
            "current_floor": self.current_floor
        }
        forced_calls_topic = f"elevator/{self.name}/forced_calls"
        yield self.broker.put(forced_calls_topic, forced_calls_message)

    def _broadcast_car_calls_status(self):
        """Send car_calls status"""
        car_calls_message = {
            "timestamp": self.env.now,
            "elevator_name": self.name,
            "car_calls": list(self.car_calls),
            "current_floor": self.current_floor
        }
        car_calls_topic = f"elevator/{self.name}/car_calls"
        yield self.broker.put(car_calls_topic, car_calls_message)

    def _broadcast_new_car_call_registration(self, dest_floor, passenger_name):
        """Send new car_call registration for visualization"""
        new_car_call_message = {
            "timestamp": self.env.now,
            "elevator_name": self.name,
            "destination": dest_floor,
            "passenger_name": passenger_name,
            "current_floor": self.current_floor
        }
        new_car_call_topic = f"elevator/{self.name}/new_car_call"
        yield self.broker.put(new_car_call_topic, new_car_call_message)

    def get_current_capacity(self):
        """Get current number of passengers in elevator."""
        return len(self.passengers_onboard)
    
    def get_max_capacity(self):
        """Get maximum capacity of elevator."""
        return self.max_capacity
    
    def can_serve_floor(self, floor: int) -> bool:
        """
        Check if this elevator can serve (stop at) the specified floor.
        
        Args:
            floor: Control floor number to check
            
        Returns:
            True if this elevator services the floor, False otherwise
        """
        return floor in self.service_floors

    def _should_interrupt(self, new_floor, new_direction):
        """Determine if current movement should be interrupted"""
        if self.state == "IDLE" or self.current_destination is None:
            return False  # No need to interrupt if stopped

        if self.direction == "UP" and new_direction == "UP":
            # During upward movement, is there a call above current position but before destination?
            return self.current_floor < new_floor < self.current_destination
        
        if self.direction == "DOWN" and new_direction == "DOWN":
            # During downward movement, is there a call below current position but before destination?
            return self.current_floor > new_floor > self.current_destination

        return False

    def _hall_call_listener(self):
        task_topic = f"elevator/{self.name}/task"
        while True:
            task = yield self.broker.get(task_topic)
            details = task['details']
            floor, direction = details['floor'], details['direction']
            
            # Reject hall calls for non-service floors
            if not self.can_serve_floor(floor):
                print(f"{self.env.now:.2f} [{self.name}] Hall call rejected: Floor {floor} is not in service floors.")
                continue
            
            if direction == "UP": self.hall_calls_up.add(floor)
            else: self.hall_calls_down.add(floor)
            print(f"{self.env.now:.2f} [{self.name}] Hall call registered: Floor {floor} {direction}.")
            
            # Cancel move command when real hall call is assigned
            if self.move_command_target_floor is not None:
                print(f"{self.env.now:.2f} [{self.name}] Move command cancelled due to real hall call assignment.")
                self.move_command_target_floor = None
            
            # Send hall_calls status
            self.env.process(self._broadcast_hall_calls_status())
            
            # If direction is NO_DIRECTION (idle or about to become idle), update direction
            if self.direction == "NO_DIRECTION":
                self._decide_direction_on_hall_call_assigned()
            
            # Determine if emergency button should be pressed
            if self._should_interrupt(floor, direction):
                print(f"{self.env.now:.2f} [{self.name}] New valid call on the way! INTERRUPTING.")
                self.process.interrupt()
            else:
                 if not self.new_call_event.triggered:
                    self.new_call_event.succeed()
                    self.new_call_event = self.env.event()

    def _car_call_listener(self):
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            car_call = yield self.broker.get(car_call_topic)
            dest_floor = car_call['destination']
            passenger_name = car_call['passenger_name']
            
            # Reject car calls for non-service floors
            if not self.can_serve_floor(dest_floor):
                print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' rejected: Floor {dest_floor} is not in service floors.")
                continue
            
            # Ignore already registered car_calls (actual elevator behavior)
            if dest_floor in self.car_calls:
                print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' for {dest_floor} - already registered (button already lit).")
                continue
            
            # Register only new car_calls
            self.car_calls.add(dest_floor)
            print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' registered for {dest_floor}.")
            
            # Send new car_call registration message for visualization
            self.env.process(self._broadcast_new_car_call_registration(dest_floor, passenger_name))
            
            # Send car_calls status
            self.env.process(self._broadcast_car_calls_status())
            
            # TODO: Implement interruption for car calls as well
            if not self.new_call_event.triggered:
                self.new_call_event.succeed()
                self.new_call_event = self.env.event()

    def _move_command_listener(self):
        """
        Receive move command (only when idle)
        
        Receives move commands from the group control system.
        Reception condition: Only when elevator is in IDLE state
        Behavior: Moves to specified floor but does NOT open door
        Cancellation: Cancelled when real hall call is assigned
        """
        move_command_topic = f"elevator/{self.name}/move_command"
        while True:
            command = yield self.broker.get(move_command_topic)
            target_floor = command['floor']
            
            # Reject move commands for non-service floors
            if not self.can_serve_floor(target_floor):
                print(f"{self.env.now:.2f} [{self.name}] Move command rejected: Floor {target_floor} is not in service floors.")
                continue
            
            # Check reception condition: Only when IDLE state and NO_DIRECTION
            if self.state == "IDLE" and self.direction == "NO_DIRECTION":
                self.move_command_target_floor = target_floor
                print(f"{self.env.now:.2f} [{self.name}] Move command received: target floor {target_floor}")
                
                # Trigger new call event to start movement
                if not self.new_call_event.triggered:
                    self.new_call_event.succeed()
                    self.new_call_event = self.env.event()
            else:
                print(f"{self.env.now:.2f} [{self.name}] Move command ignored (not IDLE): target floor {target_floor}")

    def _forced_move_command_listener(self):
        """
        Receive forced move command (in any state)
        
        Receives forced move commands from the group control system.
        Reception condition: Always received regardless of elevator state
        Behavior: Treated as real hall call, selective collective response applied
        Cancellation: Not cancelled (treated same as real hall call)
        """
        forced_move_command_topic = f"elevator/{self.name}/forced_move_command"
        while True:
            command = yield self.broker.get(forced_move_command_topic)
            floor = command['floor']
            direction = command['direction']
            
            # Reject forced move commands for non-service floors
            if not self.can_serve_floor(floor):
                print(f"{self.env.now:.2f} [{self.name}] Forced move command rejected: Floor {floor} is not in service floors.")
                continue
            
            # Register in separate set to distinguish from real hall calls
            if direction == "UP":
                self.forced_calls_up.add(floor)
            else:
                self.forced_calls_down.add(floor)
            
            print(f"{self.env.now:.2f} [{self.name}] Forced move command registered: Floor {floor} {direction} (kept separate from real hall calls)")
            
            # Broadcast both hall calls and forced calls status
            self.env.process(self._broadcast_hall_calls_status())
            self.env.process(self._broadcast_forced_calls_status())
            
            # If direction is NO_DIRECTION (idle or about to become idle), update direction
            if self.direction == "NO_DIRECTION":
                self._decide_direction_on_hall_call_assigned()
            
            # Determine if emergency button should be pressed
            if self._should_interrupt(floor, direction):
                print(f"{self.env.now:.2f} [{self.name}] Forced move command on the way! INTERRUPTING.")
                self.process.interrupt()
            else:
                if not self.new_call_event.triggered:
                    self.new_call_event.succeed()
                    self.new_call_event = self.env.event()


    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor 1.")
        self.env.process(self._report_status())

        while True:
            if self._should_stop_at_current_floor():
                self.set_state("STOPPING")
                yield self.env.process(self._handle_boarding_and_alighting())
            
            self._decide_next_direction()
            
            if self.direction == "NO_DIRECTION":
                self.set_state_and_direction("IDLE", "NO_DIRECTION")
                self.current_destination = None
                
                # Check if there's a move command to execute
                if self.move_command_target_floor is not None and self.move_command_target_floor != self.current_floor:
                    # Execute move command
                    print(f"{self.env.now:.2f} [{self.name}] Executing move command to floor {self.move_command_target_floor}")
                    self.current_destination = self.move_command_target_floor
                    
                    # Determine direction for move command
                    if self.current_destination > self.current_floor:
                        self._update_direction("UP")
                    else:
                        self._update_direction("DOWN")
                    
                    # Move to target floor
                    self.set_state("MOVING")
                    try:
                        self.current_move_process = self.env.process(self._move_process(self.current_destination))
                        yield self.current_move_process
                        
                        # Arrived at move command target floor - do NOT open door
                        print(f"{self.env.now:.2f} [{self.name}] Arrived at move command target floor {self.current_floor}. Door remains closed.")
                        
                        # Clear move command
                        self.move_command_target_floor = None
                        
                        # Reset direction to NO_DIRECTION
                        self._update_direction("NO_DIRECTION")
                        
                    except Interrupt:
                        print(f"{self.env.now:.2f} [{self.name}] Move command interrupted by new call.")
                        if self.current_move_process and self.current_move_process.is_alive:
                            self.current_move_process.interrupt()
                        self.current_move_process = None
                        # Move command should already be cancelled by _hall_call_listener
                    
                    continue  # Return to loop start for re-evaluation
                
                if not self._has_any_calls():
                    print(f"{self.env.now:.2f} [{self.name}] IDLE. Waiting for new call signal...")
                    yield self.new_call_event
                continue  # Return to loop start for re-evaluation

            # New operation logic starts here
            self.current_destination = self._get_next_stop_floor()

            if self.current_destination is None:
                self.set_state_and_direction("IDLE", "NO_DIRECTION")
                continue

            # This try block is the interruptible flight plan
            self.set_state("MOVING")
            try:
                # Track current movement process
                self.current_move_process = self.env.process(self._move_process(self.current_destination))
                yield self.current_move_process
            except Interrupt:
                # Emergency call from radio operator!
                print(f"{self.env.now:.2f} [{self.name}] Movement interrupted by new call. Re-evaluating next stop.")
                # Cancel old movement process
                if self.current_move_process and self.current_move_process.is_alive:
                    self.current_move_process.interrupt()
                self.current_move_process = None
                # Return to loop start will automatically recalculate new destination
                continue

    def _move_process(self, destination_floor):
        """Movement process using cruise_table/brake_table"""
        if self.use_table_method and self.physics_engine:
            return self._move_process_with_tables(destination_floor)
        else:
            return self._move_process_with_timeline(destination_floor)
    
    def _move_process_with_tables(self, destination_floor):
        """Table-based movement process (corrected version)"""
        if self.current_floor == destination_floor:
            print(f"{self.env.now:.2f} [{self.name}] Already at destination floor {destination_floor}")
            return
        
        # Remember the "departure floor" for this continuous trip
        start_floor_of_this_trip = self.current_floor
        
        direction = 1 if destination_floor > start_floor_of_this_trip else -1
        total_time = self.physics_engine.flight_time_table.get((start_floor_of_this_trip, destination_floor), 0)
        
        print(f"{self.env.now:.2f} [{self.name}] Moving from floor {start_floor_of_this_trip} to {destination_floor} (total {total_time:.2f}s) [TABLE METHOD]...")
        
        try:
            current_floor_in_trip = start_floor_of_this_trip
            
            # Move through each floor sequentially (cruise phase)
            while current_floor_in_trip != destination_floor:
                # Interruption check
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                next_floor = current_floor_in_trip + direction
                
                # Complete fix: Update state with same timing as timeline method
                # Step 1: Use remembered "departure floor" as key
                cruise_time = self.physics_engine.cruise_table.get((start_floor_of_this_trip, next_floor), 0.1)
                
                # Step 2: Execute cruise phase first to advance time (same as timeline method)
                yield self.env.timeout(cruise_time)
                
                # Step 3: Re-check for interruption
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                # Step 4: Update physical floor after time has passed
                old_floor = current_floor_in_trip
                current_floor_in_trip = next_floor
                self.current_floor = current_floor_in_trip
                
                # Update Door object's current floor as well
                if hasattr(self.door, 'set_current_floor'):
                    self.door.set_current_floor(self.current_floor)
                
                # Step 5: Update predicted position (advanced_position)
                # Same logic as timeline method: same value as currently reached floor
                self.advanced_position = current_floor_in_trip
                
                # Step 6: Report status (after time has passed)
                if self.advanced_position != self.last_advanced_position:
                    self.env.process(self._report_status())
                self.last_advanced_position = self.advanced_position
                
                # Reverse movement check
                if self.direction == "UP" and current_floor_in_trip < old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {current_floor_in_trip}F")
                    return
                elif self.direction == "DOWN" and current_floor_in_trip > old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {current_floor_in_trip}F")
                    return
            
            # Use remembered "departure floor" as key here as well
            brake_time = self.physics_engine.brake_table.get((start_floor_of_this_trip, destination_floor), 0.1)
            
            # Final braking phase - CRITICAL: This is where direction should be finalized
            if brake_time > self.MIN_BRAKE_TIME_THRESHOLD:
                # Enter DECELERATING state
                self.set_state("DECELERATING")
                
                # Re-evaluate direction at deceleration start (THIS FIXES THE BUG!)
                self._decide_next_direction()
                
                # Check if direction changed - if so, abort movement
                expected_direction = "UP" if destination_floor > start_floor_of_this_trip else "DOWN"
                if self.direction != expected_direction and self.direction != "NO_DIRECTION":
                    print(f"{self.env.now:.2f} [{self.name}] Direction changed during deceleration! Expected {expected_direction}, now {self.direction}. Aborting movement.")
                    return
                
                yield self.env.timeout(brake_time)
                
                # Final interruption check
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled during final braking.")
                    return
            
            print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            
        except Interrupt:
            print(f"{self.env.now:.2f} [{self.name}] Table-based movement process interrupted and terminated.")
            return
    
    def _move_process_with_timeline(self, destination_floor):
        """Timeline-based movement process"""
        profile = self.flight_profiles.get((self.current_floor, destination_floor))
        if not profile or not profile.get('timeline'):
            print(f"[{self.name}] Warning: No profile found for {self.current_floor} -> {destination_floor}")
            return

        print(f"{self.env.now:.2f} [{self.name}] Moving from floor {self.current_floor} to {destination_floor} (total {profile['total_time']:.2f}s)...")
        
        try:
            for i, event in enumerate(profile['timeline']):
                # Interruption check: abort if destination changed during movement
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                # Do NOT change direction during movement - wait until after arrival
                # Direction change will be handled by _decide_next_direction() after boarding/alighting
                    
                yield self.env.timeout(event['time_delta'])
                
                # Re-check for interruption
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                old_floor = self.current_floor
                self.current_floor = event['advanced_position']  # Fixed: changed from physical_floor to advanced_position
                self.advanced_position = event['advanced_position']
                
                # Update Door object's current floor as well
                if hasattr(self.door, 'set_current_floor'):
                    self.door.set_current_floor(self.current_floor)
                
                # Reverse movement check
                if self.direction == "UP" and self.current_floor < old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {self.current_floor}F (Event {i})")
                    return
                elif self.direction == "DOWN" and self.current_floor > old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {self.current_floor}F (Event {i})")
                    return
                
                if self.advanced_position != self.last_advanced_position:
                    self.env.process(self._report_status())
                self.last_advanced_position = self.advanced_position
            
            print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            
        except Interrupt:
            # Quietly exit on interruption (logging is done at higher level)
            print(f"{self.env.now:.2f} [{self.name}] Movement process interrupted and terminated.")
            return

    def _get_all_up_calls(self):
        """Get all UP calls (hall calls + forced calls)"""
        return self.hall_calls_up | self.forced_calls_up
    
    def _get_all_down_calls(self):
        """Get all DOWN calls (hall calls + forced calls)"""
        return self.hall_calls_down | self.forced_calls_down

    def _get_next_stop_floor(self):
        if self.direction == "UP":
            up_calls = [f for f in (self.car_calls | self._get_all_up_calls()) if f > self.current_floor]
            if up_calls: return min(up_calls)
            all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
            if all_calls: return max(all_calls)

        elif self.direction == "DOWN":
            down_calls = [f for f in (self.car_calls | self._get_all_down_calls()) if f < self.current_floor]
            if down_calls: return max(down_calls)
            all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
            if all_calls: return min(all_calls)
        
        return None

    def _handle_boarding_and_alighting(self):
        print(f"{self.env.now:.2f} [{self.name}] Handling boarding and alighting at floor {self.current_floor}.")
        passengers_to_exit = sorted([p for p in self.passengers_onboard if p.destination_floor == self.current_floor], key=lambda p: p.entity_id, reverse=True)

        boarding_queues = []
        
        # Check if there are calls (hall or forced) at current floor
        all_up_calls = self._get_all_up_calls()
        all_down_calls = self._get_all_down_calls()
        
        # Determine which direction to serve based on current direction
        if self.direction == "UP":
            # Moving UP: serve UP passengers first (hall calls or forced calls)
            if self.current_floor in all_up_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["UP"])
            # Only serve DOWN passengers if no more calls above (direction change)
            elif self.current_floor in all_down_calls and not self._has_any_calls_above():
                boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])
        
        elif self.direction == "DOWN":
            # Moving DOWN: serve DOWN passengers first (hall calls or forced calls)
            if self.current_floor in all_down_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])
            # Only serve UP passengers if no more calls below (direction change)
            elif self.current_floor in all_up_calls and not self._has_any_calls_below():
                boarding_queues.append(self.floor_queues[self.current_floor]["UP"])
        
        elif self.direction == "NO_DIRECTION":
            # NO_DIRECTION state: determine direction based on calls
            has_calls_above = self._has_any_calls_above()
            has_calls_below = self._has_any_calls_below()
            
            # Prefer UP if there are calls above
            if has_calls_above and self.current_floor in all_up_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["UP"])
            # If only calls below, serve DOWN
            elif has_calls_below and self.current_floor in all_down_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])
            # If no calls above/below, serve whichever is available at current floor
            elif self.current_floor in all_up_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["UP"])
            elif self.current_floor in all_down_calls:
                boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])

        # Check if current floor has a car call (for door to send OFF message at opening complete)
        has_car_call_here = self.current_floor in self.car_calls
        
        # Check if current floor is DCS floor (for automatic car call registration)
        is_dcs_floor = False
        if self.call_system:
            is_dcs_floor = self.call_system.is_dcs_floor(self.current_floor)
        
        # Call door boarding and alighting process
        # Door will get capacity information from elevator via getters
        boarding_process = self.env.process(self.door.handle_boarding_and_alighting_process(
            passengers_to_exit, boarding_queues, has_car_call_here, is_dcs_floor=is_dcs_floor))
        report = yield boarding_process
        
        # Passengers are already removed/added by Door in real-time
        # No need to process them again here
        boarded_passengers = report.get("boarded", [])
        
        # Send failure notification to passengers who couldn't board
        failed_to_board_passengers = report.get("failed_to_board", [])
        for p in failed_to_board_passengers:
            print(f"{self.env.now:.2f} [{self.name}] Notifying {p.name} that boarding failed.")
            # Notify passenger of boarding failure
            failed_notification = self.env.event()
            failed_notification.succeed()
            yield p.boarding_failed_event.put(failed_notification)

        # Clear car call for current floor
        # (Note: car_call_off message is now sent by Door at opening complete)
        car_calls_changed = False
        if self.current_floor in self.car_calls:
            self.car_calls.discard(self.current_floor)
            car_calls_changed = True
        
        hall_calls_changed = False
        forced_calls_changed = False
        serviced_directions = []  # Record directions that should be turned off
        
        # Clear hall calls and forced calls for directions that were serviced
        if any(q == self.floor_queues[self.current_floor]["UP"] for q in boarding_queues):
            # Check if anyone from this direction actually boarded
            if len(boarded_passengers) > 0:
                # Clear hall calls (only if someone boarded)
                if self.current_floor in self.hall_calls_up:
                    self.hall_calls_up.discard(self.current_floor)
                    hall_calls_changed = True
                # Always clear forced calls when serviced (even if no one boarded, door was opened)
                if self.current_floor in self.forced_calls_up:
                    self.forced_calls_up.discard(self.current_floor)
                    forced_calls_changed = True
                serviced_directions.append("UP")
            else:
                print(f"{self.env.now:.2f} [{self.name}] No one boarded from UP queue (full). Keeping hall call.")
                # Still clear forced calls even if full (door was opened as instructed)
                if self.current_floor in self.forced_calls_up:
                    self.forced_calls_up.discard(self.current_floor)
                    forced_calls_changed = True
        
        if any(q == self.floor_queues[self.current_floor]["DOWN"] for q in boarding_queues):
            # Check if anyone from this direction actually boarded
            if len(boarded_passengers) > 0:
                # Clear hall calls (only if someone boarded)
                if self.current_floor in self.hall_calls_down:
                    self.hall_calls_down.discard(self.current_floor)
                    hall_calls_changed = True
                # Always clear forced calls when serviced (even if no one boarded, door was opened)
                if self.current_floor in self.forced_calls_down:
                    self.forced_calls_down.discard(self.current_floor)
                    forced_calls_changed = True
                serviced_directions.append("DOWN")
            else:
                print(f"{self.env.now:.2f} [{self.name}] No one boarded from DOWN queue (full). Keeping hall call.")
                # Still clear forced calls even if full (door was opened as instructed)
                if self.current_floor in self.forced_calls_down:
                    self.forced_calls_down.discard(self.current_floor)
                    forced_calls_changed = True
        
        # Turn off hall buttons for serviced directions
        if serviced_directions and self.hall_buttons:
            for direction in serviced_directions:
                button = self.hall_buttons[self.current_floor][direction]
                button.serve(elevator_name=self.name)  # Turn off button with elevator name
        
        # Send status if car_calls changed
        if car_calls_changed:
            self.env.process(self._broadcast_car_calls_status())
        
        # Send status if hall_calls changed
        if hall_calls_changed:
            self.env.process(self._broadcast_hall_calls_status())
        
        # Send status if forced_calls changed
        if forced_calls_changed:
            self.env.process(self._broadcast_forced_calls_status())
        
        print(f"{self.env.now:.2f} [{self.name}] Boarding and alighting at floor {self.current_floor} complete.")
        self.env.process(self._report_status())
    
    def _is_at_full_capacity(self):
        """
        Check if elevator is at full capacity.
        
        Returns:
            True if full, False otherwise
        """
        if self.max_capacity is None:
            return False
        return len(self.passengers_onboard) >= self.max_capacity
    
    def _log_full_load_bypass(self, direction):
        """
        Log full load bypass event to message broker.
        
        Args:
            direction: Direction of the hall call being bypassed ("UP" or "DOWN")
        """
        self.broker.put('elevator/full_load_bypass', {
            'elevator': self.name,
            'floor': self.current_floor,
            'direction': direction,
            'passengers': len(self.passengers_onboard),
            'capacity': self.max_capacity,
            'timestamp': self.env.now
        })
    
    def _should_bypass_due_to_full_capacity(self, direction: str, reason: str = "hall call") -> bool:
        """
        Check if elevator should bypass stop due to full capacity
        
        Args:
            direction: Direction being bypassed ("UP" or "DOWN")
            reason: Reason for bypass (e.g., "hall call UP", "direction change")
        
        Returns:
            True if should bypass, False otherwise
        """
        if not self.full_load_bypass:
            return False
        
        if not self._is_at_full_capacity():
            return False
        
        # Log with timestamp and elevator name (important for debugging)
        print(f"{self.env.now:.2f} [{self.name}] Full load bypass: Full capacity at floor {self.current_floor}, bypassing {reason}.")
        self._log_full_load_bypass(direction)
        return True
    
    def _should_stop_at_current_floor(self):
        # NEVER stop at non-service floors
        if not self.can_serve_floor(self.current_floor):
            return False
        
        # Always stop for car calls (passengers need to exit)
        if self.current_floor in self.car_calls:
            return True
        
        all_up_calls = self._get_all_up_calls()
        all_down_calls = self._get_all_down_calls()
        
        # Always stop for forced calls (must open door regardless of capacity)
        if self.current_floor in self.forced_calls_up or self.current_floor in self.forced_calls_down:
            return True
        
        # Check hall calls with full_load_bypass consideration
        if self.direction == "UP":
            if self.current_floor in self.hall_calls_up:
                if self._should_bypass_due_to_full_capacity("UP", "hall call UP"):
                    return False
                return True
            all_calls = self.car_calls | all_up_calls | all_down_calls
            if not self._has_any_calls_above() and all_calls and self.current_floor == max(all_calls):
                # Direction change case: check if we can board
                direction = "UP" if self.current_floor in all_up_calls else "DOWN"
                if self._should_bypass_due_to_full_capacity(direction, "direction change"):
                    return False
                return True

        elif self.direction == "DOWN":
            if self.current_floor in self.hall_calls_down:
                if self._should_bypass_due_to_full_capacity("DOWN", "hall call DOWN"):
                    return False
                return True
            all_calls = self.car_calls | all_up_calls | all_down_calls
            if not self._has_any_calls_below() and all_calls and all_calls and self.current_floor == min(all_calls):
                # Direction change case: check if we can board
                direction = "DOWN" if self.current_floor in all_down_calls else "UP"
                if self._should_bypass_due_to_full_capacity(direction, "direction change"):
                    return False
                return True

        elif self.direction == "NO_DIRECTION":
            has_call = self._has_any_calls_at_current_floor()
            if has_call:
                # Check if we can board (only hall calls possible in NO_DIRECTION at current floor)
                direction = "UP" if self.current_floor in all_up_calls else "DOWN"
                if self._should_bypass_due_to_full_capacity(direction, "hall call"):
                    return False
            return has_call

        return False

    def _decide_direction_on_hall_call_assigned(self):
        """Decide direction when a new hall call is assigned while NO_DIRECTION.
        
        This is specifically for real-time direction updates when receiving hall calls
        while the elevator is idle, stopping, or decelerating to a stop.
        Excludes current floor to determine the next travel direction.
        """
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        
        if not all_calls:
            return
        
        # Exclude current floor (might still be stopping/processing there)
        calls_excluding_current = all_calls - {self.current_floor}
        
        if calls_excluding_current:
            # There are calls on other floors - determine direction to them
            closest_call = min(calls_excluding_current, key=lambda f: abs(f - self.current_floor))
            if closest_call > self.current_floor:
                self._update_direction("UP")
            else:
                self._update_direction("DOWN")
        else:
            # Only current floor has calls - check hall call direction at current floor
            all_up_calls = self._get_all_up_calls()
            all_down_calls = self._get_all_down_calls()
            if self.current_floor in all_up_calls:
                self._update_direction("UP")
            elif self.current_floor in all_down_calls:
                self._update_direction("DOWN")
    
    def _is_at_top_call(self):
        """Check if current floor is the highest call"""
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        return all_calls and max(all_calls) == self.current_floor
    
    def _is_at_bottom_call(self):
        """Check if current floor is the lowest call"""
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        return all_calls and min(all_calls) == self.current_floor
    
    def _is_past_farthest_call(self, direction):
        """Check if current floor is past the farthest call in given direction"""
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        if not all_calls:
            return False
        
        if direction == "UP":
            farthest_call = max(all_calls)
            return self.current_floor > farthest_call
        else:  # DOWN
            farthest_call = min(all_calls)
            return self.current_floor < farthest_call
    
    def _decide_next_direction(self):
        """
        Decide next direction (only updates direction, not state)
        
        Router method that delegates to direction-specific logic
        """
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()

        if not all_calls:
            self._update_direction("NO_DIRECTION")
            return

        if self.direction == "UP":
            self._decide_from_up_direction()
        elif self.direction == "DOWN":
            self._decide_from_down_direction()
        elif self.direction == "NO_DIRECTION":
            self._decide_from_no_direction()
    
    def _decide_from_up_direction(self):
        """Decide direction when currently moving UP"""
        # If there are calls above, keep going UP
        if self._has_any_calls_above():
            return
            
        # If at the top call, handle direction reversal
        if self._is_at_top_call():
            self._handle_top_call_reversal()
            return
        
        # If past the farthest call, reverse to DOWN
        if self._is_past_farthest_call("UP"):
            self._update_direction("DOWN")
    
    def _decide_from_down_direction(self):
        """Decide direction when currently moving DOWN"""
        # If there are calls below, keep going DOWN
        if self._has_any_calls_below():
            return
        
        # If at the bottom call, handle direction reversal
        if self._is_at_bottom_call():
            self._handle_bottom_call_reversal()
            return
                
        # If past the farthest call, reverse to UP
        if self._is_past_farthest_call("DOWN"):
            self._update_direction("UP")
    
    def _decide_from_no_direction(self):
        """Decide direction when currently in NO_DIRECTION state"""
        if not self._has_any_calls():
            return
        
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))
        
        if closest_call > self.current_floor:
            self._update_direction("UP")
        elif closest_call < self.current_floor:
            self._update_direction("DOWN")
        else:
            # Closest call is at current floor - check direction
            all_up_calls = self._get_all_up_calls()
            all_down_calls = self._get_all_down_calls()
            if self.current_floor in all_up_calls:
                self._update_direction("UP")
            elif self.current_floor in all_down_calls:
                self._update_direction("DOWN")
    
    def _handle_top_call_reversal(self):
        """Handle direction decision when at the top call (during UP movement)"""
        all_down_calls = self._get_all_down_calls()
        all_up_calls = self._get_all_up_calls()
        
        # First, check if there's a call at current floor
        if self.current_floor in all_down_calls:
            self._update_direction("DOWN")
            return
        elif self.current_floor in all_up_calls:
            # UP call at current floor - keep UP direction
            return
        
        # No call at current floor, check where other calls are
        all_hall_calls = all_up_calls | all_down_calls
        if all_hall_calls:
            # Determine direction based on call positions
            has_calls_above = any(f > self.current_floor for f in all_hall_calls)
            has_calls_below = any(f < self.current_floor for f in all_hall_calls)
            
            if has_calls_below:
                self._update_direction("DOWN")
            elif has_calls_above:
                self._update_direction("UP")
        else:
            # No hall calls anywhere - set to NO_DIRECTION
            self._update_direction("NO_DIRECTION")
    
    def _handle_bottom_call_reversal(self):
        """Handle direction decision when at the bottom call (during DOWN movement)"""
        all_up_calls = self._get_all_up_calls()
        all_down_calls = self._get_all_down_calls()
        
        # First, check if there's a call at current floor
        if self.current_floor in all_up_calls:
            self._update_direction("UP")
            return
        elif self.current_floor in all_down_calls:
            # DOWN call at current floor - keep DOWN direction
            return
                
        # No call at current floor, check where other calls are
        all_hall_calls = all_up_calls | all_down_calls
        if all_hall_calls:
            # Determine direction based on call positions
            has_calls_above = any(f > self.current_floor for f in all_hall_calls)
            has_calls_below = any(f < self.current_floor for f in all_hall_calls)
            
            if has_calls_above:
                self._update_direction("UP")
            elif has_calls_below:
                self._update_direction("DOWN")
        else:
            # No hall calls anywhere - set to NO_DIRECTION
            self._update_direction("NO_DIRECTION")

    def _has_any_calls(self):
        return bool(self.car_calls or self.hall_calls_up or self.hall_calls_down or self.forced_calls_up or self.forced_calls_down)

    def _has_any_calls_at_current_floor(self):
        return (self.current_floor in self.car_calls or
                self.current_floor in self.hall_calls_up or
                self.current_floor in self.hall_calls_down or
                self.current_floor in self.forced_calls_up or
                self.current_floor in self.forced_calls_down)

    def _has_any_calls_above(self):
        """Check if there are any calls (car or hall or forced, any direction) above current floor"""
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        return any(f > self.current_floor for f in all_calls)

    def _has_any_calls_below(self):
        """Check if there are any calls (car or hall or forced, any direction) below current floor"""
        all_calls = self.car_calls | self._get_all_up_calls() | self._get_all_down_calls()
        return any(f < self.current_floor for f in all_calls)

    def _predict_next_direction_at_arrival(self, arrival_floor):
        """
        Predict next direction at arrival floor in advance.
        
        IMPORTANT: Direction should only change if elevator will stop at arrival floor.
        If not stopping, direction must remain unchanged during braking.
        
        Args:
            arrival_floor: Floor number where elevator will arrive
        
        Returns:
            Predicted direction ("UP", "DOWN", or "NO_DIRECTION")
        """
        will_stop_at_arrival = False
        
        all_up_calls = self._get_all_up_calls()
        all_down_calls = self._get_all_down_calls()
        
        if self.direction == "UP":
            if arrival_floor in self.car_calls:
                will_stop_at_arrival = True
            elif arrival_floor in all_up_calls:
                will_stop_at_arrival = True
            else:
                all_calls = self.car_calls | all_up_calls | all_down_calls
                if not self._has_any_calls_above() and all_calls and arrival_floor == max(all_calls):
                    will_stop_at_arrival = True
        elif self.direction == "DOWN":
            if arrival_floor in self.car_calls:
                will_stop_at_arrival = True
            elif arrival_floor in all_down_calls:
                will_stop_at_arrival = True
            else:
                all_calls = self.car_calls | all_up_calls | all_down_calls
                if not self._has_any_calls_below() and all_calls and arrival_floor == min(all_calls):
                    will_stop_at_arrival = True
        
        # If we won't stop at arrival floor, don't change direction prematurely
        if not will_stop_at_arrival:
            return self.direction
        
        # Simulate post-arrival situation (assuming service completion at arrival floor)
        future_car_calls = self.car_calls.copy()
        future_hall_calls_up = self.hall_calls_up.copy()
        future_hall_calls_down = self.hall_calls_down.copy()
        future_forced_calls_up = self.forced_calls_up.copy()
        future_forced_calls_down = self.forced_calls_down.copy()
        
        # Remove calls at arrival floor (will be serviced)
        future_car_calls.discard(arrival_floor)
        
        # Remove hall_calls and forced_calls to be serviced based on current direction
        if self.direction in ["NO_DIRECTION", "UP"] and arrival_floor in future_hall_calls_up:
            future_hall_calls_up.discard(arrival_floor)
        if self.direction in ["NO_DIRECTION", "UP"] and arrival_floor in future_forced_calls_up:
            future_forced_calls_up.discard(arrival_floor)
        if self.direction in ["NO_DIRECTION", "DOWN"] and arrival_floor in future_hall_calls_down:
            future_hall_calls_down.discard(arrival_floor)
        if self.direction in ["NO_DIRECTION", "DOWN"] and arrival_floor in future_forced_calls_down:
            future_forced_calls_down.discard(arrival_floor)
        # Service DOWN calls even during UP movement when reaching top floor
        if self.direction == "UP":
            if arrival_floor in future_hall_calls_down or arrival_floor in future_forced_calls_down:
                up_calls_above = any(f > arrival_floor for f in future_car_calls | future_hall_calls_up | future_forced_calls_up)
            if not up_calls_above:
                future_hall_calls_down.discard(arrival_floor)
                future_forced_calls_down.discard(arrival_floor)
        # Service UP calls even during DOWN movement when reaching bottom floor
        if self.direction == "DOWN":
            if arrival_floor in future_hall_calls_up or arrival_floor in future_forced_calls_up:
                down_calls_below = any(f < arrival_floor for f in future_car_calls | future_hall_calls_down | future_forced_calls_down)
            if not down_calls_below:
                future_hall_calls_up.discard(arrival_floor)
                future_forced_calls_up.discard(arrival_floor)
        
        # Determine next direction from remaining calls (including forced calls)
        all_remaining_calls = future_car_calls | future_hall_calls_up | future_hall_calls_down | future_forced_calls_up | future_forced_calls_down
        
        if not all_remaining_calls:
            return "NO_DIRECTION"
        
        # Check upward and downward calls
        up_calls = [f for f in all_remaining_calls if f > arrival_floor]
        down_calls = [f for f in all_remaining_calls if f < arrival_floor]
        
        if up_calls and not down_calls:
            return "UP"
        elif down_calls and not up_calls:
            return "DOWN"
        elif up_calls and down_calls:
            # If calls in both directions, continue current direction
            return self.direction if self.direction in ["UP", "DOWN"] else "UP"
        else:
            return "NO_DIRECTION"

