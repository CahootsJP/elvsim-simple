import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Elevator import Elevator

class GroupControlSystem(Entity):
    """
    【v19.0】各エレベータの状況をリアルタイムで監視するようになった司令塔
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker):
        super().__init__(env, name)
        self.broker = broker
        self.elevators = {}
        # 【師匠改造】各エレベータの最新状況を格納する作戦ボード
        self.elevator_statuses = {}

    def register_elevator(self, elevator: Elevator):
        """
        GCSの管理下にエレベータを登録し、その状況監視を開始する
        """
        self.elevators[elevator.name] = elevator
        print(f"{self.env.now:.2f} [GCS] Elevator '{elevator.name}' registered.")
        # このエレベータ専用の状況報告リスナーを起動する
        self.env.process(self._status_listener(elevator.name))

    def _status_listener(self, elevator_name: str):
        """【師匠新設】特定のエレベータからの状況報告を待ち受けるプロセス"""
        status_topic = f"elevator/{elevator_name}/status"
        while True:
            status_message = yield self.broker.get(status_topic)
            self.elevator_statuses[elevator_name] = status_message
            
            # GCSが状況を把握したことをログで確認
            adv_pos = status_message.get('advanced_position')
            state = status_message.get('state')
            phys_pos = status_message.get('physical_floor')
            print(f"{self.env.now:.2f} [GCS] Status Update for {elevator_name}: Adv.Pos={adv_pos}F, State={state}, Phys.Pos={phys_pos}F")


    def run(self):
        """
        GCSのメインプロセス。ホール呼び出しを待ち受ける
        """
        print(f"{self.env.now:.2f} [GCS] GCS is operational. Waiting for hall calls...")
        
        hall_call_topic = 'gcs/hall_call'
        while True:
            message = yield self.broker.get(hall_call_topic)
            print(f"{self.env.now:.2f} [GCS] Received hall call: {message}")

            # TODO: self.elevator_statuses を見て、最適なエレベータを選ぶ
            # 今は単純に最初のエレベータに割り当てる
            if self.elevators:
                first_elevator_name = list(self.elevators.keys())[0]
                
                task_message = {
                    "task_type": "ASSIGN_HALL_CALL",
                    "details": message
                }
                
                task_topic = f"elevator/{first_elevator_name}/task"
                self.broker.put(task_topic, task_message)

