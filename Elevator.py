import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger # Passengerクラスをインポート

class Elevator(Entity):
    """
    受付係を「ホール呼び専門」と「かご内呼び専門」の2人に増員し、
    呼び出しの取りこぼしをなくしたバージョン（v7.0）
    【v7.1】乗客の乗降時間を考慮し、ログの自然さを向上
    """

    class Door:
        def __init__(self, env, elevator_name, open_time=1.5, close_time=1.5):
            self.env = env
            self.name = elevator_name
            self.open_time = open_time
            self.close_time = close_time

        def open(self):
            print(f"{self.env.now:.2f} [{self.name}] Door Opening...")
            yield self.env.timeout(self.open_time)
            print(f"{self.env.now:.2f} [{self.name}] Door Opened.")

        def close(self):
            print(f"{self.env.now:.2f} [{self.name}] Door Closing...")
            yield self.env.timeout(self.close_time)
            print(f"{self.env.now:.2f} [{self.name}] Door Closed.")

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_queues):
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        self.floor_queues = floor_queues
        
        self.current_floor = 1
        self.direction = "IDLE"
        
        self.car_calls = set()
        self.hall_calls_up = set()
        self.hall_calls_down = set()
        
        self.passengers_onboard = []
        
        self.door = self.Door(env, self.name) 
        self.floor_move_time = 2.0
        self.passenger_move_time = 1.0 # 【師匠追加】乗客が乗り降りするための時間
        
        self.new_call_event = env.event()
        
        # 受付係を2人（2プロセス）に増員！
        self.env.process(self.hall_call_listener())
        self.env.process(self.car_call_listener())

    def hall_call_listener(self):
        """ホール呼び（GCSからのタスク）専門の受付係"""
        task_topic = f"elevator/{self.name}/task"
        while True:
            message = yield self.broker.get(task_topic)
            self._process_hall_call(message)

    def car_call_listener(self):
        """かご内呼び専門の受付係"""
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            message = yield self.broker.get(car_call_topic)
            self._process_car_call(message)

    def _process_hall_call(self, task):
        details = task['details']
        floor, direction = details['floor'], details['direction']
        if direction == "UP": self.hall_calls_up.add(floor)
        else: self.hall_calls_down.add(floor)
        print(f"{self.env.now:.2f} [{self.name}] Hall call registered: Floor {floor} {direction}.")
        self._signal_new_call()

    def _process_car_call(self, car_call):
        dest_floor = car_call['destination']
        self.car_calls.add(dest_floor)
        print(f"{self.env.now:.2f} [{self.name}] Car call registered for {dest_floor}.")
        self._signal_new_call()

    def _signal_new_call(self):
        if self.new_call_event and not self.new_call_event.triggered:
            self.new_call_event.succeed()
            self.new_call_event = self.env.event()

    def run(self):
        """
        エレベータのメイン制御ループ。
        「到着」してから「判断」する、現実的なサイクルを実装。
        """
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor {self.current_floor}.")
        while True:
            # --- 待機状態(IDLE)の処理 ---
            if self.direction == "IDLE":
                print(f"{self.env.now:.2f} [{self.name}] State: IDLE at floor {self.current_floor}.")
                if not self._get_all_calls():
                    yield self.new_call_event # 新しい呼び出しを待つ
                self._decide_next_direction() # 最初のミッションを決定
                if self.direction == "IDLE": # 呼びが現在階のみでサービス完了した場合
                    continue

            # --- 到着階での判断と行動 ---
            # 1. 現在階で停止すべきか判断
            if self._should_stop_at_current_floor():
                yield self.env.process(self._service_floor())
            
            # 2. サービス後、次の行動（進行方向）を再判断
            self._decide_next_direction()
            
            # --- 次の階への移動 ---
            if self.direction == "IDLE":
                # 全ての仕事が終わった場合
                continue

            if self.direction == "UP":
                yield self.env.timeout(self.floor_move_time)
                self.current_floor += 1
                print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            elif self.direction == "DOWN":
                yield self.env.timeout(self.floor_move_time)
                self.current_floor -= 1
                print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")

    def _should_stop_at_current_floor(self):
        """現在階で停止すべきかを、全てのルールに基づき判断する"""
        # ルール1: かご内に現在階の呼びがあれば必ず停止
        if self.current_floor in self.car_calls:
            return True

        # ルール2: 進行方向と一致するホール呼びがあれば停止
        if self.direction == "UP" and self.current_floor in self.hall_calls_up:
            return True
        if self.direction == "DOWN" and self.current_floor in self.hall_calls_down:
            return True

        # ルール3: 方向転換点での停止
        all_calls = self._get_all_calls()
        if not all_calls: return False

        if self.direction == "UP":
            has_further_up_calls = any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
            if not has_further_up_calls and self.current_floor == max(all_calls):
                return True # 上昇ミッションの終点、かつ全呼びの最高到達点なら停止
        
        if self.direction == "DOWN":
            has_further_down_calls = any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
            if not has_further_down_calls and self.current_floor == min(all_calls):
                return True # 下降ミッションの終点、かつ全呼びの最低到達点なら停止

        return False
        
    def _decide_next_direction(self):
        """次のサイクルの進行方向を決定する"""
        old_direction = self.direction
        
        if old_direction == "UP":
            has_further_up_calls = any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
            if has_further_up_calls:
                self.direction = "UP"
                return 
            
            all_calls = self._get_all_calls()
            if not all_calls:
                self.direction = "IDLE"
            elif self.current_floor < max(all_calls):
                self.direction = "UP" # 最遠点まで空走を継続
            else:
                self.direction = "DOWN" # 最遠点に到達したので反転

        elif old_direction == "DOWN":
            has_further_down_calls = any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
            if has_further_down_calls:
                self.direction = "DOWN"
                return
            
            all_calls = self._get_all_calls()
            if not all_calls:
                self.direction = "IDLE"
            elif self.current_floor > min(all_calls):
                self.direction = "DOWN" # 最遠点まで空走を継続
            else:
                self.direction = "UP" # 最遠点に到達したので反転
        
        elif old_direction == "IDLE":
            all_calls = self._get_all_calls()
            if not all_calls: return

            closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))
            if closest_call > self.current_floor: self.direction = "UP"
            elif closest_call < self.current_floor: self.direction = "DOWN"
            else: # 現在階の呼び出し
                self.direction = "UP" if self.current_floor in self.hall_calls_up else "DOWN"

        if old_direction != self.direction:
            print(f"{self.env.now:.2f} [{self.name}] Direction changed from {old_direction} to {self.direction}.")

    def _service_floor(self):
        """現在階で乗客の乗降サービスを行う"""
        print(f"{self.env.now:.2f} [{self.name}] Servicing floor {self.current_floor}.")
        
        can_board_up = self.direction == "UP" and self.current_floor in self.hall_calls_up
        can_board_down = self.direction == "DOWN" and self.current_floor in self.hall_calls_down
        if self.direction == "IDLE":
            can_board_up = self.current_floor in self.hall_calls_up
            can_board_down = self.current_floor in self.hall_calls_down and not can_board_up

        is_up_turnaround = self.direction == "UP" and not any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
        is_down_turnaround = self.direction == "DOWN" and not any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
        if is_up_turnaround and self.current_floor in self.hall_calls_down: can_board_down = True
        if is_down_turnaround and self.current_floor in self.hall_calls_up: can_board_up = True
            
        passengers_to_exit = [p for p in self.passengers_onboard if p.destination_floor == self.current_floor]
        
        if passengers_to_exit or can_board_up or can_board_down:
            yield self.env.process(self.door.open())
            
            for p in passengers_to_exit:
                p.exit_event.succeed()
                self.passengers_onboard.remove(p)
                print(f"{self.env.now:.2f} [{self.name}] Passenger {p.name} exiting.")
            
            if (can_board_up or can_board_down) and self.floor_queues[self.current_floor].items:
                passenger = yield self.floor_queues[self.current_floor].get()
                self.passengers_onboard.append(passenger)
                passenger.on_board_event.succeed()
                print(f"{self.env.now:.2f} [{self.name}] Passenger {passenger.name} boarding.")

            # 【師匠修正】乗降が完了してからドアが閉まるまでの時間を確保
            if passengers_to_exit or ((can_board_up or can_board_down) and self.floor_queues[self.current_floor].items):
                 yield self.env.timeout(self.passenger_move_time)

            yield self.env.process(self.door.close())

        self.car_calls.discard(self.current_floor)
        if can_board_up: self.hall_calls_up.discard(self.current_floor)
        if can_board_down: self.hall_calls_down.discard(self.current_floor)
        print(f"{self.env.now:.2f} [{self.name}] Service at floor {self.current_floor} complete.")

    def _get_all_calls(self):
        return self.car_calls | self.hall_calls_up | self.hall_calls_down

