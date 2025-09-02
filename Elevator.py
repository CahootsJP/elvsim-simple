import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger # Passengerクラスをインポート

class Elevator(Entity):
    """
    本物のセレクティブコレクティブ制御を実装したエレベータ（v2.0）
    """

    class Door:
        def __init__(self, env, open_time=1.5, close_time=1.5):
            self.env = env
            self.open_time = open_time
            self.close_time = close_time

        def open(self):
            print(f"{self.env.now:.2f} [Door] Opening...")
            yield self.env.timeout(self.open_time)
            print(f"{self.env.now:.2f} [Door] Opened.")

        def close(self):
            print(f"{self.env.now:.2f} [Door] Closing...")
            yield self.env.timeout(self.close_time)
            print(f"{self.env.now:.2f} [Door] Closed.")

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
        
        self.passengers_onboard = [] # かごの中の乗客リスト
        
        self.door = self.Door(env)
        self.floor_move_time = 2.0
        
        self.new_call_event = env.event()
        
        self.env.process(self.task_listener())

    def task_listener(self):
        task_topic = f"elevator/{self.name}/task"
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            task_event = self.broker.get(task_topic)
            car_call_event = self.broker.get(car_call_topic)
            result = yield task_event | car_call_event
            if task_event in result:
                self._process_hall_call(result[task_event])
            if car_call_event in result:
                self._process_car_call(result[car_call_event])

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
        if not self.new_call_event.triggered:
            self.new_call_event.succeed()
            self.new_call_event = self.env.event()

    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor {self.current_floor}.")
        while True:
            if self.direction == "IDLE":
                yield self.env.process(self._state_idle())
            elif self.direction == "UP":
                yield self.env.process(self._state_moving_up())
            elif self.direction == "DOWN":
                yield self.env.process(self._state_moving_down())

    def _state_idle(self):
        print(f"{self.env.now:.2f} [{self.name}] State: IDLE at floor {self.current_floor}. Waiting for calls.")
        if not self._has_any_calls():
            yield self.new_call_event
        
        if self._should_service_current_floor():
             yield self.env.process(self._service_floor())

        self._decide_next_direction()

    def _state_moving_up(self):
        """上昇運転のメインロジック"""
        while self.direction == "UP":
            if self._should_service_current_floor():
                yield self.env.process(self._service_floor())

            # 上昇方向の仕事がまだあるか？
            if not self._has_calls_in_up_direction():
                break # なければループを抜けて方向転換
            
            # 1階上昇
            if self.current_floor < self.num_floors:
                yield self.env.timeout(self.floor_move_time)
                self.current_floor += 1
                print(f"{self.env.now:.2f} [{self.name}] Reached floor {self.current_floor}.")
            else:
                break # 最上階に着いたらループを抜ける

        self._decide_next_direction()

    def _state_moving_down(self):
        """下降運転のメインロジック"""
        while self.direction == "DOWN":
            if self._should_service_current_floor():
                yield self.env.process(self._service_floor())

            if not self._has_calls_in_down_direction():
                break

            if self.current_floor > 1:
                yield self.env.timeout(self.floor_move_time)
                self.current_floor -= 1
                print(f"{self.env.now:.2f} [{self.name}] Reached floor {self.current_floor}.")
            else:
                break

        self._decide_next_direction()

    def _service_floor(self):
        print(f"{self.env.now:.2f} [{self.name}] Servicing floor {self.current_floor}.")
        
        passengers_to_exit = [p for p in self.passengers_onboard if p.destination_floor == self.current_floor]
        passengers_boarding = (self.direction in ["IDLE", "UP"] and self.current_floor in self.hall_calls_up) or \
                              (self.direction in ["IDLE", "DOWN"] and self.current_floor in self.hall_calls_down)
        
        if passengers_to_exit or passengers_boarding:
            yield self.env.process(self.door.open())

            # 降車サービス
            for p in passengers_to_exit:
                print(f"{self.env.now:.2f} [{self.name}] Passenger {p.name} is exiting.")
                p.exit_event.succeed()
                self.passengers_onboard.remove(p)
            
            # 乗車サービス
            if passengers_boarding:
                print(f"{self.env.now:.2f} [{self.name}] Picking up passengers...")
                passenger = yield self.floor_queues[self.current_floor].get()
                self.passengers_onboard.append(passenger)
                passenger.on_board_event.succeed()
                
            yield self.env.process(self.door.close())

        self.car_calls.discard(self.current_floor)
        self.hall_calls_up.discard(self.current_floor)
        self.hall_calls_down.discard(self.current_floor)
        print(f"{self.env.now:.2f} [{self.name}] Service at floor {self.current_floor} complete.")

    def _has_any_calls(self):
        return bool(self.car_calls or self.hall_calls_up or self.hall_calls_down)

    def _has_calls_in_up_direction(self):
        """自分より上か、現在の階の上向き呼びがあるか"""
        return any(f > self.current_floor for f in self.car_calls | self.hall_calls_up | self.hall_calls_down) or \
               self.current_floor in self.hall_calls_up

    def _has_calls_in_down_direction(self):
        """自分より下か、現在の階の下向き呼びがあるか"""
        return any(f < self.current_floor for f in self.car_calls | self.hall_calls_up | self.hall_calls_down) or \
               self.current_floor in self.hall_calls_down
    
    def _should_service_current_floor(self):
        # かご呼びがある
        if self.current_floor in self.car_calls: return True
        # 上昇中に上向きホール呼びがある
        if self.direction == "UP" and self.current_floor in self.hall_calls_up: return True
        # 下降中に下向きホール呼びがある
        if self.direction == "DOWN" and self.current_floor in self.hall_calls_down: return True
        # IDLE状態でホール呼びがある
        if self.direction == "IDLE" and (self.current_floor in self.hall_calls_up or self.current_floor in self.hall_calls_down): return True
        
        # 方向転換のための停止
        if self.direction == "UP" and not self._has_calls_in_up_direction() and self.current_floor in self.hall_calls_down: return True
        if self.direction == "DOWN" and not self._has_calls_in_down_direction() and self.current_floor in self.hall_calls_up: return True

        return False

    def _decide_next_direction(self):
        current_direction = self.direction
        
        if current_direction == "UP":
            if self._has_calls_in_up_direction():
                return
            if self._has_calls_in_down_direction():
                self.direction = "DOWN"
                return

        elif current_direction == "DOWN":
            if self._has_calls_in_down_direction():
                return
            if self._has_calls_in_up_direction():
                self.direction = "UP"
                return

        # IDLE状態、または全ての仕事が終わった場合
        all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down
        if not all_calls:
            self.direction = "IDLE"
            return

        closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))

        if closest_call > self.current_floor: self.direction = "UP"
        elif closest_call < self.current_floor: self.direction = "DOWN"
        else:
            if self.current_floor in self.hall_calls_up: self.direction = "UP"
            elif self.current_floor in self.hall_calls_down: self.direction = "DOWN"
            else:
                other_calls = all_calls - {self.current_floor}
                if not other_calls: self.direction = "IDLE" 
                else:
                    closest_other = min(other_calls, key=lambda f: abs(f-self.current_floor))
                    self.direction = "UP" if closest_other > self.current_floor else "DOWN"

