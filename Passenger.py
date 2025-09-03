import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton

class Passenger(Entity):
    """
    乗客エンティティ（v2.1）
    【師匠修正】ログの表示順を自然な流れに変更
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, 
                 hall_buttons, floor_queues, arrival_floor: int, destination_floor: int):
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        
        self.arrival_floor = arrival_floor
        self.destination_floor = destination_floor
        
        self.on_board_event = env.event()
        self.exit_event = env.event()
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor}.")

    def run(self):
        """乗客のライフサイクル"""
        # 1. 乗り場ボタンを押す
        yield self.env.timeout(1)
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button = self.hall_buttons[self.arrival_floor][direction]
        button.press()

        # 2. 乗り場の行列に自分自身を並ばせる
        print(f"{self.env.now:.2f} [{self.name}] Now waiting in queue at floor {self.arrival_floor}.")
        current_queue = self.floor_queues[self.arrival_floor]
        yield current_queue.put(self)

        # 3. エレベータに「乗ったで！」と知らされるまで、ひたすら待つ
        yield self.on_board_event

        # 4. エレベータに乗り込み、行き先ボタンを押す
        print(f"{self.env.now:.2f} [{self.name}] Boarding elevator at floor {self.arrival_floor}.")
        
        # 【師匠修正】乗客がボタンを押した後に、ブローカーがメッセージを送信するように順番を変更
        print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
        car_call_topic = "elevator/Elevator_1/car_call"
        self.broker.put(car_call_topic, {'destination': self.destination_floor})
        
        # 5. 目的地に着いて、「降りてええで！」と知らされるまで待つ
        yield self.exit_event
        
        print(f"{self.env.now:.2f} [{self.name}] Exited at floor {self.destination_floor}. Journey complete.")
