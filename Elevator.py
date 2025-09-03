import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger # Passengerクラスをインポート

class Elevator(Entity):
    """
    【v9.0】降車をLIFO（後入れ先出し）に変更し、より現実的な動きに
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
        self.passenger_move_time = 1.0
        
        self.new_call_event = env.event()
        
        self.env.process(self.hall_call_listener())
        self.env.process(self.car_call_listener())

    def hall_call_listener(self):
        task_topic = f"elevator/{self.name}/task"
        while True:
            message = yield self.broker.get(task_topic)
            self._process_hall_call(message)

    def car_call_listener(self):
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
        passenger_name = car_call['passenger_name']
        self.car_calls.add(dest_floor)
        print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' registered for {dest_floor}.")
        self._signal_new_call()

    def _signal_new_call(self):
        if self.new_call_event and not self.new_call_event.triggered:
            self.new_call_event.succeed()
            self.new_call_event = self.env.event()

    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor {self.current_floor}.")
        while True:
            if self.direction == "IDLE":
                print(f"{self.env.now:.2f} [{self.name}] State: IDLE at floor {self.current_floor}.")
                if not self._get_all_calls():
                    yield self.new_call_event
                self._decide_next_direction()
                if self.direction == "IDLE":
                    continue

            if self._should_stop_at_current_floor():
                yield self.env.process(self._service_floor())
            
            self._decide_next_direction()
            
            if self.direction == "IDLE":
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
        if self.current_floor in self.car_calls: return True
        if self.direction == "UP" and self.current_floor in self.hall_calls_up: return True
        if self.direction == "DOWN" and self.current_floor in self.hall_calls_down: return True
        
        all_calls = self._get_all_calls()
        if not all_calls: return False

        if self.direction == "UP":
            has_further_up_calls = any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
            if not has_further_up_calls and self.current_floor == max(all_calls): return True
        
        if self.direction == "DOWN":
            has_further_down_calls = any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
            if not has_further_down_calls and self.current_floor == min(all_calls): return True

        return False
        
    def _decide_next_direction(self):
        old_direction = self.direction
        
        if old_direction == "UP":
            has_further_up_calls = any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
            if has_further_up_calls:
                self.direction = "UP"; return 
            
            all_calls = self._get_all_calls()
            if not all_calls: self.direction = "IDLE"
            elif self.current_floor < max(all_calls): self.direction = "UP"
            else: self.direction = "DOWN"

        elif old_direction == "DOWN":
            has_further_down_calls = any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
            if has_further_down_calls:
                self.direction = "DOWN"; return
            
            all_calls = self._get_all_calls()
            if not all_calls: self.direction = "IDLE"
            elif self.current_floor > min(all_calls): self.direction = "DOWN"
            else: self.direction = "UP"
        
        elif old_direction == "IDLE":
            all_calls = self._get_all_calls()
            if not all_calls: return

            closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))
            if closest_call > self.current_floor: self.direction = "UP"
            elif closest_call < self.current_floor: self.direction = "DOWN"
            else: self.direction = "UP" if self.current_floor in self.hall_calls_up else "DOWN"

        if old_direction != self.direction:
            print(f"{self.env.now:.2f} [{self.name}] Direction changed from {old_direction} to {self.direction}.")

    def _service_floor(self):
        print(f"{self.env.now:.2f} [{self.name}] Servicing floor {self.current_floor}.")
        
        passengers_to_exit = [p for p in self.passengers_onboard if p.destination_floor == self.current_floor]
        
        is_up_turnaround = self.direction == "UP" and not any(f > self.current_floor for f in self.car_calls | self.hall_calls_up)
        is_down_turnaround = self.direction == "DOWN" and not any(f < self.current_floor for f in self.car_calls | self.hall_calls_down)
        
        can_board_up = (self.direction == "UP" or self.direction == "IDLE" or is_down_turnaround) and self.current_floor in self.hall_calls_up
        can_board_down = (self.direction == "DOWN" or (self.direction == "IDLE" and not can_board_up) or is_up_turnaround) and self.current_floor in self.hall_calls_down
            
        any_passengers_moved = False
        
        if passengers_to_exit or can_board_up or can_board_down:
            yield self.env.process(self.door.open())
            
            if passengers_to_exit:
                any_passengers_moved = True
                # 【鴨川師匠 LIFO修正】現実の降車に近づけるため、後から乗った人（リストの後ろの方）から先に降りるようにする
                # print(f"{self.env.now:.2f} [{self.name}] Passengers exiting (LIFO): {[p.name for p in reversed(passengers_to_exit)]}")
                for p in reversed(passengers_to_exit): # リストを逆順に処理することでLIFOを実現
                    p.exit_event.succeed()
                    self.passengers_onboard.remove(p) # remove()は値で探すので順序は関係ない
                    print(f"{self.env.now:.2f} [{self.name}] Passenger {p.name} exiting.")
            
            boarding_queues = []
            if can_board_up: boarding_queues.append(self.floor_queues[self.current_floor]['UP'])
            if can_board_down: boarding_queues.append(self.floor_queues[self.current_floor]['DOWN'])

            for queue in boarding_queues:
                while queue.items:
                    any_passengers_moved = True
                    passenger = yield queue.get()
                    self.passengers_onboard.append(passenger)
                    passenger.on_board_event.succeed()
                    print(f"{self.env.now:.2f} [{self.name}] Passenger {passenger.name} boarding.")

            if any_passengers_moved:
                 yield self.env.timeout(self.passenger_move_time)

            yield self.env.process(self.door.close())

        self.car_calls.discard(self.current_floor)
        if can_board_up: self.hall_calls_up.discard(self.current_floor)
        if can_board_down: self.hall_calls_down.discard(self.current_floor)
        print(f"{self.env.now:.2f} [{self.name}] Service at floor {self.current_floor} complete.")

    def _get_all_calls(self):
        return self.car_calls | self.hall_calls_up | self.hall_calls_down

