import simpy
from Entity import Entity
from MessageBroker import MessageBroker
from Elevator import Elevator

class GroupControlSystem(Entity):
    """
    複数のエレベータを管理する司令塔（GCS）
    """
    def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker):
        """
        GCSを初期化する

        Args:
            env (simpy.Environment): SimPy環境
            name (str): このGCSの名前
            broker (MessageBroker): 通信に使うメッセージブローカー
        """
        super().__init__(env, name)
        self.broker = broker
        self.elevators = {}  # 管理下の本物のエレベータを登録する
        #self.env.process(self.run())

    def register_elevator(self, elevator: Elevator):
        """
        GCSの管理下にエレベータを登録する
        """
        self.elevators[elevator.name] = elevator
        print(f"{self.env.now:.2f} [GCS] Elevator '{elevator.name}' registered.")

    def run(self):
        """
        GCSのメインプロセス。ホール呼び出しを待ち受ける
        """
        print(f"{self.env.now:.2f} [GCS] GCS is operational. Waiting for hall calls...")
        
        while True:
            # 郵便局で 'gcs/hall_call' 宛の手紙を待つ
            message = yield self.broker.get('gcs/hall_call')
            print(f"{self.env.now:.2f} [GCS] Received hall call: {message}")

            # TODO: どのエレベータに割り当てるかの賢いロジック（セレコレなど）
            # 今は単純に最初のエレベータに割り当てる
            if self.elevators:
                # 辞書から最初のエレベータを取得
                first_elevator_name = list(self.elevators.keys())[0]
                
                # タスクメッセージを作成
                task_message = {
                    "task_type": "ASSIGN_HALL_CALL",
                    "details": message
                }
                
                # エレベータ宛のポストに手紙を出す
                task_topic = f"elevator/{first_elevator_name}/task"
                self.broker.put(task_topic, task_message)