# File: MessageBroker.py
import simpy
from simpy import Store
from typing import Any, Dict

class MessageBroker:
    """
    SimPy環境内で動作するシンプルなメッセージブローカー（郵便局）。
    トピックベースの出版購読モデルを提供し、各コンポーネント間の通信を仲介します。
    これにより、コンポーネント同士が互いを直接知らなくても通信できる疎結合な設計を実現します。
    """
    def __init__(self, env: simpy.Environment):
        """
        MessageBrokerを初期化します。

        Args:
            env: SimPyのシミュレーション環境。
        """
        self.env = env
        # トピックごとに専用のStore(ポスト)を用意するための辞書
        self.topics: Dict[str, Store] = {}

    def _get_topic_store(self, topic: str) -> Store:
        """トピックに対応するStoreを取得または新規作成する"""
        if topic not in self.topics:
            self.topics[topic] = Store(self.env)
        return self.topics[topic]

    def publish(self, topic: str, message: Any):
        """
        指定されたトピックにメッセージを出版（手紙を投函）します。

        Args:
            topic (str): メッセージの宛先となるトピック (例: "gcs/hall_call")。
            message (Any): 送信するメッセージ本体。
        """
        print(f"{self.env.now:.2f} [Broker] Publish on '{topic}': {message}")
        # 対応するトピックのポストに手紙を入れる
        store = self._get_topic_store(topic)
        return store.put(message)

    def subscribe(self, topic: str) -> simpy.Event:
        """
        指定されたトピックのメッセージを取得するための get イベントを返します。
        購読者はこのイベントを yield することで、メッセージが来るまで待機します。

        Args:
            topic (str): 購読したいトピック。

        Returns:
            simpy.Event: 指定されたトピックのメッセージを取得するための get イベント。
        """
        # 対応するトピックのポストから手紙を取り出す準備
        store = self._get_topic_store(topic)
        return store.get()

# --- このクラスの動作を確認するための簡単なテストコード ---
def publisher_process(env: simpy.Environment, broker: MessageBroker, topic: str, interval: int):
    """一定間隔でメッセージを送信するテスト用のプロセス"""
    for i in range(3):
        yield env.timeout(interval)
        message = f"Message {i+1}"
        broker.publish(topic, message)

def subscriber_process(env: simpy.Environment, name: str, broker: MessageBroker, topic_to_subscribe: str):
    """指定されたトピックのメッセージを受信するまで待機するテスト用のプロセス"""
    print(f"{env.now:.2f} [{name}] Waiting for messages on '{topic_to_subscribe}'...")
    while True:
        # broker.subscribe(topic) は、メッセージが来るまで処理を中断(待機)するイベントを返す
        message = yield broker.subscribe(topic_to_subscribe)
        print(f"{env.now:.2f} [{name}] Received on '{topic_to_subscribe}': {message}")


if __name__ == '__main__':
    # シミュレーション環境を作成
    env = simpy.Environment()
    
    # 郵便局を作成
    broker = MessageBroker(env)

    # 購読者(Subscriber)を作成
    # Elevator_1 は 'elevator/1/task' トピックを購読する
    env.process(subscriber_process(env, "Elevator_1", broker, "elevator/1/task"))

    # GCS は 'gcs/hall_call' トピックを購読する
    env.process(subscriber_process(env, "GCS", broker, "gcs/hall_call"))

    # 出版者(Publisher)を作成
    # 10秒おきに 'elevator/1/task' へ手紙を出す人
    env.process(publisher_process(env, broker, "elevator/1/task", 10))
    # 7秒おきに 'gcs/hall_call' へ手紙を出す人
    env.process(publisher_process(env, broker, "gcs/hall_call", 7))

    # シミュレーションを実行 (40秒間)
    print("--- Simulation Start ---")
    env.run(until=40)
    print("--- Simulation End ---")
