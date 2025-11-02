# 🏢 Elevator Simulation Viewer

Unified elevator simulation viewer - supports live execution, replay, and real elevator connection

## 🎯 Features

- ✅ **Fully Unified**: Single rendering logic (easy to debug)
- ✅ **Two Modes**:
  - 🔴 **Live**: Real-time display during simulation
  - 📁 **Replay**: Playback recorded files (with pause, fast-forward, rewind)
- ✅ **JSON Lines Format**: Standardized log format
- ✅ **Future-Ready**: Real elevator connection using the same mechanism

---

## 🚀 Usage

### 1. Start HTTP Server

```bash
cd /home/abbey/elvsim-simple
python visualizer/http_server.py
```

Once the server is running, open in browser:
```
http://localhost:5000/static/index_new.html
```

---

### 2. Live Mode (Real-time)

1. Click "🔴 Live" button in browser
2. Run simulation in a separate terminal:
   ```bash
   python main.py
   # or
   python run_with_visualization.py
   ```
3. Display updates in real-time in browser (100ms delay)

---

### 3. Replay Mode (Playback)

1. Click "📁 Replay" button in browser
2. Select `simulation_log.jsonl` from dropdown
3. Click "Load" button
4. Playback controls:
   - **⏵ Play / ⏸ Pause**: Play/pause
   - **↻ Restart**: Start from beginning
   - **Timeline slider**: Jump to any time
   - **Speed selection**: 0.25x ~ 10x
   - **Keyboard shortcuts**:
     - `Space`: Play/pause
     - `←`: Rewind 5 seconds
     - `→`: Forward 5 seconds
     - `R`: Restart

---

## 📊 Architecture

```
┌────────────────────────────────────────┐
│  Data Source                           │
├────────────────────────────────────────┤
│  • SimPy (simulation_log.jsonl)       │
│  • Real Elevator (sensor_log.jsonl)   │
│  • Replay File (any .jsonl)           │
└─────────────┬──────────────────────────┘
              │
              │ Standard Event Format
              │ {"time": X, "type": Y, "data": Z}
              │
┌─────────────▼──────────────────────────┐
│  Unified Viewer                        │
│  - handleEvent()                       │
│  - Rendering Logic (Single!)           │
└────────────────────────────────────────┘
```

---

## 🔧 API Endpoints

Provided by HTTP server (`visualizer/http_server.py`):

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main HTML |
| `GET /static/<path>` | Static files (CSS, JS) |
| `GET /api/status` | Server status |
| `GET /api/logs/list` | List available log files |
| `GET /api/logs/<filename>` | Get entire log file (for Replay) |
| `GET /api/logs/stream?file=<name>&from=<line>` | Get incremental log entries (for Live) |

---

## 📁 File Structure

```
visualizer/
├── http_server.py          # HTTP Server (Flask)
├── server.py               # WebSocket Server (legacy, reference)
└── static/
    ├── index_new.html      # Main HTML
    ├── style_new.css       # Styles
    ├── eventSource.js      # Event source abstraction
    ├── viewer.js           # Unified viewer
    ├── controls.js         # Playback control UI
    └── main_new.js         # Main application
```

---

## 🐛 Debugging

### If problems occur:

1. **Open browser console** (F12 key)
2. **Check logs**:
   ```javascript
   [Viewer] Metadata received: {...}
   [Viewer] Elevator status: {...}
   ```
3. **Check log file**:
   ```bash
   cat simulation_log.jsonl | jq '.type' | sort | uniq -c
   ```
4. **Search for specific events**:
   ```bash
   # Search for 5F UP events
   cat simulation_log.jsonl | jq 'select(.data.floor == 5 and .data.direction == "UP")'
   ```

---

## 🎨 Real Elevator Connection (Future)

Required work on real elevator side:

```python
# adapter.py (real elevator side)
import requests
import json

def send_event(event_type, event_data):
    event = {
        "time": time.time(),
        "type": event_type,
        "data": event_data
    }
    
    # Send to HTTP server (future implementation)
    requests.post('http://server:5000/api/events', json=event)
    
    # Or write to file
    with open('sensor_log.jsonl', 'a') as f:
        f.write(json.dumps(event) + '\n')

# Convert sensor data to standard format
send_event('elevator_status', {
    'elevator': 'Elevator_A',
    'floor': get_current_floor(),
    'state': get_direction(),
    'passengers': estimate_passenger_count()
})
```

---

## ✅ Tested

- ✅ HTTP server startup
- ✅ API endpoint verification
- ✅ Log file loading (170 events)
- ✅ Streaming API verification

---

## 📝 Next Steps

1. Open viewer in browser and verify operation
2. Adjust UI as needed
3. Create real elevator connection prototype

---

**🎉 Complete!**
