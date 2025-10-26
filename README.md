# VTS Control Suite
**Vertical Transport System Control Suite** - エレベータシミュレーター

SimPyベースの離散事象シミュレーションシステム。Web可視化対応。

---

## 🚀 クイックスタート

### シミュレーション実行

```bash
python main.py
```

実行すると：
- ✅ 2台のエレベータ、10フロアでシミュレーション
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
python visualizer/http_server.py
```

#### ブラウザ

```
http://localhost:5000
```

- **Live**: リアルタイムで観察
- **Replay**: 実行後に再生（速度調整、シーク可能）

詳細は [`visualizer/README.md`](visualizer/README.md) を参照。

---

## 📁 プロジェクト構成

```
elvsim-simple/
├── main.py                    # メインシミュレーション実行スクリプト
├── MessageBroker.py           # エンティティ間メッセージング
├── GroupControlSystem.py      # 群管理システム
├── Elevator.py                # エレベータエンティティ
├── Door.py                    # ドアエンティティ
├── HallButton.py              # ホールボタン
├── Passenger.py               # 乗客エンティティ
├── PhysicsEngine.py           # 物理エンジン（運動プロファイル計算）
├── Statistics.py              # 統計収集・JSONLログ生成
├── visualizer/
│   ├── http_server.py         # Flask HTTPサーバー
│   ├── static/
│   │   ├── index.html         # Web UI
│   │   ├── app.js             # ビューアロジック
│   │   ├── eventSource.js     # イベントソース抽象化
│   │   └── style.css          # スタイル
│   └── README.md              # 可視化システム詳細
├── simulation_log.jsonl       # シミュレーションログ（自動生成）
└── README.md                  # このファイル
```

---

## 🎯 主要機能

### シミュレーション
- ✅ SimPy離散事象シミュレーション
- ✅ 複数エレベータ群管理（Group Control System）
- ✅ リアルな物理演算（加速度、躍度考慮）
- ✅ 容量制限、乗降処理
- ✅ ホールコール・カーコール管理
- ✅ ドア開閉タイミング制御（光電センサーモデル）

### データ収集
- ✅ JSON Lines形式ログ（`simulation_log.jsonl`）
- ✅ 軌跡図自動生成（Matplotlib）
- ✅ イベント単位の詳細記録

### Web可視化
- ✅ Live/Replay統一ビューア
- ✅ マルチエレベータ表示（最大3台）
- ✅ エレベータホールパネル（待機乗客表示）
- ✅ 号機別カラーコーディング
- ✅ 再生速度調整・シーク機能

---

## 🛠️ 技術スタック

- **シミュレーション**: Python 3.x, SimPy
- **データ形式**: JSON Lines (JSONL)
- **Web可視化**: Flask, HTML5/CSS3/JavaScript
- **グラフ生成**: Matplotlib

---

## 📦 依存パッケージ

```bash
pip install -r requirements.txt
```

主要パッケージ:
- `simpy`: 離散事象シミュレーション
- `matplotlib`: グラフ生成
- `flask`: HTTPサーバー
- `flask-cors`: CORS対応

---

## 📊 シミュレーションパラメータ（`main.py`）

| パラメータ | 値 | 説明 |
|-----------|---|------|
| `SIM_DURATION` | 600秒 | シミュレーション時間 |
| `NUM_FLOORS` | 10 | フロア数 |
| `NUM_ELEVATORS` | 2 | エレベータ台数 |
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
# Create Elevator 1
elevator1 = Elevator(...)
gcs.register_elevator(elevator1)

# Create Elevator 2
elevator2 = Elevator(...)
gcs.register_elevator(elevator2)

# Add more elevators here...
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
pkill -f "python visualizer/http_server.py"
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

---

## 📝 ライセンス

VTS Control Suite プロジェクト

---

## 🚀 次のステップ

1. **シミュレーションパラメータ調整**: `main.py` を編集
2. **群管理アルゴリズム改良**: `GroupControlSystem.py` を編集
3. **Web UI拡張**: `visualizer/static/` を編集
4. **実機エレベータ接続**: 同じJSONL形式でデータ送信

---

**Enjoy simulating! 🏢✨**

