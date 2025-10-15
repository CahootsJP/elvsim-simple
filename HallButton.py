import simpy
from MessageBroker import MessageBroker

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

    def is_lit(self):
        """Check if the button is lit"""
        return self.is_pressed
    
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

    def serve(self):
        """Process when call is served (turn off light, etc.)"""
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Call served at floor {self.floor} ({self.direction}). Light OFF.")