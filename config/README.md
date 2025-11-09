# Configuration System

Configuration management system for elevator simulation.

## Overview

Configuration is separated into two categories:

### 📦 GroupControlConfig (Real System Compatible)

Control logic settings for the group control system. Can be shared between simulation and real elevator systems.

- **allocation_strategy**: Call allocation strategy
- **repositioning_strategy**: Elevator repositioning strategy
- **reassignment_policy**: Call reassignment policy

### 📦 SimulationConfig (Simulator Only)

Physical specifications and traffic patterns for simulation environment.

- **BuildingConfig**: Building specifications (floors, floor height, etc.)
- **ElevatorConfig**: Elevator specifications (number, capacity, speed, etc.)
- **DoorConfig**: Door specifications (open/close time, etc.)
- **TrafficConfig**: Traffic patterns (passenger generation rate, OD matrix, etc.)

## File Structure

```
scenarios/
├── group_control/                # Group control settings (real-system compatible)
│   ├── nearest_car.yaml         # Nearest car strategy
│   └── test_forced_move.yaml   # Test: Forced move command
│
└── simulation/                   # Simulation settings
    ├── default.yaml             # Default settings
    ├── office_morning_rush.yaml # Office: Morning upward peak
    └── test_short.yaml          # Short test (10 seconds)
```

## Usage

### Python API

```python
from config import load_group_control_config, load_simulation_config

# Load configuration files
gc_config = load_group_control_config('scenarios/group_control/nearest_car.yaml')
sim_config = load_simulation_config('scenarios/simulation/default.yaml')

# Access configuration values
num_floors = sim_config.building.num_floors
strategy_name = gc_config.allocation_strategy.name
```

### Using in main.py

```python
from main import run_simulation

# Run with default configuration
run_simulation()

# Run with custom configuration
run_simulation(
    sim_config_path='scenarios/simulation/office_morning_rush.yaml',
    gc_config_path='scenarios/group_control/nearest_car.yaml'
)
```

## Configuration Examples

### Group Control Config

```yaml
group_control:
  allocation_strategy:
    name: "NearestCar"
    parameters: {}
  
  repositioning_strategy:
    name: "TestForcedMove"
    parameters: {}
  
  reassignment_policy:
    enabled: false
    name: "EarliestArrival"
    parameters: {}
```

### Simulation Config

```yaml
simulation:
  building:
    num_floors: 10
    floor_height: 3.5
    lobby_floor: 1
  
  elevator:
    num_elevators: 4
    max_capacity: 10
    rated_speed: 2.5
    acceleration: 1.0
    jerk: 2.0
    full_load_bypass: true
    home_floor: 1
    main_direction: "UP"
  
  door:
    open_time: 2.0
    close_time: 2.0
    reopen_delay: 0.5
  
  traffic:
    pattern: "uniform"
    simulation_duration: 300.0
    passenger_generation_rate: 0.1
    od_matrix: null
    avg_boarding_time: 1.0
    avg_alighting_time: 0.8
  
  random_seed: 42
  realtime_factor: 0.0
```

## Extension Guide

### Adding a New Strategy

1. **Implement strategy class** (e.g., `controller/algorithms/my_strategy.py`)
2. **Add import and conditional branch to main.py**
3. **Specify strategy name in configuration file**

```yaml
group_control:
  allocation_strategy:
    name: "MyNewStrategy"
    parameters:
      threshold: 10
      weight: 0.5
```

### Adding New Configuration Items

1. **Add item to dataclass** (`config/simulation.py` or `config/group_control.py`)
2. **Update `from_dict()` and `to_dict()` methods**
3. **Add validation logic** (if needed)

## Validation

Validation is automatically performed when loading configuration files:

```python
# Error example: num_floors less than 2
building:
  num_floors: 1  # ValueError: num_floors must be at least 2

# Error example: negative speed value
elevator:
  rated_speed: -1.0  # ValueError: rated_speed must be positive
```

## Dependencies

- **PyYAML**: Reading and writing YAML files

```bash
pip install pyyaml
```

## Design Philosophy

1. **Separation of Concerns**: Clear separation between real-system settings and simulator-only settings
2. **YAGNI Principle**: Implement only currently needed settings, future extensions are easy
3. **Type Safety**: Type checking via dataclass, IDE completion support
4. **Reproducibility**: Complete recording of experimental conditions via configuration files
5. **Shareable**: Share configuration files among researchers to reproduce scenarios
