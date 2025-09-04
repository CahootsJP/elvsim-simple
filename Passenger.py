import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton

class Passenger(Entity):
    """
    【v3.0】乗客が自身の乗降時間を持つように修正
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, 
                 hall_buttons, floor_queues, arrival_floor: int, destination_floor: int,
                 move_speed: float = 1.0): # 【師匠追加】
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        
        self.arrival_floor = arrival_floor
        self.destination_floor = destination_floor
        self.move_speed = move_speed # 【師匠追加】
        
        self.on_board_event = env.event()
        self.exit_event = env.event()
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor} (Move time: {self.move_speed}s).")

    def run(self):
        """乗客のライフサイクル"""
        yield self.env.timeout(1)
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button = self.hall_buttons[self.arrival_floor][direction]
        button.press()

        print(f"{self.env.now:.2f} [{self.name}] Now waiting in '{direction}' queue at floor {self.arrival_floor}.")
        current_queue = self.floor_queues[self.arrival_floor][direction]
        yield current_queue.put(self)

        yield self.on_board_event

        print(f"{self.env.now:.2f} [{self.name}] Boarding elevator.")
        
        print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
        car_call_topic = "elevator/Elevator_1/car_call"
        self.broker.put(car_call_topic, {'destination': self.destination_floor, 'passenger_name': self.name})
        
        yield self.exit_event
        
        print(f"{self.env.now:.2f} [{self.name}] Exited at floor {self.destination_floor}. Journey complete.")

