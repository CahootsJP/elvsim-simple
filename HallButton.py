import simpy
from MessageBroker import MessageBroker

class HallButton:
    """
    エレベータの乗り場呼び出しボタン（状態管理機能付き）
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

    def is_lit(self):
        """ボタンが点灯しているかチェック"""
        return self.is_pressed
    
    def press(self, passenger_name=None):
        """ボタンが押された時の処理"""
        if not self.is_pressed:
            self.is_pressed = True
            print(f"{self.env.now:.2f} [HallButton] Button pressed at floor {self.floor} ({self.direction}). Light ON.")
            
            call_message = {'floor': self.floor, 'direction': self.direction}
            # GCS宛のポストに手紙を投函する
            self.broker.put("gcs/hall_call", call_message)
            
            # 【新規】可視化用の新規hall_call登録メッセージを送信
            if passenger_name:
                new_hall_call_message = {
                    "timestamp": self.env.now,
                    "floor": self.floor,
                    "direction": self.direction,
                    "passenger_name": passenger_name
                }
                new_hall_call_topic = f"hall_button/floor_{self.floor}/new_hall_call"
                self.broker.put(new_hall_call_topic, new_hall_call_message)
            
            return True  # 新規登録成功
        else:
            # 既に点灯している場合
            if passenger_name:
                print(f"{self.env.now:.2f} [HallButton] Button at floor {self.floor} ({self.direction}) already lit by someone else. {passenger_name} sees the light.")
            return False  # 既に登録済み

    def serve(self):
        """呼び出しに応答があった時の処理（ライトを消すなど）"""
        if self.is_pressed:
            self.is_pressed = False
            print(f"{self.env.now:.2f} [HallButton] Call served at floor {self.floor} ({self.direction}). Light OFF.")