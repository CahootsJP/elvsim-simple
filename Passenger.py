import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from HallButton import HallButton

class Passenger(Entity):
    """
    【v13.0】セルフサービス方式で、自分の意志で乗り降りする乗客
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

        # 【師匠改造】店長（Door）からの許可を待つための専用の待合室
        # Storeを使うことで、許可と同時に「完了報告用のイベント」を受け取れる
        self.board_permission_event = simpy.Store(env, capacity=1)
        self.exit_permission_event = simpy.Store(env, capacity=1)
        
        print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.arrival_floor}. Wants to go to {self.destination_floor} (Move time: {self.move_speed:.1f}s).")

    def run(self):
        """【師匠大改造】乗客の自立したライフサイクル"""
        # 1. 乗り場ボタンを押す（重複チェック機能付き）
        yield self.env.timeout(1)
        direction = "UP" if self.destination_floor > self.arrival_floor else "DOWN"
        button = self.hall_buttons[self.arrival_floor][direction]
        
        # 【新規】ボタンの点灯状態をチェックしてから押下
        if button.is_lit():
            print(f"{self.env.now:.2f} [{self.name}] Hall button at floor {self.arrival_floor} ({direction}) already lit. No need to press.")
        else:
            button.press(passenger_name=self.name)

        # 2. 正しい方向の行列に並ぶ
        current_queue = self.floor_queues[self.arrival_floor][direction]
        print(f"{self.env.now:.2f} [{self.name}] Now waiting in '{direction}' queue at floor {self.arrival_floor}.")
        yield current_queue.put(self)

        # 3. 店長（Door）から「乗ってええで」と許可が出るのを待つ
        completion_event = yield self.board_permission_event.get()

        # 4. 自分の足で、自分のペースでエレベータに乗り込む
        print(f"{self.env.now:.2f} [{self.name}] Boarding elevator.")
        yield self.env.timeout(self.move_speed)

        # 5. エレベータに乗り込み、行き先ボタンを押す
        print(f"{self.env.now:.2f} [{self.name}] Pressed car button for floor {self.destination_floor}.")
        car_call_topic = "elevator/Elevator_1/car_call"
        self.broker.put(car_call_topic, {'destination': self.destination_floor, 'passenger_name': self.name})

        # 6. 店長に「乗り終わったで」と報告する
        completion_event.succeed()

        # 7. 目的地に着いて、店長から「降りてええで」と許可が出るのを待つ
        completion_event = yield self.exit_permission_event.get()

        # 8. 自分の足で、自分のペースでエレベータから降りる
        print(f"{self.env.now:.2f} [{self.name}] Exiting elevator.")
        yield self.env.timeout(self.move_speed)
        
        # 9. 店長に「降り終わったで」と報告する
        completion_event.succeed()
        
        print(f"{self.env.now:.2f} [{self.name}] Journey complete.")

