import simpy
from MessageBroker import MessageBroker

class HallButton:
    """
    乗り場の呼び出しボタン
    """
    def __init__(self, env: simpy.Environment, broker: MessageBroker, floor: int, direction: str):
        """
        ホールボタンを初期化する

        Args:
            env (simpy.Environment): SimPy環境
            broker (MessageBroker): 通信に使うメッセージブローカー
            floor (int): ボタンが設置されている階
            direction (str): ボタンの方向 ("UP" or "DOWN")
        """
        self.env = env
        self.broker = broker
        self.floor = floor
        self.direction = direction
        self.is_pressed = False

    def press(self):
        """
        ボタンを押し、GCSに通知する
        """
        if not self.is_pressed:
            self.is_pressed = True
            print(f"{self.env.now:.2f} [HallButton] Button pressed at floor {self.floor} ({self.direction}). Light ON.")
            call_message = {"floor": self.floor, "direction": self.direction}
            self.broker.put("gcs/hall_call", call_message)

    def serve(self):
        """
        呼び出しに応答があったときにボタンの点灯をリセットする
        """
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Button served at floor {self.floor} ({self.direction}). Light OFF.")
