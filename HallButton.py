# File: HallButton.py
import simpy
from typing import Optional

# 必要なクラスをインポート
from MessageBroker import MessageBroker

class HallButton:
    """
    乗り場の呼び出しボタンを表現するクラス。
    SimPyのプロセスではなく、状態を持つ単純なオブジェクトです。
    """
    def __init__(self, env: simpy.Environment, broker: MessageBroker, floor: int, direction: str):
        """
        HallButtonを初期化します。

        Args:
            env: SimPyのシミュレーション環境。
            broker: 通信を仲介するメッセージブローカー。
            floor: このボタンが設置されている階。
            direction: ボタンの方向 ('UP' または 'DOWN')。
        """
        self.env = env
        self.broker = broker
        self.floor = floor
        self.direction = direction
        self.is_pressed = False # ボタンが押されているかどうかの状態

    def press(self):
        """
        ボタンを押し、GCSに通知します。
        すでに押されている場合は何もしません。
        """
        if not self.is_pressed:
            self.is_pressed = True
            print(f"{self.env.now:.2f} [HallButton] Button pressed at floor {self.floor} ({self.direction}). Light ON.")
            
            # GCS宛に手紙を出す
            call_message = {"floor": self.floor, "direction": self.direction}
            self.broker.publish("gcs/hall_call", call_message)

    def serve(self):
        """
        呼び出しに応答し、ボタンの状態を元に戻します。
        (将来、GCSがエレベータを割り当てた際に呼び出す)
        """
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Button served at floor {self.floor} ({self.direction}). Light OFF.")


if __name__ == '__main__':
    # --- このクラスの動作を確認するための簡単なテストコード ---

    # ダミーのGCSプロセス
    def dummy_gcs_process(env, broker):
        # GCSはホール呼び出しを購読する
        while True:
            # ループの中で、毎回新しい「目覚まし時計」(subscribeイベント)を用意する
            message = yield broker.subscribe("gcs/hall_call")
            print(f"{env.now:.2f} [DummyGCS] Received call: {message}. Now I would assign an elevator.")

    # ダミーの乗客プロセス
    def dummy_passenger_process(env, button):
        yield env.timeout(5) # 5秒後にボタンを押す
        print(f"{env.now:.2f} [Passenger] I'm at floor {button.floor}, going {button.direction}. Pressing the button.")
        button.press()

    # --- セットアップ ---
    env = simpy.Environment()
    broker = MessageBroker(env)
    
    # 5階の上りボタンを作成
    hall_button_5_up = HallButton(env, broker, 5, "UP")

    # ダミーのGCSと乗客を登場させる
    env.process(dummy_gcs_process(env, broker))
    env.process(dummy_passenger_process(env, hall_button_5_up))

    # --- 実行 ---
    print("--- HallButton Test Simulation Start ---")
    env.run(until=10)
    print("--- HallButton Test Simulation End ---")
