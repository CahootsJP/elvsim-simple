# Elevator Simulator - Real-time Visualization

A web-based interface for real-time visualization of the elevator simulation.

## Directory Structure

```
visualizer/
├── server.py           # WebSocket server
├── static/
│   ├── index.html     # HTML interface
│   ├── app.js         # JavaScript client
│   └── style.css      # Stylesheet
└── README.md          # This file
```

## Usage

### Quick Start (Recommended) 🚀

Just run this single command:

```bash
python run_with_visualization.py
```

**This will automatically:**
- ✅ Start HTTP server (port 8080)
- ✅ Start WebSocket server (port 8765)
- ✅ Start the simulation
- ✅ Open your browser automatically

**To stop:** Press `Ctrl+C`

---

### Manual Execution (Alternative)

#### Step 1: Start HTTP Server

```bash
# Run from project root
python -m http.server 8080 --directory visualizer
```

#### Step 2: Start Simulation + WebSocket Server

```bash
# In a separate terminal
python run_with_visualization.py
```

#### Step 3: Open in Browser

```
http://localhost:8080/static/index.html
```

## Features

### Real-time Visualization
- Current elevator position
- State (IDLE, UP, DOWN)
- Passenger count / Capacity
- Event log

### WebSocket Communication
- Bidirectional communication
- Automatic reconnection
- Status indicator

## Data Flow

```
Simulator (SimPy)
    ↓
MessageBroker
    ↓
Statistics.py
    ↓ (Thread-safe queue)
WebSocket Server (server.py)
    ↓ (WebSocket)
Browser (app.js)
    ↓
UI Display (index.html + style.css)
```

## Future Extensions

### Migration Path to Enhanced Version
1. **Server-side**:
   - `message_adapter.py` - Data transformation layer
   - Module separation
   
2. **Frontend-side**:
   - React migration
   - Advanced visualization with Chart.js / D3.js
   - Replay functionality (JSONL file loading)

### Planned Features
- [ ] JSONL file saving
- [ ] Log file replay mode
- [ ] Real-time trajectory diagram
- [ ] Multiple elevator support
- [ ] Performance metrics display

## Technology Stack

- **Backend**: Python, WebSockets, SimPy
- **Frontend**: Vanilla JS, HTML5, CSS3
- **Future**: React, Chart.js, D3.js

## Troubleshooting

### Cannot Connect

1. Check if HTTP server is running:
   ```bash
   ps aux | grep "http.server"
   ```

2. Check if WebSocket server is running (check run_with_visualization.py output)

3. If ports are in use:
   ```bash
   # Check ports in use
   lsof -i :8080
   lsof -i :8765
   ```

### Browser Console Errors

Press F12 to open Developer Tools and check the Console tab.

## License

Part of this project.
