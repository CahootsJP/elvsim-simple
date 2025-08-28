# File: Entity.py
import simpy
from abc import ABC, abstractmethod
import itertools # エンティティIDカウンター用のヘルパー
from typing import Optional # 型ヒントのために Optional を追加

class Entity(ABC):
    """
    SimPy シミュレーションにおけるエンティティの抽象基底クラス。

    このクラスは、SimPy プロセスとして動作するエンティティに共通する
    基本的な属性と振る舞いを定義し、SimPy 環境におけるエンティティの
    ライフサイクル管理の基盤を提供します。
    """
    # クラス全体で共有するエンティティIDのカウンター
    _entity_id_counter = itertools.count()

    def __init__(self, env: simpy.Environment, name: str = None):
        """
        エンティティの初期化。

        Args:
            env: このエンティティが所属する SimPy シミュレーション環境。
            name: エンティティの名前。省略可能。指定しない場合はクラス名とIDから自動生成されます。
        """
        self.env = env
        # 一意のエンティティIDを生成
        self.entity_id: int = next(self._entity_id_counter)
        # エンティティの名前を設定
        self.name: str = name if name is not None else f"{self.__class__.__name__}_{self.entity_id}"

        # エンティティの現在の状態を保持する変数
        # 具体的な状態の値は具象クラスで定義・使用されます (例: 'idle', 'moving', 'waiting' など)。
        self.state: str = "initial_state" # 初期状態としてデフォルト値を設定（具象クラスで上書き推奨）

        # このエンティティに対応する SimPy プロセス オブジェクト
        # コンストラクタ内で run() メソッドを実行するプロセスとして開始します。
        # run() メソッドはサブクラスで実装されます。
        self._process = self.env.process(self.run())

        # 初期化完了のログ
        print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}, ID:{self.entity_id}) が作成されました。')
        # 初期状態への遷移ログ（初期状態が 'initial_state' から変わる場合を想定）
        # もし初期状態が具象クラスで設定される場合は、具象クラスの __init__ で
        # set_state を呼び出す方が適切かもしれません。ここでは作成直後の状態としてログ。
        # self._log_state_change(self.state) # 初期状態のログが必要であれば有効化


    @abstractmethod
    def run(self):
        """
        エンティティの SimPy プロセス本体となるジェネレーターメソッド（抽象メソッド）。

        このメソッドは SimPy 環境によって実行され、エンティティのシミュレーション上の
        主要な振る舞いを定義します。このメソッド内で yield を使用してイベントの完了を待ち、
        シミュレーション時間を進めます。
        サブクラスで必ず実装する必要があります。通常は無限ループで状態に応じた
        処理を呼び出す構造になります。

        例:
            while True:
                if self.state == '状態A':
                    yield from self._state_A()
                elif self.state == '状態B':
                    yield from self._state_B()
                else:
                    # 未定義の状態の場合の処理 (エラーログなど)
                    print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}) 不明な状態: {self.state}')
                    yield self.env.timeout(1) # 無限ループ防止のため待機
        """
        pass # 抽象メソッドなので具体的な実装はなし

    # --- 共通で役立つメソッド ---

    def set_state(self, new_state: str):
        """
        エンティティの状態を遷移させます。

        Args:
            new_state: 遷移先の状態を表す文字列。
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self._log_state_change(old_state, new_state)

    def get_state(self) -> str:
        """
        現在のエンティティの状態を取得します。

        Returns:
            現在の状態を表す文字列。
        """
        return self.state

    def _log_state_change(self, old_state: str, new_state: str):
        """
        状態遷移をログに出力する内部ヘルパーメソッド。
        ロギングの詳細度や形式は必要に応じてカスタマイズできます。
        """
        print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}, ID:{self.entity_id}) 状態遷移: {old_state} -> {new_state}')

    # SimPy プロセス オブジェクトへのアクセス
    @property
    def process(self) -> simpy.Process:
        """
        このエンティティの SimPy プロセス オブジェクトを取得します。
        Interrupt をかける際などに使用できます。
        """
        return self._process

    # 必要に応じて、状態ごとの抽象メソッドなども追加
    # @abstractmethod
    # def _state_some_state(self):
    #     """ 'some_state' 状態での処理（サブクラスで実装）"""
    #     pass

    # ESM.java の delays() に相当する概念は、SimPy では各状態メソッド内で
    # yield self.env.timeout(時間) の形で直接記述されることが多いです。
    # 状態に応じた遅延時間を計算する共通メソッドが必要であれば、それもここに追加できます。
    # 例:
    # def get_delay_for_current_state(self) -> float:
    #    """現在の状態に対応する標準的な遅延時間を返します。"""
    #    # 具象クラスで状態に応じた遅延時間を返すロジックを実装
    #    return 0.0 # デフォルト値
