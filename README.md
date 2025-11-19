# elvsim - Elevator Simulation System

[![Status](https://img.shields.io/badge/status-active%20development-yellow)](https://github.com/CahootsJP/elvsim-simple)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![SimPy](https://img.shields.io/badge/simpy-4.0%2B-orange)](https://simpy.readthedocs.io/)

**VTS Control Suite (Vertical Transport System Control Suite)** - Comprehensive Elevator Simulation System

SimPy-based discrete event simulation system with web visualization support.

---

## 🚧 Development Status

**Core Features: Functional ✅** | **Next: PyPI Packaging 🔄**

### ✅ Functional
- Discrete Event Simulator with realistic physics
- Web Visualization (Live/Replay with dark mode)
- Multi-elevator Group Control System
- Event-driven Architecture & Data Analysis (JSONL)

### 🔄 In Progress
- PyPI Package Publishing (`elvsim`, `elvsim-simulator`, `elvsim-controller`, etc.)
- Comprehensive Documentation
- Test Coverage

### 🔮 Planned
- Advanced AI/ML-based algorithms
- Real building integration support

<details>
<summary><b>📋 Detailed Feature List (Click to expand)</b></summary>

### Core Simulator (`simulator/`)
- [x] Discrete Event Simulator (SimPy-based)
- [x] Realistic Physics Engine (S-curve velocity profile, jerk consideration)
- [x] State/Direction Management System
- [x] Capacity Limits & Boarding/Alighting Processing
- [x] Door Open/Close Timing Control (photoelectric sensor model)
- [x] Message Broker for Event-Driven Architecture
- [x] Selective-Collective Operation Logic

### Group Control System (`group_control/`)
- [x] Multi-elevator Group Control
- [x] Nearest Car Strategy (Circular Distance-based)
- [x] Real-time Status Monitoring
- [x] Dynamic Hall Call Assignment
- [x] Pluggable Algorithm Design (Strategy Pattern)
- [x] Allocation Strategy Interface (`IAllocationStrategy`)
- [x] Repositioning Strategy Interface (`IRepositioningStrategy`)
- [x] Move Commands (Idle repositioning)
- [x] Forced Move Commands (Predictive hall call equivalent)
- [x] Arrival Time Predictor (Physics-based prediction with learning capability)
- [ ] Waiting Time Strategy (Prediction-based allocation, planned)

### Data Analysis (`analyzer/`)
- [x] JSON Lines Format Logging
- [x] Event-Level Detailed Recording
- [x] Trajectory Diagram Generation (Matplotlib)
- [x] Real Elevator Log Analysis Support

### Web Visualization (`visualizer/`)
- [x] Live Mode (Real-time Display)
- [x] Replay Mode (Playback Controls with speed adjustment)
- [x] Call System Type Badge (Automatic detection of Traditional/DCS/Hybrid systems)
- [x] Call Status Indicators (hall calls ●, car calls ○, forced calls ◆, move commands ▲)
- [x] Performance Monitor Tab (Real-world compatible metrics)
  - Response times (avg, max, long response count)
  - Trip counts, door operations, travel distances
  - Per-elevator statistics
- [x] Event Log with Category Filtering
  - Door events, hall calls, car calls, passengers, elevator status, commands
- [x] Dark Mode UI
- [x] Multi-elevator Display (scalable)
- [x] HTTP Long Polling (WebSocket-free)
- [x] Elevator Hall Panel (waiting passenger display)

### Architecture
- [x] Modular Package Design (Simulator/Controller/Analyzer/Visualizer)
- [x] Event-Driven Architecture
- [x] Information Hiding & Separation of Concerns
- [x] Look-ahead Bias Avoidance

</details>

---

## 🚀 Quick Start

### Installation

```bash
# Development version (recommended)
git clone https://github.com/CahootsJP/elvsim-simple.git
cd elvsim-simple
pip install -r requirements.txt

# Or from PyPI (future)
pip install elvsim
```

### Run Simulation

```bash
# Run with default configuration
python main.py

# Run with custom configuration files
python -c "from main import run_simulation; run_simulation('scenarios/simulation/office_morning_rush.yaml', 'scenarios/group_control/nearest_car.yaml')"
```

This will:
- ✅ Simulate 4 elevators with 10 floors
- ✅ Run for configured duration (default: 300 seconds)
- ✅ Save logs to `simulation_log.jsonl`
- ✅ Generate trajectory diagram

### Configuration Files

**NEW**: Settings are now managed via YAML configuration files!

```bash
# Available configurations
scenarios/
├── group_control/           # Group control settings (real-system compatible)
│   ├── nearest_car.yaml
│   └── test_forced_move.yaml
└── simulation/             # Simulation settings (simulator only)
    ├── default.yaml
    ├── office_morning_rush.yaml
    └── test_short.yaml
```

See [`config/README.md`](config/README.md) for detailed configuration documentation.

---

### Web Visualization (Live/Replay)

#### Terminal 1: Run Simulation

```bash
python main.py
```

#### Terminal 2: Start HTTP Server

```bash
python visualizer/server/http_server.py

# Or as a command (after pip install -e .)
elvsim-viz
```

#### Browser

```
http://localhost:5000
```

**Features:**
- **Live**: Observe in real-time
- **Replay**: Replay after execution (with speed control and seeking)
- **Call System Badge**: Displays the call system type (Conventional Up-Down, Full DCS, or Hybrid DCS) with automatic detection
- **Performance Monitor**: Real-world compatible metrics (response times, trips, door operations, distances)
- **Event Log**: Filterable by category (door, hall calls, car calls, passengers, elevator status, commands)
- **Call Indicators**: Visual display of hall calls (●), car calls (○), forced calls (◆), and move commands (▲)
- **Dark Mode**: Toggle theme with button

For details, see [`visualizer/README.md`](visualizer/README.md).

---

## 📁 Project Structure

```
elvsim-simple/
│
├── config/                 # Configuration management (NEW!)
│   ├── __init__.py         # Configuration package
│   ├── group_control.py    # Group control config classes
│   ├── simulation.py       # Simulation config classes
│   ├── config_loader.py    # YAML loader utilities
│   └── README.md           # Configuration documentation
│
├── scenarios/              # Configuration files (NEW!)
│   ├── group_control/      # Group control settings
│   │   ├── nearest_car.yaml
│   │   └── test_forced_move.yaml
│   └── simulation/         # Simulation settings
│       ├── default.yaml
│       ├── office_morning_rush.yaml
│       └── test_short.yaml
│
├── simulator/              # PyPI: elvsim-simulator
│   ├── core/               # Core entities
│   │   ├── entity.py       # Abstract base class
│   │   ├── elevator.py     # Elevator
│   │   ├── passenger.py    # Passenger
│   │   ├── door.py         # Door
│   │   └── hall_button.py  # Hall button
│   ├── physics/
│   │   └── physics_engine.py  # Physics engine
│   ├── infrastructure/
│   │   ├── message_broker.py  # Message broker
│   │   └── realtime_env.py    # Real-time environment
│   ├── interfaces/         # Interface definitions
│   └── implementations/    # Implementation variations
│
├── controller/             # PyPI: elvsim-controller
│   ├── interfaces/         # Group control interfaces
│   ├── algorithms/         # Algorithm implementations
│   └── group_control.py    # GroupControlSystem
│
├── analyzer/               # PyPI: elvsim-analyzer
│   ├── statistics.py       # Statistics processing & log collection
│   └── reporters/          # Report generation
│
├── visualizer/             # PyPI: elvsim-visualizer
│   ├── server/
│   │   └── http_server.py  # Flask HTTP server
│   └── static/
│       ├── index.html      # Web UI
│       ├── app.js          # Viewer logic
│       ├── eventSource.js  # Event source abstraction
│       └── style.css       # Styles (dark mode support)
│
├── examples/               # Usage examples
│   ├── configs/            # Configuration file examples
│   └── *.py                # Sample scripts
│
├── tests/                  # Test code
│   ├── test_simulator/
│   ├── test_controller/
│   ├── test_analyzer/
│   └── test_visualizer/
│
├── docs/                   # Documentation
│
├── scripts/                # Developer tools
│
├── main.py                 # Main simulation execution
├── requirements.txt        # Dependencies
├── requirements-dev.txt    # Development dependencies
├── setup.py                # Packaging configuration
├── pyproject.toml          # Project configuration
├── MANIFEST.in             # Packaging configuration
├── LICENSE                 # MIT License
└── README.md               # This file
```

---

## 🎯 Key Features

### Simulation (`simulator/`)
- ✅ SimPy discrete event simulation
- ✅ Realistic physics (acceleration, jerk consideration)
- ✅ Capacity limits, boarding/alighting processing
- ✅ Hall call & car call management
- ✅ Door open/close timing control (photoelectric sensor model)
- ✅ Complete object-oriented design

### Group Control (`controller/`)
- ✅ Multi-elevator group control (Group Control System)
- ✅ Real-time status monitoring
- ✅ Dynamic assignment algorithms
- ✅ Pluggable algorithm design (Allocation & Repositioning strategies)
- ✅ Move commands (idle repositioning)
- ✅ Forced move commands (hall call equivalent for predictive positioning)

### Data Collection & Analysis (`analyzer/`)
- ✅ JSON Lines format logs (`simulation_log.jsonl`)
- ✅ Automatic trajectory diagram generation (Matplotlib)
- ✅ Detailed event-level recording
- ✅ Real elevator log analysis capability

### Web Visualization (`visualizer/`)
- ✅ Unified Live/Replay viewer
- ✅ Multi-elevator display (scalable)
- ✅ Call system type badge (auto-detects Traditional/Full DCS/Hybrid DCS)
- ✅ Elevator hall panel (waiting passenger display)
- ✅ Color-coded by elevator
- ✅ Call status indicators (hall calls ●, car calls ○, forced calls ◆, move commands ▲)
- ✅ Event log with category-based filtering (door, hall calls, car calls, passengers, elevator status, commands)
- ✅ Performance monitor (response times, trip counts, door operations, distances) - Real-world compatible
- ✅ Playback speed control & seek functionality
- ✅ Dark mode support
- ✅ HTTP Long Polling (no WebSocket required)

---

## 🛠️ Technology Stack

- **Simulation**: Python 3.8+, SimPy
- **Data Format**: JSON Lines (JSONL)
- **Web Visualization**: Flask, HTML5/CSS3/JavaScript
- **Graph Generation**: Matplotlib
- **Physics Calculation**: NumPy, SymPy

---

## 📦 PyPI Package Structure (Future)

```bash
# Meta-package (all-in-one)
pip install elvsim

# Individual installation
pip install elvsim-simulator   # Simulator core
pip install elvsim-controller   # Group control system
pip install elvsim-analyzer     # Analysis tools
pip install elvsim-visualizer   # Visualization system

# Premium version (future)
pip install elvsim-controller-pro
```

**Installation Examples by Use Case:**

1. **Full System (Development/Research)**: `pip install elvsim`
2. **Analyzer Only (Existing Building)**: `pip install elvsim-analyzer`
3. **Custom Configuration**: Select individual packages as needed

---

## 📊 Simulation Parameters (Configuration Files)

**NEW**: Parameters are now configured via YAML files instead of hardcoded values!

### Default Configuration (`scenarios/simulation/default.yaml`)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `simulation_duration` | 300s | Simulation time |
| `num_floors` | 10 | Number of floors |
| `num_elevators` | 4 | Number of elevators |
| `floor_height` | 3.5m | Floor height |
| `rated_speed` | 2.5m/s | Maximum speed |
| `acceleration` | 1.0m/s² | Acceleration |
| `jerk` | 2.0m/s³ | Jerk |
| `max_capacity` | 10 people | Capacity |
| `passenger_generation_rate` | 0.1/s | Passenger generation rate |

Edit configuration files in `scenarios/` to customize parameters!

---

## 🔧 Customization

**NEW**: Use configuration files for easy customization!

### Change Number of Elevators

Edit `scenarios/simulation/default.yaml`:

```yaml
simulation:
  elevator:
    num_elevators: 4  # Change to any number
    max_capacity: 10
    rated_speed: 2.5
    # ... other settings
```

### Change Passenger Generation Pattern

Edit `scenarios/simulation/default.yaml`:

```yaml
simulation:
  traffic:
    passenger_generation_rate: 0.2  # Passengers per second (0.2 = 1 per 5 seconds avg)
    simulation_duration: 600.0      # Simulation time in seconds
    
    # Custom Origin-Destination matrix (optional)
    od_matrix:
      - [0.00, 0.15, 0.15, ...]  # From floor 1 to others
      - [0.90, 0.00, 0.02, ...]  # From floor 2 to others
      # ...
```

See [`config/README.md`](config/README.md) for full configuration options.

### Create Custom Scenario

1. Copy existing configuration:
   ```bash
   cp scenarios/simulation/default.yaml scenarios/simulation/my_scenario.yaml
   ```

2. Edit settings in `my_scenario.yaml`

3. Run simulation:
   ```python
   from main import run_simulation
   run_simulation('scenarios/simulation/my_scenario.yaml')
```

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Kill existing processes
pkill -f "python main.py"
pkill -f "python visualizer/server/http_server.py"
```

### Web Visualization Not Displaying

1. Hard refresh browser: `Ctrl + Shift + R`
2. Check if `simulation_log.jsonl` is generated
3. Check for errors in browser developer tools (F12)

### Dependency Package Errors

```bash
pip install --upgrade -r requirements.txt
```

---

## 📚 Detailed Documentation

- [Web Visualization System Details](visualizer/README.md)
- Architecture Details: See docstrings in each Python file
- API Reference: `docs/api_reference.md` (in preparation)

---

## 🎓 Design Philosophy

### Object-Oriented Design
- **Information Hiding**: Each entity hides its internal state
- **Separation of Concerns**: Passengers press buttons, GCS assigns
- **Avoid Look-ahead Bias**: Don't use future information

### Event-Driven Architecture
- Loose coupling via MessageBroker
- Record all events in JSONL
- Unified Live/Replay processing

### Package Separation Design
- **simulator**: Physical simulation (can run independently)
- **controller**: Group control algorithms (pluggable)
- **analyzer**: Data analysis (can process real elevator logs)
- **visualizer**: Visualization (can run without simulator)

---

## 🏢 Real Building Use Cases

### Pattern 1: Existing Building Operation Analysis

```bash
pip install elvsim-analyzer elvsim-visualizer

# Collect logs from real elevators in JSONL format
python -m analyzer.statistics --input /var/log/elevator/log.jsonl --report monthly_report.pdf

# Visualize
elvsim-viz
```

### Pattern 2: Pre-Simulation for New Building

```bash
pip install elvsim

# Customize main.py according to building specifications
python main.py

# Analyze results
python -m analyzer.statistics --input simulation_log.jsonl
```

---

## 📝 License

MIT License - See [LICENSE](LICENSE) for details

---

## 🚀 Next Steps

1. **Adjust Simulation Parameters**: Edit configuration files in `scenarios/simulation/`
2. **Customize Group Control**: Edit configuration files in `scenarios/group_control/`
3. **Develop Custom Algorithms**: Implement `IAllocationStrategy` or `IRepositioningStrategy` in `controller/algorithms/`
4. **Extend Web UI**: Edit `visualizer/static/`
5. **Connect Real Elevators**: Send data in the same JSONL format
6. **Analyze Performance**: Use Performance Monitor tab in web visualizer

---

## 🤝 Contributing

Pull requests are welcome! See `CONTRIBUTING.md` (in preparation) for details.

---

**Enjoy simulating! 🏢✨**
