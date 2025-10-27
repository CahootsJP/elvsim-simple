import simpy
from ..infrastructure.message_broker import MessageBroker

class HallButton:
    """
    Elevator hall call button (with state management functionality)
    """
    def __init__(self, env: simpy.Environment, floor: int, direction: str, broker: MessageBroker):
        """
        Args:
            env (simpy.Environment): SimPy environment
            floor (int): Floor where the button is installed
            direction (str): 'UP' or 'DOWN'
            broker (MessageBroker): Message broker that mediates communication
        """
        self.env = env
        self.floor = floor
        self.direction = direction
        self.broker = broker
        self.is_pressed = False
        self.button_off_events = []  # List of events waiting for button OFF

    def is_lit(self):
        """Check if the button is lit"""
        return self.is_pressed
    
    def wait_for_button_off(self):
        """Create and return an event to wait for button OFF"""
        event = self.env.event()
        self.button_off_events.append(event)
        return event
    
    def press(self, passenger_name=None):
        """Process when button is pressed"""
        if not self.is_pressed:
            self.is_pressed = True
            print(f"{self.env.now:.2f} [HallButton] Button pressed at floor {self.floor} ({self.direction}). Light ON.")
            
            call_message = {'floor': self.floor, 'direction': self.direction}
            # Post message to GCS mailbox
            self.broker.put("gcs/hall_call", call_message)
            
            # Send new hall_call registration message for visualization
            if passenger_name:
                new_hall_call_message = {
                    "timestamp": self.env.now,
                    "floor": self.floor,
                    "direction": self.direction,
                    "passenger_name": passenger_name
                }
                new_hall_call_topic = f"hall_button/floor_{self.floor}/new_hall_call"
                self.broker.put(new_hall_call_topic, new_hall_call_message)
            
            return True  # New registration successful
        else:
            # If already lit
            if passenger_name:
                print(f"{self.env.now:.2f} [HallButton] Button at floor {self.floor} ({self.direction}) already lit by someone else. {passenger_name} sees the light.")
            return False  # Already registered

    def serve(self, elevator_name=None):
        """Process when call is served (turn off light, etc.)
        
        Args:
            elevator_name: Name of the elevator that serviced this call (for visualization)
        """
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Call served at floor {self.floor} ({self.direction}). Light OFF.")
            
            # Send hall call OFF message for visualization
            hall_call_off_message = {
                "timestamp": self.env.now,
                "floor": self.floor,
                "direction": self.direction,
                "action": "OFF",
                "serviced_by": elevator_name  # Add elevator name for color-coding
            }
            hall_call_off_topic = f"hall_button/floor_{self.floor}/call_off"
            self.broker.put(hall_call_off_topic, hall_call_off_message)
            
            # Fire all events that were waiting for button OFF
            for event in self.button_off_events:
                if not event.triggered:
                    event.succeed()
            self.button_off_events = []  # Clear list