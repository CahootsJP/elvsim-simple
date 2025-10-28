# elvsim - Elevator Simulation System
**VTS Control Suite (Vertical Transport System Control Suite)** - 総合エレベータシミュレーションシステム

SimPyベースの離散事象シミュレーションシステム。Web可視化対応。

---

## 🚀 クイックスタート

### インストール

```bash
# 開発版（推奨）
git clone https://github.com/CahootsJP/elvsim-simple.git
cd elvsim-simple
pip install -r requirements.txt

# または PyPI から（将来）
pip install elvsim
```

### シミュレーション実行

```bash
python main.py
```

実行すると：
- ✅ 3台のエレベータ、10フロアでシミュレーション
- ✅ 600秒（10分間）実行
- ✅ `simulation_log.jsonl` にログ保存
- ✅ 軌跡図（trajectory diagram）を生成

---

### Web可視化（Live/Replay）

#### ターミナル1: シミュレーション実行

```bash
python main.py
```

#### ターミナル2: HTTPサーバー起動

```bash
python visualizer/server/http_server.py

# またはコマンドとして（pip install -e . 後）
elvsim-viz
```

#### ブラウザ

```
http://localhost:5000
```

- **Live**: リアルタイムで観察
- **Replay**: 実行後に再生（速度調整、シーク可能）
- **Dark Mode**: トグルボタンでテーマ切替

詳細は [`visualizer/README.md`](visualizer/README.md) を参照。

---

## 📁 プロジェクト構成

```
elvsim-simple/
│
├── simulator/              # PyPI: elvsim-simulator
│   ├── core/               # コアエンティティ
│   │   ├── entity.py       # 抽象基底クラス
│   │   ├── elevator.py     # エレベータ
│   │   ├── passenger.py    # 乗客
│   │   ├── door.py         # ドア
│   │   └── hall_button.py  # ホールボタン
│   ├── physics/
│   │   └── physics_engine.py  # 物理エンジン
│   ├── infrastructure/
│   │   ├── message_broker.py  # メッセージブローカー
│   │   └── realtime_env.py    # リアルタイム環境
│   ├── interfaces/         # インターフェース定義
│   └── implementations/    # 実装バリエーション
│
├── controller/             # PyPI: elvsim-controller
│   ├── interfaces/         # 群管理インターフェース
│   ├── algorithms/         # アルゴリズム実装
│   └── group_control.py    # GroupControlSystem
│
├── analyzer/               # PyPI: elvsim-analyzer
│   ├── statistics.py       # 統計処理・ログ収集
│   └── reporters/          # レポート生成
│
├── visualizer/             # PyPI: elvsim-visualizer
│   ├── server/
│   │   └── http_server.py  # Flask HTTPサーバー
│   └── static/
│       ├── index.html      # Web UI
│       ├── app.js          # ビューアロジック
│       ├── eventSource.js  # イベントソース抽象化
│       └── style.css       # スタイル（ダークモード対応）
│
├── examples/               # 使用例
│   ├── configs/            # 設定ファイル例
│   └── *.py                # サンプルスクリプト
│
├── tests/                  # テストコード
│   ├── test_simulator/
│   ├── test_controller/
│   ├── test_analyzer/
│   └── test_visualizer/
│
├── docs/                   # ドキュメント
│
├── scripts/                # 開発者向けツール
│
├── main.py                 # メインシミュレーション実行
├── requirements.txt        # 依存パッケージ
├── requirements-dev.txt    # 開発用依存
├── setup.py                # パッケージング設定
├── pyproject.toml          # プロジェクト設定
├── MANIFEST.in             # パッケージング設定
├── LICENSE                 # MITライセンス
└── README.md               # このファイル
```

---

## 🎯 主要機能

### シミュレーション (`simulator/`)
- ✅ SimPy離散事象シミュレーション
- ✅ リアルな物理演算（加速度、躍度考慮）
- ✅ 容量制限、乗降処理
- ✅ ホールコール・カーコール管理
- ✅ ドア開閉タイミング制御（光電センサーモデル）
- ✅ 完全なオブジェクト指向設計

### 群管理 (`controller/`)
- ✅ 複数エレベータ群管理（Group Control System）
- ✅ リアルタイム状態監視
- ✅ 動的割り当てアルゴリズム
- ✅ プラグイン可能なアルゴリズム設計

### データ収集・解析 (`analyzer/`)
- ✅ JSON Lines形式ログ（`simulation_log.jsonl`）
- ✅ 軌跡図自動生成（Matplotlib）
- ✅ イベント単位の詳細記録
- ✅ 実機エレベータログ解析可能

### Web可視化 (`visualizer/`)
- ✅ Live/Replay統一ビューア
- ✅ マルチエレベータ表示（スケーラブル）
- ✅ エレベータホールパネル（待機乗客表示）
- ✅ 号機別カラーコーディング
- ✅ 再生速度調整・シーク機能
- ✅ ダークモード対応
- ✅ HTTP Long Polling（WebSocket不要）

---

## 🛠️ 技術スタック

- **シミュレーション**: Python 3.8+, SimPy
- **データ形式**: JSON Lines (JSONL)
- **Web可視化**: Flask, HTML5/CSS3/JavaScript
- **グラフ生成**: Matplotlib
- **物理計算**: NumPy, SymPy

---

## 📦 PyPI パッケージ構成（将来）

```bash
# メタパッケージ（全部入り）
pip install elvsim

# 個別インストール
pip install elvsim-simulator   # シミュレータ本体
pip install elvsim-controller   # 群管理システム
pip install elvsim-analyzer     # 解析ツール
pip install elvsim-visualizer   # 可視化システム

# 有料版（将来）
pip install elvsim-controller-pro
```

**用途別インストール例:**

1. **フルシステム（開発・研究）**: `pip install elvsim`
2. **アナライザーのみ（既設ビル）**: `pip install elvsim-analyzer`
3. **カスタム構成**: 必要なパッケージを個別選択

---

## 📊 シミュレーションパラメータ（`main.py`）

| パラメータ | 値 | 説明 |
|-----------|---|------|
| `SIM_DURATION` | 600秒 | シミュレーション時間 |
| `NUM_FLOORS` | 10 | フロア数 |
| `NUM_ELEVATORS` | 3 | エレベータ台数 |
| `FLOOR_HEIGHT` | 3.5m | 階高 |
| `MAX_SPEED` | 2.5m/s | 最高速度 |
| `ACCELERATION` | 1.0m/s² | 加速度 |
| `JERK` | 2.0m/s³ | 躍度 |
| `CAPACITY` | 10人 | 定員 |

---

## 🔧 カスタマイズ

### エレベータ台数を変更

`main.py` の以下の部分を編集：

```python
# Create elevators
for i in range(1, 4):  # 3台 → 任意の台数に変更
    door = Door(env, f"Elevator_{i}_Door")
    elevator = Elevator(env, f"Elevator_{i}", broker, NUM_FLOORS, ...)
    gcs.register_elevator(elevator)
```

### 乗客生成パターンを変更

`main.py` の `passenger_generator_integrated_test()` 関数を編集：

```python
def passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues):
    # ここで乗客生成ロジックをカスタマイズ
    yield env.timeout(random.uniform(1, 5))  # 生成間隔
    arrival_floor = random.randint(1, 10)    # 出発階
    destination_floor = random.randint(1, 10) # 目的階
    ...
```

---

## 🐛 トラブルシューティング

### ポートが使用中

```bash
# 既存プロセスを終了
pkill -f "python main.py"
pkill -f "python visualizer/server/http_server.py"
```

### Web可視化が表示されない

1. ブラウザのハードリフレッシュ: `Ctrl + Shift + R`
2. `simulation_log.jsonl` が生成されているか確認
3. ブラウザの開発者ツール（F12）でエラーを確認

### 依存パッケージエラー

```bash
pip install --upgrade -r requirements.txt
```

---

## 📚 詳細ドキュメント

- [Web可視化システム詳細](visualizer/README.md)
- アーキテクチャ詳細: 各Pythonファイルのdocstringを参照
- API リファレンス: `docs/api_reference.md` (準備中)

---

## 🎓 設計思想

### オブジェクト指向設計
- **情報隠蔽**: 各エンティティは内部状態を隠蔽
- **責任の分離**: ボタンを押すのは乗客、割り当てはGCS
- **Look-ahead bias回避**: 未来の情報を使わない

### イベント駆動アーキテクチャ
- MessageBrokerによる疎結合
- 全イベントをJSONLで記録
- Live/Replay統一処理

### パッケージ分離設計
- **simulator**: 物理シミュレーション（独立動作可能）
- **controller**: 群管理アルゴリズム（プラグイン可能）
- **analyzer**: データ解析（実機ログも処理可能）
- **visualizer**: 可視化（シミュレータ不要で動作）

---

## 🏢 実際のビルでの利用例

### パターン1: 既設ビルの運行解析

```bash
pip install elvsim-analyzer elvsim-visualizer

# 実際のエレベータからJSONL形式でログ収集
python -m analyzer.statistics --input /var/log/elevator/log.jsonl --report monthly_report.pdf

# 可視化
elvsim-viz
```

### パターン2: 新規ビルの事前シミュレーション

```bash
pip install elvsim

# ビル仕様に合わせてmain.pyをカスタマイズ
python main.py

# 結果を解析
python -m analyzer.statistics --input simulation_log.jsonl
```

---

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

---

## 🚀 次のステップ

1. **シミュレーションパラメータ調整**: `main.py` を編集
2. **群管理アルゴリズム改良**: `controller/group_control.py` を編集
3. **Web UI拡張**: `visualizer/static/` を編集
4. **実機エレベータ接続**: 同じJSONL形式でデータ送信
5. **カスタムアルゴリズム開発**: `controller/algorithms/` に追加

---

## 🤝 貢献

プルリクエスト歓迎！詳細は `CONTRIBUTING.md` (準備中) を参照。

---

**Enjoy simulating! 🏢✨**
