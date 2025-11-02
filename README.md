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

### Group Control System (`controller/`)
- [x] Multi-elevator Group Control
- [x] Nearest Car Strategy (Circular Distance-based)
- [x] Real-time Status Monitoring
- [x] Dynamic Hall Call Assignment
- [x] Pluggable Algorithm Design

### Data Analysis (`analyzer/`)
- [x] JSON Lines Format Logging
- [x] Event-Level Detailed Recording
- [x] Trajectory Diagram Generation (Matplotlib)
- [x] Real Elevator Log Analysis Support

### Web Visualization (`visualizer/`)
- [x] Live Mode (Real-time Display)
- [x] Replay Mode (Playback Controls with speed adjustment)
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
python main.py
```

This will:
- ✅ Simulate 3 elevators with 10 floors
- ✅ Run for 600 seconds (10 minutes)
- ✅ Save logs to `simulation_log.jsonl`
- ✅ Generate trajectory diagram

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

- **Live**: Observe in real-time
- **Replay**: Replay after execution (with speed control and seeking)
- **Dark Mode**: Toggle theme with button

For details, see [`visualizer/README.md`](visualizer/README.md).

---

## 📁 Project Structure

```
elvsim-simple/
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
- ✅ Pluggable algorithm design

### Data Collection & Analysis (`analyzer/`)
- ✅ JSON Lines format logs (`simulation_log.jsonl`)
- ✅ Automatic trajectory diagram generation (Matplotlib)
- ✅ Detailed event-level recording
- ✅ Real elevator log analysis capability

### Web Visualization (`visualizer/`)
- ✅ Unified Live/Replay viewer
- ✅ Multi-elevator display (scalable)
- ✅ Elevator hall panel (waiting passenger display)
- ✅ Color-coded by elevator
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

## 📊 Simulation Parameters (`main.py`)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `SIM_DURATION` | 600s | Simulation time |
| `NUM_FLOORS` | 10 | Number of floors |
| `NUM_ELEVATORS` | 3 | Number of elevators |
| `FLOOR_HEIGHT` | 3.5m | Floor height |
| `MAX_SPEED` | 2.5m/s | Maximum speed |
| `ACCELERATION` | 1.0m/s² | Acceleration |
| `JERK` | 2.0m/s³ | Jerk |
| `CAPACITY` | 10 people | Capacity |

---

## 🔧 Customization

### Change Number of Elevators

Edit the following section in `main.py`:

```python
# Create elevators
for i in range(1, 4):  # 3 elevators → change to any number
    door = Door(env, f"Elevator_{i}_Door")
    elevator = Elevator(env, f"Elevator_{i}", broker, NUM_FLOORS, ...)
    gcs.register_elevator(elevator)
```

### Change Passenger Generation Pattern

Edit the `passenger_generator_integrated_test()` function in `main.py`:

```python
def passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues):
    # Customize passenger generation logic here
    yield env.timeout(random.uniform(1, 5))  # Generation interval
    arrival_floor = random.randint(1, 10)    # Origin floor
    destination_floor = random.randint(1, 10) # Destination floor
    ...
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

1. **Adjust Simulation Parameters**: Edit `main.py`
2. **Improve Group Control Algorithms**: Edit `controller/group_control.py`
3. **Extend Web UI**: Edit `visualizer/static/`
4. **Connect Real Elevators**: Send data in the same JSONL format
5. **Develop Custom Algorithms**: Add to `controller/algorithms/`

---

## 🤝 Contributing

Pull requests are welcome! See `CONTRIBUTING.md` (in preparation) for details.

---

**Enjoy simulating! 🏢✨**
