# Elevator Simulator - Unified Visualization System

A web-based interface for both **Live** and **Replay** visualization of the elevator simulation.

## Architecture Overview

```
Simulator (SimPy)
    ↓
MessageBroker
    ↓
Statistics.py
    ↓
simulation_log.jsonl (JSON Lines log file)
    ↓
HTTP Server (Flask)
    ↓ (HTTP Long Polling / File Download)
Browser (app.js)
    ↓
UI Display (index.html + style.css)
```

## Directory Structure

```
visualizer/
├── http_server.py     # Flask HTTP server (API + static file serving)
├── static/
│   ├── index.html     # HTML interface (unified Live/Replay UI)
│   ├── app.js         # JavaScript client (unified viewer)
│   ├── eventSource.js # Event source abstraction (FileEventSource, LiveFileEventSource)
│   └── style.css      # Stylesheet
└── README.md          # This file
```

## Usage

### Method 1: Live Visualization (Real-time) 🔴

Watch the simulation as it runs in real-time.

#### Step 1: Start the Simulation

```bash
python main.py
```

This will:
- ✅ Run the simulation
- ✅ Generate `simulation_log.jsonl` continuously
- ⏰ Run for 600 seconds (10 minutes)

#### Step 2: Start the HTTP Server

In a **separate terminal**:

```bash
python visualizer/http_server.py
```

This will:
- ✅ Start Flask server on port 5000
- ✅ Serve static files and API endpoints

#### Step 3: Open in Browser

```
http://localhost:5000
```

#### Step 4: Select "Live" Mode

- Click the **"Live"** button
- The viewer will automatically poll `simulation_log.jsonl` and update in real-time

**To stop:**
- Press `Ctrl+C` in both terminals

---

### Method 2: Replay Mode (After Simulation) ⏯️

Replay a previously recorded simulation.

#### Step 1: Run the Simulation (if not done already)

```bash
python main.py
```

This generates `simulation_log.jsonl`.

#### Step 2: Start the HTTP Server

```bash
python visualizer/http_server.py
```

#### Step 3: Open in Browser

```
http://localhost:5000
```

#### Step 4: Select "Replay" Mode

- Click the **"Replay"** button
- Select a log file from the dropdown (e.g., `simulation_log.jsonl`)
- Use playback controls:
  - ▶️ **Play/Pause**
  - ⏮️ **Restart**
  - ⏩ **Speed control** (0.5x, 1x, 2x, 5x, 10x)
  - 🎚️ **Timeline slider** (seek to any time)

---

## Quick Start (Batch Script) 🚀

For convenience, you can use this one-liner (requires `tmux` or manual terminal splitting):

```bash
# Terminal 1: Start simulation
python main.py &

# Terminal 2: Start HTTP server
python visualizer/http_server.py
```

Then open `http://localhost:5000` and select **"Live"** mode.

---

## Features

### 🎨 Unified Interface
- **Single HTML/JS codebase** for both Live and Replay modes
- **Mode switcher** (Live ↔ Replay)
- **Elevator Hall panel** (displays waiting passengers)
- **Multi-elevator support** (up to 3 elevators displayed side-by-side)
- **Color-coded calls**:
  - Elevator 1: Sky blue (`#87CEEB`)
  - Elevator 2: Orange (`#FFA500`)
  - Elevator 3: Lime green (`#32CD32`)

### 📊 Real-time Display
- Elevator position, state, passenger count
- Hall calls (UP/DOWN buttons)
- Car calls (destination floors)
- Door open/close animations
- Waiting passengers count

### ⏯️ Playback Controls (Replay Mode)
- Play/Pause
- Restart
- Speed adjustment (0.5x ~ 10x)
- Timeline scrubbing
- Current time display

### 📡 Event Source Abstraction
- `FileEventSource`: Loads and replays JSONL log files
- `LiveFileEventSource`: Polls JSONL file for new events (HTTP Long Polling)
- `WebSocketEventSource`: (Reserved for future WebSocket support)

---

## Technology Stack

- **Backend**: Python, Flask, Flask-CORS, SimPy
- **Frontend**: Vanilla JS (ES6), HTML5, CSS3 (Flexbox)
- **Data Format**: JSON Lines (JSONL)
- **Communication**: HTTP REST API + Long Polling

---

## API Endpoints

The Flask server (`http_server.py`) provides the following endpoints:

### `GET /`
Returns the main HTML interface.

### `GET /static/<filename>`
Serves static files (HTML, JS, CSS).

### `GET /api/status`
Returns server status.

```json
{
  "server": "Elevator Visualization HTTP Server",
  "status": "ok",
  "version": "1.0"
}
```

### `GET /api/logs/list`
Lists all available JSONL log files.

```json
[
  {
    "name": "simulation_log.jsonl",
    "size": 123456,
    "modified": 1698765432.123
  }
]
```

### `GET /api/logs/<filename>`
Downloads a specific log file.

### `GET /api/logs/stream?file=<filename>&from=<line_number>`
Streams new log entries from a specific line number (for Live mode polling).

```json
[
  { "time": 10.5, "type": "elevator_status", "data": { ... } },
  { "time": 11.0, "type": "hall_call_registered", "data": { ... } }
]
```

---

## Troubleshooting

### Port Already in Use

If you see `Address already in use` error:

```bash
# Kill existing Flask server
pkill -f "python visualizer/http_server.py"

# Or kill existing simulation
pkill -f "python main.py"
```

### Browser Shows Empty Screen

1. **Hard refresh**: Press `Ctrl + Shift + R` (or `Cmd + Shift + R` on Mac)
2. **Clear cache**: Open Developer Tools (F12) → Application → Clear storage
3. **Check console**: F12 → Console tab for errors

### No Events Displayed (Live Mode)

1. Check if `simulation_log.jsonl` exists and is growing:
   ```bash
   ls -lh simulation_log.jsonl
   tail -f simulation_log.jsonl
   ```
2. Check if the simulation is running:
   ```bash
   ps aux | grep run_with_visualization.py
   ```
3. Check Flask server logs for errors

### Replay Mode Not Working

1. Ensure the log file is complete (simulation finished)
2. Check if the log file is valid JSON Lines:
   ```bash
   head -n 5 simulation_log.jsonl
   ```
3. Open Developer Tools (F12) → Network tab to check if file is loading

---

## Comparison: Old vs New System

| Feature | Old (WebSocket) | New (JSON Lines) |
|---------|----------------|------------------|
| Live mode | ✅ WebSocket | ✅ HTTP Long Polling |
| Replay mode | ❌ Not supported | ✅ Full playback controls |
| Debugging | ⚠️ No logs | ✅ JSONL file inspection |
| Reproducibility | ❌ Hard to reproduce | ✅ Exact replay from logs |
| Complexity | ⚠️ Multi-threaded | ✅ Simple HTTP |
| Real elevator support | ⚠️ Requires WebSocket | ✅ Same JSONL format |

---

## Future Extensions

### Planned Features
- [ ] Real elevator integration (via JSONL streaming)
- [ ] Multiple log file comparison
- [ ] Export trajectory diagram from replay
- [ ] WebSocket support (optional, for ultra-low latency)
- [ ] ZeroMQ support (optional, for distributed systems)

### Migration to React
The current vanilla JS implementation can be migrated to React for better state management and component reusability. The event source abstraction (`eventSource.js`) makes this migration straightforward.

---

## Folder Reorganization (Future)

```
visualizer/
├── backend/
│   ├── http_server.py
│   └── websocket_server.py (optional)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── eventSources/
│   │   └── App.js
│   └── public/
└── logs/
    └── *.jsonl
```

---

## License

Part of the VTS Control Suite project.
