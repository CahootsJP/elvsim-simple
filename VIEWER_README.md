# 🏢 Elevator Simulation Viewer

統一されたエレベータシミュレーションビューア - ライブ実行、録画再生、実機接続に対応

## 🎯 特徴

- ✅ **完全統一**：描画ロジックは1つだけ（デバッグが容易）
- ✅ **2つのモード**：
  - 🔴 **Live**: シミュレーション実行中にリアルタイム表示
  - 📁 **Replay**: 録画ファイルを再生（一時停止・早送り・巻き戻し対応）
- ✅ **JSON Lines形式**：標準化されたログフォーマット
- ✅ **将来対応**：実機エレベータとの接続も同じ仕組みで可能

---

## 🚀 使い方

### 1. HTTPサーバーを起動

```bash
cd /home/abbey/elvsim-simple
python visualizer/http_server.py
```

サーバーが起動したら、ブラウザで開く：
```
http://localhost:5000/static/index_new.html
```

---

### 2. Liveモード（リアルタイム）

1. ブラウザで「🔴 Live」ボタンをクリック
2. 別ターミナルでシミュレーションを実行：
   ```bash
   python main.py
   # または
   python run_with_visualization.py
   ```
3. ブラウザにリアルタイムで表示される（100ms遅延）

---

### 3. Replayモード（録画再生）

1. ブラウザで「📁 Replay」ボタンをクリック
2. ドロップダウンから`simulation_log.jsonl`を選択
3. 「Load」ボタンをクリック
4. 再生コントロール：
   - **⏵ Play / ⏸ Pause**：再生・一時停止
   - **↻ Restart**：最初から再生
   - **Timeline slider**：任意の時刻にジャンプ
   - **速度選択**：0.25x ～ 10x
   - **キーボードショートカット**：
     - `Space`：再生/一時停止
     - `←`：5秒戻る
     - `→`：5秒進む
     - `R`：リスタート

---

## 📊 アーキテクチャ

```
┌────────────────────────────────────────┐
│  Data Source (データソース)             │
├────────────────────────────────────────┤
│  • SimPy (simulation_log.jsonl)       │
│  • Real Elevator (sensor_log.jsonl)   │
│  • Replay File (任意の.jsonl)          │
└─────────────┬──────────────────────────┘
              │
              │ Standard Event Format
              │ {"time": X, "type": Y, "data": Z}
              │
┌─────────────▼──────────────────────────┐
│  Unified Viewer (統一ビューア)          │
│  - handleEvent()                       │
│  - 描画ロジック（1つだけ！）            │
└────────────────────────────────────────┘
```

---

## 🔧 API エンドポイント

HTTPサーバー（`visualizer/http_server.py`）が提供：

| エンドポイント | 説明 |
|---------------|------|
| `GET /` | メインHTML |
| `GET /static/<path>` | 静的ファイル（CSS, JS） |
| `GET /api/status` | サーバーステータス |
| `GET /api/logs/list` | 利用可能なログファイル一覧 |
| `GET /api/logs/<filename>` | ログファイル全体取得（Replay用） |
| `GET /api/logs/stream?file=<name>&from=<line>` | ログファイルの増分取得（Live用） |

---

## 📁 ファイル構成

```
visualizer/
├── http_server.py          # HTTPサーバー（Flask）
├── server.py               # WebSocketサーバー（旧版、参考用）
└── static/
    ├── index_new.html      # メインHTML
    ├── style_new.css       # スタイル
    ├── eventSource.js      # イベントソース抽象化
    ├── viewer.js           # 統一ビューア
    ├── controls.js         # 再生コントロールUI
    └── main_new.js         # メインアプリケーション
```

---

## 🐛 デバッグ方法

### 問題が発生した場合：

1. **ブラウザのコンソールを開く**（F12キー）
2. **ログを確認**：
   ```javascript
   [Viewer] Metadata received: {...}
   [Viewer] Elevator status: {...}
   ```
3. **ログファイルを確認**：
   ```bash
   cat simulation_log.jsonl | jq '.type' | sort | uniq -c
   ```
4. **特定イベントを検索**：
   ```bash
   # 5F UP のイベントを検索
   cat simulation_log.jsonl | jq 'select(.data.floor == 5 and .data.direction == "UP")'
   ```

---

## 🎨 実機エレベータとの接続（将来）

実機側で必要な作業：

```python
# adapter.py（実機側）
import requests
import json

def send_event(event_type, event_data):
    event = {
        "time": time.time(),
        "type": event_type,
        "data": event_data
    }
    
    # HTTPサーバーに送信（将来実装予定）
    requests.post('http://server:5000/api/events', json=event)
    
    # または、ファイルに書き込み
    with open('sensor_log.jsonl', 'a') as f:
        f.write(json.dumps(event) + '\n')

# センサーからのデータを標準形式に変換
send_event('elevator_status', {
    'elevator': 'Elevator_A',
    'floor': get_current_floor(),
    'state': get_direction(),
    'passengers': estimate_passenger_count()
})
```

---

## ✅ テスト済み

- ✅ HTTPサーバー起動
- ✅ API エンドポイント動作確認
- ✅ ログファイル読み込み（170イベント）
- ✅ ストリーミングAPI動作確認

---

## 📝 次のステップ

1. ブラウザでビューアを開いて動作確認
2. 必要に応じてUIを調整
3. 実機接続のプロトタイプ作成

---

**🎉 完成しました！**

