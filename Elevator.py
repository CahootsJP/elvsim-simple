import simpy
from Entity import Entity
from MessageBroker import MessageBroker

class Elevator(Entity):
    """
    セレコレ機能を持つエレベータ
    """

    class Door:
        """エレベータのドア（簡易版）"""
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

    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker, num_floors: int):
        super().__init__(env, name)
        self.broker = broker
        self.num_floors = num_floors
        
        # --- セレコレ用の新しい属性 ---
        self.current_floor = 1
        self.direction = "IDLE"  # "IDLE", "UP", "DOWN"
        
        # 呼び出しを記憶するためのリスト（セットを使うと重複がなくて便利）
        self.car_calls = set()
        self.hall_calls_up = set()
        self.hall_calls_down = set()
        
        # 内部コンポーネント
        self.door = self.Door(env)
        
        # 定数
        self.floor_move_time = 2.0
        
        self.env.process(self.run())
        self.env.process(self.task_listener())

    def task_listener(self):
        """郵便局からタスクを受け取り、やることリストに追加し続ける"""
        task_topic = f"elevator/{self.name}/task"
        car_call_topic = f"elevator/{self.name}/car_call"

        while True:
            # 2種類のポストを同時に監視する
            task_event = self.broker.get(task_topic)
            car_call_event = self.broker.get(car_call_topic)
            
            # どちらかの手紙が来たら、処理を始める
            result = yield task_event | car_call_event
            
            if task_event in result:
                task = result[task_event]
                self._process_hall_call(task)
            
            if car_call_event in result:
                car_call = result[car_call_event]
                self._process_car_call(car_call)

    def _process_hall_call(self, task):
        """乗り場呼び出しをやることリストに追加する"""
        details = task['details']
        floor = details['floor']
        direction = details['direction']
        
        if direction == "UP":
            self.hall_calls_up.add(floor)
        elif direction == "DOWN":
            self.hall_calls_down.add(floor)
        
        print(f"{self.env.now:.2f} [{self.name}] Hall call registered: Floor {floor} {direction}. Lists: car={self.car_calls}, up={self.hall_calls_up}, down={self.hall_calls_down}")

    def _process_car_call(self, car_call):
        """かご呼びをやることリストに追加する"""
        dest_floor = car_call['destination']
        self.car_calls.add(dest_floor)
        print(f"{self.env.now:.2f} [{self.name}] Car call registered: Floor {dest_floor}. Lists: car={self.car_calls}, up={self.hall_calls_up}, down={self.hall_calls_down}")

    def run(self):
        """エレベータのメインロジック"""
        print(f"{self.env.now:.2f} [{self.name}] Operational at floor {self.current_floor}. Waiting for calls.")
        
        # --- ここから下に、セレコレのアルゴリズムを実装していく ---
        while True:
            # 今はまだ何もしないで、1秒待つだけ
            # TODO: decide_next_move() のような判断ロジックを実装する
            yield self.env.timeout(1)

    # --- これから作るセレコレ用のメソッド（今はまだ空っぽ） ---
    def _decide_next_direction(self):
        pass # 次の進行方向を決めるロジック

    def _find_next_stop(self):
        pass # 現在の進行方向で、次に停まるべき階を見つけるロジック

    def _move_to_floor(self, target_floor):
        pass # 指定された階まで移動するロジック

    def _service_floor(self):
        pass # 到着した階で乗客を乗降させるロジック
