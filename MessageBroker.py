import simpy

class MessageBroker:
    """
    シミュレーション内の各コンポーネント間の通信を仲介する。
    トピックベースの出版購読モデルを実装する。
    """
    def __init__(self, env: simpy.Environment):
        """
        メッセージブローカーを初期化する

        Args:
            env (simpy.Environment): SimPy環境
        """
        self.env = env
        self.topics = {}  # トピックごとのStoreを保持する辞書
        self.broadcast_pipe = simpy.Store(self.env)

    def get_pipe(self, topic: str) -> simpy.Store:
        """
        指定されたトピック用の通信パイプ（Store）を取得または作成する
        """
        if topic not in self.topics:
            self.topics[topic] = simpy.Store(self.env)
        return self.topics[topic]

    def put(self, topic: str, message):
        """
        指定されたトピックにメッセージを発行（put）する
        """
        print(f"{self.env.now:.2f} [Broker] Publish on '{topic}': {message}")
        pipe = self.get_pipe(topic)
        self.broadcast_pipe.put({'topic': topic, 'message': message})
        return pipe.put(message)

    def get(self, topic: str):
        """
        指定されたトピックからメッセージを受信（get）するのを待つ
        """
        pipe = self.get_pipe(topic)
        return pipe.get()

    def get_broadcast_pipe(self) -> simpy.Store:
        """
        Statisticsクラスがこのパイプにアクセスするためのメソッド
        全局ブロードキャスト用のパイプを返す
        """
        return self.broadcast_pipe
