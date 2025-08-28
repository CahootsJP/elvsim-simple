# File: Elevator.py
import simpy
from typing import Set

# 必要なクラスをインポート
# このファイルを実行するには、同じディレクトリに Entity.py, MessageBroker.py, GroupControlSystem.py が必要です。
from Entity import Entity
from MessageBroker import MessageBroker
# from elevator_interfaces import Directions # 将来的に使う

class Door:
    """ドアの開閉をシミュレートするシンプルなクラス"""
    def __init__(self, env: simpy.Environment, open_time: float = 1.5, close_time: float = 1.5):
        self.env = env
        self.open_time = open_time
        self.close_time = close_time

    def open(self):
        """ドアを開けるプロセス"""
        print(f"{self.env.now:.2f} [Door] Opening...")
        yield self.env.timeout(self.open_time)
        print(f"{self.env.now:.2f} [Door] Opened.")

    def close(self):
        """ドアを閉めるプロセス"""
        print(f"{self.env.now:.2f} [Door] Closing...")
        yield self.env.timeout(self.close_time)
        print(f"{self.env.now:.2f} [Door] Closed.")

class Elevator(Entity):
    """
    エレベータ単体を表現するクラス。
    GCSからの指示を受けて動作する。
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_move_time: float = 2.0):
        """
        Elevatorを初期化します。

        Args:
            env: SimPyのシミュレーション環境。
            name: エレベータの名前 (例: "Elevator_1")。
            broker: 通信を仲介するメッセージブローカー。
            num_floors: 建物の階数。
            floor_move_time: 1フロア移動するのにかかる時間(秒)。
        """
        super().__init__(env, name)
        self.broker = broker
        self.current_floor: int = 1
        self.num_floors: int = num_floors
        self.floor_move_time = floor_move_time
        self.door = Door(env)
        
        self.state: str = 'idle'
        self.car_calls: Set[int] = set()

    def run(self):
        """Elevatorのメインプロセス。GCSからのタスクを待ち受ける。"""
        task_topic = f"elevator/{self.entity_id}/task"
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor {self.current_floor}. Waiting for tasks on '{task_topic}'.")

        while True:
            task = yield self.broker.subscribe(task_topic)
            print(f"{self.env.now:.2f} [{self.name}] Received task: {task}")

            task_type = task.get("task_type")
            if task_type == "ASSIGN_HALL_CALL":
                pickup_floor = task.get("details", {}).get("floor")
                if pickup_floor:
                    yield self.env.process(self._handle_hall_call_trip(pickup_floor))

    def _handle_hall_call_trip(self, pickup_floor: int):
        """ホール呼び出しに応答し、乗客を目的地まで運ぶ一連のプロセス"""
        # 1. 呼び出し階へ移動
        yield self.env.process(self._move_to_floor(pickup_floor))
        
        # 2. ドアを開けて、乗客からの行先階指示(かご内呼び出し)を待つ
        yield self.env.process(self.door.open())
        
        car_call_topic = f"elevator/{self.entity_id}/car_call"
        print(f"{self.env.now:.2f} [{self.name}] Waiting for car call on '{car_call_topic}'...")
        
        boarding_timeout = 5 # 5秒以内にかご内ボタンが押されなければドアを閉める
        car_call_event = self.broker.subscribe(car_call_topic)
        result = yield car_call_event | self.env.timeout(boarding_timeout)

        destination_floor = None
        if car_call_event in result:
            car_call_task = result[car_call_event]
            destination_floor = car_call_task.get("destination")
            print(f"{self.env.now:.2f} [{self.name}] Received car call for floor {destination_floor}.")
            self.car_calls.add(destination_floor)
        else:
            print(f"{self.env.now:.2f} [{self.name}] Boarding time expired. No car call received.")

        # 3. ドアを閉める
        yield self.env.process(self.door.close())
        
        # 4. 行先階が指示されていれば、そこへ移動する
        if destination_floor:
            yield self.env.process(self._move_to_floor(destination_floor))
            
            # 目的地でドアを開閉して乗客を降ろす
            yield self.env.process(self.door.open())
            print(f"{self.env.now:.2f} [{self.name}] Passenger exiting.")
            yield self.env.timeout(1.5) # 乗客が降りる時間
            yield self.env.process(self.door.close())
            
            self.car_calls.remove(destination_floor)

        print(f"{self.env.now:.2f} [{self.name}] Service trip complete. Returning to idle.")
        self.state = 'idle'


    def _move_to_floor(self, target_floor: int):
        """指定された階まで移動するプロセス"""
        if self.current_floor == target_floor:
            return

        self.state = 'moving'
        print(f"{self.env.now:.2f} [{self.name}] Moving from {self.current_floor} to {target_floor}.")

        while self.current_floor != target_floor:
            yield self.env.timeout(self.floor_move_time)
            
            if self.current_floor < target_floor:
                self.current_floor += 1
            else:
                self.current_floor -= 1
            
            print(f"{self.env.now:.2f} [{self.name}] Reached floor {self.current_floor}.")
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}.")


if __name__ == '__main__':
    # --- このクラスの動作をGCSと連携させて確認するためのテストコード ---
    from GroupControlSystem import GroupControlSystem

    def dummy_passenger_process(env, broker, elevator_id, start_floor, dest_floor):
        # 1. ホールボタンを押す
        yield env.timeout(5)
        hall_call_message = {"floor": start_floor, "direction": "UP"}
        print(f"{env.now:.2f} [Passenger] Pressing hall button: {hall_call_message}")
        broker.publish("gcs/hall_call", hall_call_message)

        # 2. エレベータが到着してドアが開くのを待ってから、かご内ボタンを押す
        # (ここでは固定時間でシミュレート)
        yield env.timeout(10) # 5秒(登場) + 4秒(移動) + 1.5秒(ドア開) = 10.5秒後あたり
        car_call_message = {"destination": dest_floor}
        car_call_topic = f"elevator/{elevator_id}/car_call"
        print(f"{env.now:.2f} [Passenger] Pressing car button: {car_call_message}")
        broker.publish(car_call_topic, car_call_message)


    env = simpy.Environment()
    broker = MessageBroker(env)
    gcs = GroupControlSystem(env, broker)
    elevator1 = Elevator(env, "Elevator_1", broker, 10, floor_move_time=2)
    gcs.register_elevator(elevator1)
    # 3階から8階へ行きたい乗客をシミュレート
    env.process(dummy_passenger_process(env, broker, elevator1.entity_id, 3, 8))

    print("--- Elevator Integration Test Start ---")
    env.run(until=50) # シミュレーション時間を延長
    print("--- Elevator Integration Test End ---")
