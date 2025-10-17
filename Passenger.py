import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton

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

    def run(self):
        """Passenger's autonomous lifecycle with retry logic"""
        yield self.env.timeout(1)
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button = self.hall_buttons[self.arrival_floor][direction]
        
        boarded_successfully = False
        
        # Loop until boarding succeeds
        while not boarded_successfully:
            # 1. Press hall button (with duplicate check functionality)
            if button.is_lit():
                print(f"{self.env.now:.2f} [{self.name}] Hall button at floor {self.arrival_floor} ({direction}) already lit. No need to press.")
            else:
                button.press(passenger_name=self.name)

            # 2. Join the queue in the correct direction
            current_queue = self.floor_queues[self.arrival_floor][direction]
            print(f"{self.env.now:.2f} [{self.name}] Now waiting in '{direction}' queue at floor {self.arrival_floor}.")
            yield current_queue.put(self)

            # 3. Wait for either "please board" or "boarding failed" notification
            # Use AnyOf to wait for either event
            board_get = self.board_permission_event.get()
            fail_get = self.boarding_failed_event.get()
            results = yield board_get | fail_get
            
            # Check which event fired
            if board_get in results:
                # Boarding permission received
                completion_event = results[board_get]
                print(f"{self.env.now:.2f} [{self.name}] Boarding elevator.")
                yield self.env.timeout(self.move_speed)

                # 5. Board the elevator and press destination button
                print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
                car_call_topic = "elevator/Elevator_1/car_call"
                self.broker.put(car_call_topic, {'destination': self.destination_floor, 'passenger_name': self.name})

                # 6. Report to Door that "boarding is complete"
                completion_event.succeed()
                
                boarded_successfully = True
                
            else:
                # Boarding failure notification received
                print(f"{self.env.now:.2f} [{self.name}] Failed to board (capacity full). Waiting for button OFF to retry...")
                button_off_event = button.wait_for_button_off()
                yield button_off_event
                print(f"{self.env.now:.2f} [{self.name}] Button OFF detected. Will retry boarding.")

        # 7. Wait for "please exit" permission from Door at destination
        completion_event = yield self.exit_permission_event.get()

        # 8. Exit the elevator at own pace
        print(f"{self.env.now:.2f} [{self.name}] Exiting elevator.")
        yield self.env.timeout(self.move_speed)
        
        # 9. Report to Door that "exiting is complete"
        completion_event.succeed()
        
        print(f"{self.env.now:.2f} [{self.name}] Journey complete.")

