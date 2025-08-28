# File: Passenger.py
import simpy
from typing import List

# 必要なクラスをインポート
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton
from Elevator import Elevator # Elevatorクラスもテストで使うためインポート
from GroupControlSystem import GroupControlSystem # GCSもテストで使うためインポート

class Passenger(Entity):
    """
    乗客を表現するクラス。
    ホールボタンを押し、エレベータを待って乗車し、目的地で降車する。
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker,
                 arrival_floor: int, destination_floor: int, 
                 hall_buttons: List[HallButton], floor_queues: List[simpy.Store]):
        """
        Passengerを初期化します。

        Args:
            env: SimPyのシミュレーション環境。
            name: 乗客の名前。
            broker: 通信を仲介するメッセージブローカー。
            arrival_floor: 乗客が登場する階。
            destination_floor: 乗客の目的階。
            hall_buttons: 建物に設置されている全てのホールボタンのリスト。
            floor_queues: 各階の乗客待ち行列(Store)のリスト。
        """
        super().__init__(env, name)
        self.broker = broker
        self.arrival_floor = arrival_floor
        self.destination_floor = destination_floor
        self.hall_buttons = hall_buttons
        self.floor_queues = floor_queues
        self.arrived_event = self.env.event() # 目的地到着を知らせるためのイベント

    def run(self):
        """Passengerのメインプロセス。登場から降車までのライフサイクル。"""
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor}.")

        # 1. 押すべきボタンを探して押す
        target_direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button_to_press = next((b for b in self.hall_buttons if b.floor == self.arrival_floor and b.direction == target_direction), None)
        
        if button_to_press:
            yield self.env.timeout(1) # ボタンを探して押すまでに1秒
            button_to_press.press()
        else:
            print(f"{self.env.now:.2f} [{self.name}] ERROR: No button found.")
            return

        # 2. 乗り場の列に入って、エレベータに拾われるのを待つ
        print(f"{self.env.now:.2f} [{self.name}] Waiting in queue at floor {self.arrival_floor}.")
        yield self.floor_queues[self.arrival_floor - 1].put(self)
        print(f"{self.env.now:.2f} [{self.name}] Boarding elevator...")

        # 3. エレベータに乗ったら、行先階ボタンを押す
        # (エレベータのIDを知る必要があるが、ここではGCSが1台しか割り当てないので固定打ち)
        car_call_message = {"destination": self.destination_floor}
        # 実際にはGCSから割り当てられたエレベータIDを使う
        elevator_id_assigned = 1 # 仮にID:1のエレベータ
        car_call_topic = f"elevator/{elevator_id_assigned}/car_call"
        self.broker.publish(car_call_topic, car_call_message)
        print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")

        # 4. 目的地に到着するまで待つ (エレベータがarrived_eventをsucceedさせる)
        yield self.arrived_event
        
        print(f"{self.env.now:.2f} [{self.name}] Exited at floor {self.destination_floor}. Journey complete.")


if __name__ == '__main__':
    # --- 全てのコンポーネントを連携させる最終統合テスト ---

    # Elevatorクラスを、乗客の乗り降りに対応できるように修正
    class ElevatorWithBoarding(Elevator):
        def __init__(self, env, name, broker, num_floors, floor_queues, **kwargs):
            super().__init__(env, name, broker, num_floors, **kwargs)
            self.floor_queues = floor_queues
            self.passenger_onboard = None

        def _handle_hall_call_trip(self, pickup_floor: int):
            # 1. 呼び出し階へ移動
            yield self.env.process(self._move_to_floor(pickup_floor))
            
            # 2. ドアを開けて、乗客を乗せる
            yield self.env.process(self.door.open())
            
            # 乗り場の列から乗客を一人取得する
            queue = self.floor_queues[pickup_floor - 1]
            self.passenger_onboard = yield queue.get()
            print(f"{self.env.now:.2f} [{self.name}] Picked up '{self.passenger_onboard.name}'.")
            
            # 3. 乗客からの行先階指示(かご内呼び出し)を待つ
            car_call_topic = f"elevator/{self.entity_id}/car_call"
            car_call_event = self.broker.subscribe(car_call_topic)
            result = yield car_call_event | self.env.timeout(5)

            destination_floor = None
            if car_call_event in result:
                destination_floor = result[car_call_event].get("destination")
                self.car_calls.add(destination_floor)
            
            # 4. ドアを閉める
            yield self.env.process(self.door.close())
            
            # 5. 行先階へ移動し、乗客を降ろす
            if destination_floor:
                yield self.env.process(self._move_to_floor(destination_floor))
                yield self.env.process(self.door.open())
                
                # 乗客に到着を知らせる
                if self.passenger_onboard:
                    self.passenger_onboard.arrived_event.succeed()
                    self.passenger_onboard = None
                
                yield self.env.timeout(1.5) # 乗客が降りる時間
                yield self.env.process(self.door.close())
                self.car_calls.remove(destination_floor)

            self.state = 'idle'
            print(f"{self.env.now:.2f} [{self.name}] Service trip complete. Returning to idle.")

    # --- セットアップ ---
    env = simpy.Environment()
    broker = MessageBroker(env)
    
    num_floors = 10
    hall_buttons = [HallButton(env, broker, f, d) for f in range(1, num_floors + 1) for d in ("UP", "DOWN") if (f > 1 and d == "DOWN") or (f < num_floors and d == "UP")]
    floor_queues = [simpy.Store(env) for _ in range(num_floors)]

    gcs = GroupControlSystem(env, broker)
    elevator1 = ElevatorWithBoarding(env, "Elevator_1", broker, num_floors, floor_queues, floor_move_time=2)
    gcs.register_elevator(elevator1)

    # 本物の乗客を登場させる
    passenger1 = Passenger(env, "Taro", broker, 3, 8, hall_buttons, floor_queues)

    # --- 実行 ---
    print("--- Final Integration Test Start ---")
    env.run(until=50)
    print("--- Final Integration Test End ---")
