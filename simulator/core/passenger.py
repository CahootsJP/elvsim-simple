import simpy
from .entity import Entity
from ..infrastructure.message_broker import MessageBroker
from .hall_button import HallButton

class Passenger(Entity):
    """
    [v13.0] Passenger who boards and exits at their own will
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, 
                 hall_buttons, floor_queues, arrival_floor: int, destination_floor: int, move_speed: float):
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        
        self.arrival_floor = arrival_floor
        self.destination_floor = destination_floor
        self.move_speed = move_speed

        # To wait for permission from Door
        # Using Store allows receiving "completion reporting event" along with permission
        self.board_permission_event = simpy.Store(env, capacity=1)
        self.exit_permission_event = simpy.Store(env, capacity=1)
        
        # For boarding failure notification
        self.boarding_failed_event = simpy.Store(env, capacity=1)
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor} (Move time: {self.move_speed:.1f}s).")

    def is_front_of_queue(self, queue):
        """Check if this passenger is at the front of the queue"""
        if len(queue.items) == 0:
            return False
        return queue.items[0] == self

    def run(self):
        """Passenger's autonomous lifecycle with retry logic"""
        yield self.env.timeout(1)
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
        CHECK_INTERVAL = 0.1  # Check every 0.1 second (fast response with minimal overhead)
        
        while not boarded_successfully:
            # Wait for next check interval
            yield self.env.timeout(CHECK_INTERVAL)
            
            # Check 1: If I'm at front and button is OFF, press it
            if self.is_front_of_queue(current_queue) and not button.is_lit():
                print(f"{self.env.now:.2f} [{self.name}] I'm at front and button is OFF. Pressing button!")
                button.press(passenger_name=self.name)
            
            # Check 2: Has boarding permission arrived?
            if len(self.board_permission_event.items) > 0:
                # Get permission data
                permission_data = yield self.board_permission_event.get()
                completion_event = permission_data['completion_event']
                elevator_name = permission_data.get('elevator_name', None)
                
                print(f"{self.env.now:.2f} [{self.name}] Boarding elevator.")
                
                # Publish passenger boarding event
                self.broker.put('passenger/boarding', {
                    'passenger_name': self.name,
                    'floor': self.arrival_floor,
                    'direction': direction,
                    'elevator_name': elevator_name,
                    'timestamp': self.env.now
                })
                
                yield self.env.timeout(self.move_speed)

                # Board the elevator and press destination button
                print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
                car_call_topic = f"elevator/{elevator_name}/car_call"
                self.broker.put(car_call_topic, {'destination': self.destination_floor, 'passenger_name': self.name})

                # Report to Door that "boarding is complete"
                completion_event.succeed()
                
                boarded_successfully = True
            
            # Check 3: Has boarding failed?
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
        
        # 9. Report to Door that "exiting is complete"
        completion_event.succeed()
        
        print(f"{self.env.now:.2f} [{self.name}] Journey complete.")

