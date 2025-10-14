import simpy
from simpy.events import Interrupt
from Entity import Entity
from MessageBroker import MessageBroker
from Passenger import Passenger
from Door import Door
import math

class Elevator(Entity):
    """
    【v20.0】走行中の割り込みに対応できる、エースパイロットになった運転手
    """

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int, floor_queues, door: Door, flight_profiles: dict, physics_engine=None):
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        self.floor_queues = floor_queues
        self.door = door
        self.flight_profiles = flight_profiles
        self.physics_engine = physics_engine  # PhysicsEngineへのアクセス

        self.current_floor = 1
        self.state = "initial_state" 
        self.advanced_position = 1
        self.current_destination = None # 現在の最終目的地
        self.last_advanced_position = None # 前回のadvanced_position
        self.current_move_process = None # 【修正】現在の移動プロセスを追跡
        
        # テーブル方式の有効化フラグ（デフォルト：実用タイムライン方式）
        self.use_table_method = True

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
        status_message = {
            "timestamp": self.env.now,
            "physical_floor": self.current_floor,
            "advanced_position": self.advanced_position,
            "state": self.state,
            "passengers": len(self.passengers_onboard)
        }
        yield self.broker.put(self.status_topic, status_message)

    def _broadcast_hall_calls_status(self):
        """hall_calls状態を送信する"""
        hall_calls_message = {
            "timestamp": self.env.now,
            "elevator_name": self.name,
            "hall_calls_up": list(self.hall_calls_up),
            "hall_calls_down": list(self.hall_calls_down),
            "current_floor": self.current_floor
        }
        hall_calls_topic = f"elevator/{self.name}/hall_calls"
        yield self.broker.put(hall_calls_topic, hall_calls_message)

    def _set_state(self, new_state):
        if self.state != new_state:
            print(f"{self.env.now:.2f}: Entity \"{self.name}\" ({self.__class__.__name__}) 状態遷移: {self.state} -> {new_state}")
            self.state = new_state
            self.env.process(self._report_status())

    def _should_interrupt(self, new_floor, new_direction):
        """現在の走行を中断すべきか判断する"""
        if self.state == "IDLE" or self.current_destination is None:
            return False # 止まってるなら中断の必要なし

        if self.state == "UP" and new_direction == "UP":
            # 上昇中に、今の位置より上で、目的地より手前の呼び出しが入ったか？
            return self.current_floor < new_floor < self.current_destination
        
        if self.state == "DOWN" and new_direction == "DOWN":
            # 下降中に、今の位置より下で、目的地より手前の呼び出しが入ったか？
            return self.current_floor > new_floor > self.current_destination

        return False

    def _hall_call_listener(self):
        task_topic = f"elevator/{self.name}/task"
        while True:
            task = yield self.broker.get(task_topic)
            details = task['details']
            floor, direction = details['floor'], details['direction']
            
            if direction == "UP": self.hall_calls_up.add(floor)
            else: self.hall_calls_down.add(floor)
            print(f"{self.env.now:.2f} [{self.name}] Hall call registered: Floor {floor} {direction}.")
            
            # hall_calls状態を送信
            self.env.process(self._broadcast_hall_calls_status())
            
            # 緊急ボタンを押すか判断
            if self._should_interrupt(floor, direction):
                print(f"{self.env.now:.2f} [{self.name}] New valid call on the way! INTERRUPTING.")
                self.process.interrupt()
            else:
                 if not self.new_call_event.triggered:
                    self.new_call_event.succeed()
                    self.new_call_event = self.env.event()

    def _car_call_listener(self):
        car_call_topic = f"elevator/{self.name}/car_call"
        while True:
            car_call = yield self.broker.get(car_call_topic)
            dest_floor = car_call['destination']
            passenger_name = car_call['passenger_name']
            self.car_calls.add(dest_floor)
            print(f"{self.env.now:.2f} [{self.name}] Car call from '{passenger_name}' registered for {dest_floor}.")
            
            # TODO: かご呼びでも割り込みを実装する
            if not self.new_call_event.triggered:
                self.new_call_event.succeed()
                self.new_call_event = self.env.event()


    def run(self):
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor 1.")
        self.env.process(self._report_status())

        while True:
            if self._should_stop_at_current_floor():
                yield self.env.process(self._service_floor())
            
            self._decide_next_direction()
            
            if self.state == "IDLE":
                self.current_destination = None
                if not self._has_any_calls():
                    print(f"{self.env.now:.2f} [{self.name}] IDLE. Waiting for new call signal...")
                    yield self.new_call_event
                continue # ループの先頭に戻って再判断

            # ここからが新しい運転ロジック
            self.current_destination = self._get_next_stop_floor()

            if self.current_destination is None:
                self._set_state("IDLE")
                continue

            # このtryブロックが、中断可能なフライトプラン
            try:
                # 【修正】現在の移動プロセスを追跡
                self.current_move_process = self.env.process(self._move_process(self.current_destination))
                yield self.current_move_process
            except Interrupt:
                # 無線係から緊急連絡が来た！
                print(f"{self.env.now:.2f} [{self.name}] Movement interrupted by new call. Re-evaluating next stop.")
                # 【修正】古い移動プロセスをキャンセル
                if self.current_move_process and self.current_move_process.is_alive:
                    self.current_move_process.interrupt()
                self.current_move_process = None
                # ループの先頭に戻れば、自動的に新しい目的地が再計算される
                continue

    def _move_process(self, destination_floor):
        """cruise_table/brake_tableを使った移動プロセス"""
        if self.use_table_method and self.physics_engine:
            return self._move_process_with_tables(destination_floor)
        else:
            return self._move_process_with_timeline(destination_floor)
    
    def _move_process_with_tables(self, destination_floor):
        """【修正版】テーブル方式による移動プロセス - flight.c準拠の正しいテーブル参照"""
        if self.current_floor == destination_floor:
            print(f"{self.env.now:.2f} [{self.name}] Already at destination floor {destination_floor}")
            return
        
        # 🔧【修正点1】この連続走行の「出発階」を最初に記憶する
        start_floor_of_this_trip = self.current_floor
        
        direction = 1 if destination_floor > start_floor_of_this_trip else -1
        total_time = self.physics_engine.flight_time_table.get((start_floor_of_this_trip, destination_floor), 0)
        
        print(f"{self.env.now:.2f} [{self.name}] Moving from floor {start_floor_of_this_trip} to {destination_floor} (total {total_time:.2f}s) [TABLE METHOD]...")
        
        try:
            current_floor_in_trip = start_floor_of_this_trip
            
            # 各階層を順次移動（巡航フェーズ）
            while current_floor_in_trip != destination_floor:
                # 割り込みチェック
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                next_floor = current_floor_in_trip + direction
                
                # 🔧【完全修正】タイムライン方式と完全に同じタイミングで状態更新
                # Step 1: 🔧【修正点2】記憶した「出発階」をキーとして使用する
                cruise_time = self.physics_engine.cruise_table.get((start_floor_of_this_trip, next_floor), 0.1)
                
                # Step 2: 先に巡航フェーズを実行して時間を進める（タイムライン方式と同じ）
                yield self.env.timeout(cruise_time)
                
                # Step 3: 再度割り込みチェック
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                # Step 4: 時間経過後に物理的なフロアを更新する
                old_floor = current_floor_in_trip
                current_floor_in_trip = next_floor
                self.current_floor = current_floor_in_trip
                
                # Step 5: 予測位置 (advanced_position) を更新する
                # タイムライン方式と同じロジック：現在到達した階と同じ値
                self.advanced_position = current_floor_in_trip
                
                # Step 6: 状態を報告する（時間経過後）
                if self.advanced_position != self.last_advanced_position:
                    self.env.process(self._report_status())
                self.last_advanced_position = self.advanced_position
                
                # 逆戻りチェック
                if self.state == "UP" and current_floor_in_trip < old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {current_floor_in_trip}F")
                    return
                elif self.state == "DOWN" and current_floor_in_trip > old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {current_floor_in_trip}F")
                    return
            
            # 🔧【修正点3】ここでも記憶した「出発階」をキーとして使用する
            brake_time = self.physics_engine.brake_table.get((start_floor_of_this_trip, destination_floor), 0.1)
            
            # 最終制動フェーズ
            if brake_time > 0.05:
                yield self.env.timeout(brake_time)
                
                # 最終割り込みチェック
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled during final braking.")
                    return
            
            print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            
        except Interrupt:
            print(f"{self.env.now:.2f} [{self.name}] Table-based movement process interrupted and terminated.")
            return
    
    def _move_process_with_timeline(self, destination_floor):
        """タイムライン方式による移動プロセス"""
        profile = self.flight_profiles.get((self.current_floor, destination_floor))
        if not profile or not profile.get('timeline'):
            print(f"[{self.name}] Warning: No profile found for {self.current_floor} -> {destination_floor}")
            return

        print(f"{self.env.now:.2f} [{self.name}] Moving from floor {self.current_floor} to {destination_floor} (total {profile['total_time']:.2f}s)...")
        
        try:
            for i, event in enumerate(profile['timeline']):
                # 割り込みチェック：移動中に目的地が変更された場合は中断
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                    
                yield self.env.timeout(event['time_delta'])
                
                # 再度割り込みチェック
                if self.current_destination != destination_floor:
                    print(f"{self.env.now:.2f} [{self.name}] Movement cancelled due to destination change.")
                    return
                
                old_floor = self.current_floor
                self.current_floor = event['advanced_position'] # Fixed: changed from physical_floor to advanced_position
                self.advanced_position = event['advanced_position']
                
                # 逆戻りチェック
                if self.state == "UP" and self.current_floor < old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {self.current_floor}F (Event {i})")
                    return
                elif self.state == "DOWN" and self.current_floor > old_floor:
                    print(f"[{self.name}] ERROR: REVERSE MOVEMENT: {old_floor}F -> {self.current_floor}F (Event {i})")
                    return
                
                if self.advanced_position != self.last_advanced_position:
                    self.env.process(self._report_status())
                self.last_advanced_position = self.advanced_position
            
            print(f"{self.env.now:.2f} [{self.name}] Arrived at floor {self.current_floor}")
            
        except Interrupt:
            # 【修正】割り込み時は静かに終了（ログ出力は上位で行う）
            print(f"{self.env.now:.2f} [{self.name}] Movement process interrupted and terminated.")
            return

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
        hall_calls_changed = False
        if any(q == self.floor_queues[self.current_floor]["UP"] for q in boarding_queues):
            self.hall_calls_up.discard(self.current_floor)
            hall_calls_changed = True
        if any(q == self.floor_queues[self.current_floor]["DOWN"] for q in boarding_queues):
            self.hall_calls_down.discard(self.current_floor)
            hall_calls_changed = True
        
        # hall_callsが変更された場合は状態を送信
        if hall_calls_changed:
            self.env.process(self._broadcast_hall_calls_status())
        
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
            if not self._has_any_down_calls_below() and all_calls and all_calls and self.current_floor == min(all_calls):
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
            if self._has_any_up_calls_above(): return
            farthest_call = max(all_calls) if all_calls else self.current_floor
            if self.current_floor >= farthest_call:
                self._set_state("DOWN")

        elif current_direction == "DOWN":
            if self._has_any_down_calls_below(): return
            farthest_call = min(all_calls) if all_calls else self.current_floor
            if self.current_floor <= farthest_call:
                self._set_state("UP")

        elif current_direction == "IDLE":
            if not self._has_any_calls(): return
            closest_call = min(all_calls, key=lambda f: abs(f - self.current_floor))
            if closest_call > self.current_floor: self._set_state("UP")
            elif closest_call < self.current_floor: self._set_state("DOWN")
            else:
                if self.current_floor in self.hall_calls_up: self._set_state("UP")
                elif self.current_floor in self.hall_calls_down: self._set_state("DOWN")

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

