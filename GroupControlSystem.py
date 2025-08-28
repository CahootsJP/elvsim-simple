# File: GroupControlSystem.py
import simpy
from typing import List, Any

# 必要なクラスをインポートする
# このファイルを実行するには、同じディレクトリに Entity.py と MessageBroker.py が必要です。
from Entity import Entity
from MessageBroker import MessageBroker
# Elevatorクラスはまだないので、型ヒントのためだけに前方宣言的に扱う
# from Elevator import Elevator # 将来的に型ヒントで使う

class GroupControlSystem(Entity):
    """
    エレベータ群管理システム(GCS)。
    ホール呼び出しを受け取り、最適なエレベータにタスクを割り当てる司令塔。
    """
    def __init__(self, env: simpy.Environment, broker: MessageBroker):
        """
        GCSを初期化します。

        Args:
            env: SimPyのシミュレーション環境。
            broker: 通信を仲介するメッセージブローカー。
        """
        super().__init__(env, "GCS")
        self.broker = broker
        # 管理対象のエレベータのリスト (将来的には複数台になる)
        self.managed_elevators: List[Any] = [] # 本来はList[Elevator]

        # GCSのメインプロセス(runメソッド)はEntityの__init__で自動的に開始される

    def register_elevator(self, elevator):
        """管理対象のエレベータを登録します。"""
        self.managed_elevators.append(elevator)
        print(f"{self.env.now:.2f} [{self.name}] Elevator '{elevator.name}' registered.")

    def run(self):
        """GCSのメインプロセス。ホール呼び出しを待ち受け、タスクを割り当てる。"""
        print(f"{self.env.now:.2f} [{self.name}] GCS is operational. Waiting for hall calls...")
        
        # 'gcs/hall_call' トピックを購読する準備
        hall_call_topic = "gcs/hall_call"

        while True:
            # 郵便局に 'gcs/hall_call' 宛の手紙が来るまで待つ
            message = yield self.broker.subscribe(hall_call_topic)
            
            print(f"{self.env.now:.2f} [{self.name}] Received hall call: {message}")

            # --- 自転車作戦のシンプルなロジック ---
            # とりあえず、管理している最初のエレベータにオウム返しで指示を出す
            if not self.managed_elevators:
                print(f"{self.env.now:.2f} [{self.name}] No elevators registered. Cannot assign task.")
                continue

            # 本来は最適なエレベータを選ぶアルゴリズムがここに入る
            target_elevator = self.managed_elevators[0]
            
            # 指示用のメッセージを作成
            task_message = {
                "task_type": "ASSIGN_HALL_CALL",
                "details": message # 受け取ったメッセージをそのまま流す
            }
            
            # エレベータの専用ポストに手紙を出す
            elevator_topic = f"elevator/{target_elevator.entity_id}/task"
            self.broker.publish(elevator_topic, task_message)


if __name__ == '__main__':
    # --- このクラスの動作を確認するための簡単なテストコード ---
    
    # ダミーのエレベータクラス (Elevator.pyがまだないので)
    # テストのため、本物のEntityクラスを継承する
    class DummyElevator(Entity):
        def __init__(self, env: simpy.Environment, name: str, broker: MessageBroker):
            super().__init__(env, name)
            self.broker = broker

        def run(self):
            # 自身のタスク用ポストを購読する
            task_topic = f"elevator/{self.entity_id}/task"
            while True:
                task = yield self.broker.subscribe(task_topic)
                print(f"{self.env.now:.2f} [{self.name}] Received task: {task}")

    # ダミーの乗客プロセス
    def dummy_passenger_process(env, broker, floor, direction):
        yield env.timeout(5) # 5秒後にボタンを押す
        call_message = {"floor": floor, "direction": direction}
        # self.env.now ではなく、引数で受け取った env を使うのが正解
        print(f"{env.now:.2f} [Passenger] Pressing button: {call_message}")
        broker.publish("gcs/hall_call", call_message)

    # --- セットアップ ---
    env = simpy.Environment()
    broker = MessageBroker(env)
    
    # 本物のGroupControlSystemクラスをインスタンス化する
    gcs = GroupControlSystem(env, broker)

    # ダミーのエレベータを作ってGCSに登録
    elevator1 = DummyElevator(env, "Elevator_1", broker)
    gcs.register_elevator(elevator1)

    # ダミーの乗客を登場させる
    env.process(dummy_passenger_process(env, broker, 5, "UP"))

    # --- 実行 ---
    print("--- GCS Test Simulation Start ---")
    env.run(until=20)
    print("--- GCS Test Simulation End ---")
