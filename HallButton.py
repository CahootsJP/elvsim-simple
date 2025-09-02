import simpy
from MessageBroker import MessageBroker

class HallButton:
    """
    エレベータの乗り場呼び出しボタン
    """
    def __init__(self, env: simpy.Environment, floor: int, direction: str, broker: MessageBroker):
        """
        Args:
            env (simpy.Environment): SimPy環境
            floor (int): ボタンが設置されている階
            direction (str): 'UP' または 'DOWN'
            broker (MessageBroker): 通信を仲介するメッセージブローカー
        """
        self.env = env
        self.floor = floor
        self.direction = direction
        self.broker = broker
        self.is_pressed = False

    def press(self):
        """ボタンが押された時の処理"""
        if not self.is_pressed:
            self.is_pressed = True
            print(f"{self.env.now:.2f} [HallButton] Button pressed at floor {self.floor} ({self.direction}). Light ON.")
            
            call_message = {'floor': self.floor, 'direction': self.direction}
            # GCS宛のポストに手紙を投函する
            self.broker.put("gcs/hall_call", call_message)

    def serve(self):
        """呼び出しに応答があった時の処理（ライトを消すなど）"""
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Call served at floor {self.floor} ({self.direction}). Light OFF.")