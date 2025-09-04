import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger
from Door import Door

class Elevator(Entity):
    """
    【v13.5】セルフサービス方式に対応したエレベータ（運転手）
    方向転換プロトコルにおける停止判断のバグを完全修正。
    """

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_queues, door: Door):
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        self.floor_queues = floor_queues
        self.door = door

        self.current_floor = 1
        self.state = "initial_state" 
        self._set_state("IDLE")

        self.car_calls = set()
        self.hall_calls_up = set()
        self.hall_calls_down = set()
        
        self.passengers_onboard = []
        
        self.env.process(self._hall_call_listener())
        self.env.process(self._car_call_listener())

    def _set_state(self, new_state):
        if self.state != new_state:
            print(f"{self.env.now:.2f}: Entity \"{self.name}\" ({self.__class__.__name__}) 状態遷移: {self.state} -> {new_state}")
            self.state = new_state

    def _hall_call_listener(self):
        task_topic = f"elevator/{self.name}/task"
        while True:
            task = yield self.broker.get(task_topic)
            details = task['details']
            floor, direction = details['floor'], details['direction']
            if direction == "UP":
                self.hall_calls_up.add(floor)
            else:
                self.hall_calls_down.add(floor)
            print(f"{self.env.now:.2f} [{self.name}] Hall call registered: Floor {floor} {direction}.")

    def _car_call_listener(self):
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            car_call = yield self.broker.get(car_call_topic)
            dest_floor = car_call['destination']
            passenger_name = car_call['passenger_name']
            self.car_calls.add(dest_floor)
            print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' registered for {dest_floor}.")

    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor 1.")
        while True:
            if self._should_stop_at_current_floor():
                yield self.env.process(self._service_floor())
            
            self._decide_next_direction()
            
            if self.state == "UP":
                yield self.env.timeout(2.0)
                self.current_floor += 1
                print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            elif self.state == "DOWN":
                yield self.env.timeout(2.0)
                self.current_floor -= 1
                print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            else: # IDLE
                if not self._has_any_calls():
                    yield self.env.timeout(1)

    def _service_floor(self):
        print(f"{self.env.now:.2f} [{self.name}] Servicing floor {self.current_floor}.")
        passengers_to_exit = sorted([p for p in self.passengers_onboard if p.destination_floor == self.current_floor], key=lambda p: p.entity_id, reverse=True)

        boarding_queues = []
        if self.state in ["IDLE", "UP"] and self.current_floor in self.hall_calls_up:
            boarding_queues.append(self.floor_queues[self.current_floor]["UP"])
        if self.state in ["IDLE", "DOWN"] and self.current_floor in self.hall_calls_down:
            boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])
        if self.state == "UP" and self.current_floor in self.hall_calls_down and not self._has_any_up_calls_above():
             boarding_queues.append(self.floor_queues[self.current_floor]["DOWN"])
        if self.state == "DOWN" and self.current_floor in self.hall_calls_up and not self._has_any_down_calls_below():
            boarding_queues.append(self.floor_queues[self.current_floor]["UP"])

        service_done_event = self.env.event()
        task_message = {
            'task_type': 'SERVICE_FLOOR',
            'elevator_name': self.name,
            'passengers_to_exit': passengers_to_exit,
            'boarding_queues': boarding_queues,
            'callback_event': service_done_event
        }
        yield self.broker.put(self.door.command_topic, task_message)
        
        report = yield service_done_event
        
        for p in passengers_to_exit:
            self.passengers_onboard.remove(p)
            
        boarded_passengers = report.get("boarded", [])
        for p in boarded_passengers:
            self.passengers_onboard.append(p)

        self.car_calls.discard(self.current_floor)
        if any(q == self.floor_queues[self.current_floor]["UP"] for q in boarding_queues):
            self.hall_calls_up.discard(self.current_floor)
        if any(q == self.floor_queues[self.current_floor]["DOWN"] for q in boarding_queues):
            self.hall_calls_down.discard(self.current_floor)
        
        print(f"{self.env.now:.2f} [{self.name}] Service at floor {self.current_floor} complete.")
    
    def _should_stop_at_current_floor(self):
        """【師匠最終修正】現在の階で停止すべきかどうかを判断する"""
        if self.state == "UP":
            # 理由1: 上昇中に、この階のかご呼びがある
            if self.current_floor in self.car_calls: return True
            # 理由2: 上昇中に、この階の上向きホール呼びがある
            if self.current_floor in self.hall_calls_up: return True
            # 理由3: 上昇方向の仕事がもう上でなく、この階が最遠の呼び出し地点（たとえ下向きでも）
            if not self._has_any_up_calls_above() and self.current_floor == max(self.car_calls | self.hall_calls_up | self.hall_calls_down):
                return True

        elif self.state == "DOWN":
            # 理由1: 下降中に、この階のかご呼びがある
            if self.current_floor in self.car_calls: return True
            # 理由2: 下降中に、この階の下向きホール呼びがある
            if self.current_floor in self.hall_calls_down: return True
            # 理由3: 下降方向の仕事がもう下になく、この階が最遠の呼び出し地点（たとえ上向きでも）
            if not self._has_any_down_calls_below() and self.current_floor == min(self.car_calls | self.hall_calls_up | self.hall_calls_down):
                return True

        elif self.state == "IDLE":
            return self._has_any_calls_at_current_floor()

        return False

    def _decide_next_direction(self):
        current_direction = self.state
        all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down

        if not all_calls:
            self._set_state("IDLE")
            return

        if current_direction == "UP":
            if self._has_any_up_calls_above():
                return
            
            farthest_call = max(all_calls)
            if self.current_floor < farthest_call:
                return
            else:
                self._set_state("DOWN")

        elif current_direction == "DOWN":
            if self._has_any_down_calls_below():
                return
            
            farthest_call = min(all_calls)
            if self.current_floor > farthest_call:
                return
            else:
                self._set_state("UP")

        elif current_direction == "IDLE":
            if not self._has_any_calls(): return

            closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))

            if closest_call > self.current_floor:
                self._set_state("UP")
            elif closest_call < self.current_floor:
                self._set_state("DOWN")
            else:
                if self.current_floor in self.hall_calls_up:
                    self._set_state("UP")
                elif self.current_floor in self.hall_calls_down:
                    self._set_state("DOWN")

    def _has_any_calls(self):
        return bool(self.car_calls or self.hall_calls_up or self.hall_calls_down)

    def _has_any_calls_at_current_floor(self):
        return (self.current_floor in self.car_calls or
                self.current_floor in self.hall_calls_up or
                self.current_floor in self.hall_calls_down)

    def _has_any_up_calls_above(self):
        return any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)

    def _has_any_down_calls_below(self):
        return any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)

