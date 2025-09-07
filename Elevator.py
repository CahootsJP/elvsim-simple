import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger
from Door import Door
import math

class Elevator(Entity):
    """
    【v19.2】SimPyのプロセス生成のルールを正しく守るように修正した運転手。
    """

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_queues, door: Door, flight_profiles: dict):
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        self.floor_queues = floor_queues
        self.door = door
        self.flight_profiles = flight_profiles

        self.current_floor = 1
        self.state = "initial_state" 
        self.advanced_position = 1

        self.car_calls = set()
        self.hall_calls_up = set()
        self.hall_calls_down = set()
        self.passengers_onboard = []
        
        self.new_call_event = self.env.event()
        self.status_topic = f"elevator/{self.name}/status"
        
        self._set_state("IDLE")
        
        self.env.process(self._hall_call_listener())
        self.env.process(self._car_call_listener())

    def _report_status(self):
        """【師匠修正】GCSへの公式報告を、正しいプロセスの手順書（ジェネレータ）にする"""
        status_message = {
            "timestamp": self.env.now,
            "physical_floor": self.current_floor,
            "advanced_position": self.advanced_position,
            "state": self.state,
            "passengers": len(self.passengers_onboard)
        }
        # returnではなくyieldを使うことで、このメソッドはジェネレータになる
        yield self.broker.put(self.status_topic, status_message)

    def _set_state(self, new_state):
        if self.state != new_state:
            print(f"{self.env.now:.2f}: Entity \"{self.name}\" ({self.__class__.__name__}) 状態遷移: {self.state} -> {new_state}")
            self.state = new_state
            self.env.process(self._report_status())

    def _signal_new_call(self):
        if not self.new_call_event.triggered:
            self.new_call_event.succeed()
            self.new_call_event = self.env.event()

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
            self._signal_new_call()

    def _car_call_listener(self):
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            car_call = yield self.broker.get(car_call_topic)
            dest_floor = car_call['destination']
            passenger_name = car_call['passenger_name']
            self.car_calls.add(dest_floor)
            print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' registered for {dest_floor}.")
            self._signal_new_call()

    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor 1.")
        self.env.process(self._report_status())

        while True:
            if self.state == "IDLE" and not self._has_any_calls():
                print(f"{self.env.now:.2f} [{self.name}] IDLE. Waiting for new call signal...")
                yield self.new_call_event

            if self._should_stop_at_current_floor():
                yield self.env.process(self._service_floor())
            
            self._decide_next_direction()
            
            if self.state != "IDLE":
                next_stop_floor = self._get_next_stop_floor()

                if next_stop_floor is None: continue
                profile = self.flight_profiles.get((self.current_floor, next_stop_floor))
                if not profile or not profile.get('timeline'): continue

                print(f"{self.env.now:.2f} [{self.name}] Moving from floor {self.current_floor} to {next_stop_floor} (total {profile['total_time']:.2f}s)...")
                
                for event in profile['timeline']:
                    yield self.env.timeout(event['time_delta'])
                    self.current_floor = event['physical_floor']
                    self.advanced_position = event['advanced_position']
                    self.env.process(self._report_status())
                
                print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")

    def _get_next_stop_floor(self):
        if self.state == "UP":
            up_calls = [f for f in (self.car_calls | self.hall_calls_up) if f > self.current_floor]
            if up_calls: return min(up_calls)
            all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down
            if all_calls: return max(all_calls)

        elif self.state == "DOWN":
            down_calls = [f for f in (self.car_calls | self.hall_calls_down) if f < self.current_floor]
            if down_calls: return max(down_calls)
            all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down
            if all_calls: return min(all_calls)
        
        return None

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

        service_process = self.env.process(self.door.service_floor_process(self.name, passengers_to_exit, boarding_queues))
        report = yield service_process
        
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
        self.env.process(self._report_status())
    
    def _should_stop_at_current_floor(self):
        if self.state == "UP":
            if self.current_floor in self.car_calls: return True
            if self.current_floor in self.hall_calls_up: return True
            all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down
            if not self._has_any_up_calls_above() and all_calls and self.current_floor == max(all_calls):
                return True

        elif self.state == "DOWN":
            if self.current_floor in self.car_calls: return True
            if self.current_floor in self.hall_calls_down: return True
            all_calls = self.car_calls | self.hall_calls_up | self.hall_calls_down
            if not self._has_any_down_calls_below() and all_calls and self.current_floor == min(all_calls):
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

