import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton

class Passenger(Entity):
    """
    エレベータを利用する乗客
    """
    def __init__(self, env: simpy.Environment, name: str, 
                 broker: MessageBroker, hall_buttons: list[HallButton],
                 arrival_floor: int, destination_floor: int):
        """
        乗客を初期化する

        Args:
            env (simpy.Environment): SimPy環境
            name (str): 乗客の名前
            broker (MessageBroker): 通信に使うメッセージブローカー
            hall_buttons (list[HallButton]): ホールボタンのリスト
            arrival_floor (int): 乗客の出現階
            destination_floor (int): 乗客の目的階
        """
        super().__init__(env, name)
        self.broker = broker
        self.hall_buttons = hall_buttons
        self.arrival_floor = arrival_floor
        self.destination_floor = destination_floor
        self.env.process(self.run())

    def run(self):
        """
        乗客のライフサイクル（出現、ボタン押し、待機、乗車、移動、降車）
        """
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor}.")
        
        # 1. ホールボタンを押す
        yield self.env.timeout(1) # ボタンを押すまでの時間
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        
        # 該当するボタンを見つけて押す
        for button in self.hall_buttons:
            if button.floor == self.arrival_floor and button.direction == direction:
                button.press()
                break
        
        # 2. エレベータを待つ (このシンプル版では、乗車までの待機は省略)
        print(f"{self.env.now:.2f} [{self.name}] Now waiting for an elevator...")
        
        # 3. ドアが開いたら、かご内ボタンを押す (という想定)
        # 本来はエレベータのドアが開くイベントを待つ
        yield self.env.timeout(0) # すぐに押す
        car_call_topic = "elevator/Elevator_1/car_call" # TODO: 将来的にはGCSから割り当てられたエレベータ名を使う
        car_call_message = {"destination": self.destination_floor}
        self.broker.put(car_call_topic, car_call_message)
        print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")

        # 4. 降車まで待つ (このプロセスはここで終了。実際の移動はエレベータプロセスが担う)
