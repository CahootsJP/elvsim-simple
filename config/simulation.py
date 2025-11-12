"""
Simulation Configuration

This configuration is used only in simulation environment.
Contains physical specifications and traffic patterns.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class BuildingConfig:
    """Building specifications"""
    num_floors: int = 10
    floor_height: float = 3.5  # meters
    lobby_floor: int = 1
    floors: Optional[List[Dict[str, Any]]] = None  # Floor definitions (control_floor, display_name, floor_height)
    
    def __post_init__(self):
        if self.num_floors < 2:
            raise ValueError("num_floors must be at least 2")
        if self.floor_height <= 0:
            raise ValueError("floor_height must be positive")
        if not (1 <= self.lobby_floor <= self.num_floors):
            raise ValueError(f"lobby_floor must be between 1 and {self.num_floors}")
        
        # Validate floors if provided
        if self.floors is not None:
            if len(self.floors) != self.num_floors:
                raise ValueError(f"floors list length ({len(self.floors)}) must match num_floors ({self.num_floors})")


@dataclass
class ElevatorConfig:
    """Elevator specifications"""
    num_elevators: int = 4
    max_capacity: int = 10  # persons
    rated_speed: float = 2.5  # m/s
    acceleration: float = 1.0  # m/s²
    jerk: float = 2.0  # m/s³
    full_load_bypass: bool = True
    home_floor: int = 1
    main_direction: str = "UP"
    service_floors: Optional[List[int]] = None  # Service floors (None = all floors)
    per_elevator: Optional[List[Dict[str, Any]]] = None  # Per-elevator configuration
    
    def __post_init__(self):
        if self.num_elevators < 1:
            raise ValueError("num_elevators must be at least 1")
        if self.max_capacity < 1:
            raise ValueError("max_capacity must be at least 1")
        if self.rated_speed <= 0:
            raise ValueError("rated_speed must be positive")
        if self.acceleration <= 0:
            raise ValueError("acceleration must be positive")
        if self.jerk <= 0:
            raise ValueError("jerk must be positive")
        if self.main_direction not in ["UP", "DOWN"]:
            raise ValueError("main_direction must be 'UP' or 'DOWN'")
        
        # Validate per_elevator if provided
        if self.per_elevator is not None:
            if len(self.per_elevator) != self.num_elevators:
                raise ValueError(f"per_elevator list length ({len(self.per_elevator)}) must match num_elevators ({self.num_elevators})")


@dataclass
class DoorConfig:
    """Door specifications"""
    open_time: float = 2.0  # seconds
    close_time: float = 2.0  # seconds
    reopen_delay: float = 0.5  # seconds
    
    def __post_init__(self):
        if self.open_time <= 0:
            raise ValueError("open_time must be positive")
        if self.close_time <= 0:
            raise ValueError("close_time must be positive")
        if self.reopen_delay < 0:
            raise ValueError("reopen_delay cannot be negative")


@dataclass
class TrafficConfig:
    """Traffic pattern configuration"""
    pattern: str = "uniform"  # uniform, morning_rush, lunch, evening, custom
    simulation_duration: float = 300.0  # seconds
    passenger_generation_rate: float = 0.1  # passengers per second
    od_matrix: Optional[List[List[float]]] = None  # Origin-Destination matrix
    
    # Passenger behavior
    avg_boarding_time: float = 1.0  # seconds per passenger
    avg_alighting_time: float = 0.8  # seconds per passenger
    
    def __post_init__(self):
        if self.simulation_duration <= 0:
            raise ValueError("simulation_duration must be positive")
        if self.passenger_generation_rate < 0:
            raise ValueError("passenger_generation_rate cannot be negative")
        if self.avg_boarding_time <= 0:
            raise ValueError("avg_boarding_time must be positive")
        if self.avg_alighting_time <= 0:
            raise ValueError("avg_alighting_time must be positive")
        
        # Validate OD matrix if provided
        if self.od_matrix is not None:
            if not all(isinstance(row, list) for row in self.od_matrix):
                raise ValueError("od_matrix must be a list of lists")
            if len(self.od_matrix) != len(self.od_matrix[0]):
                raise ValueError("od_matrix must be square")


@dataclass
class SimulationConfig:
    """
    Complete simulation configuration
    
    This configuration is used only in simulation environment.
    Combines building, elevator, door, and traffic settings.
    """
    building: BuildingConfig
    elevator: ElevatorConfig
    door: DoorConfig
    traffic: TrafficConfig
    
    # Simulation control
    random_seed: Optional[int] = None
    realtime_factor: float = 1.0  # 1.0 = realtime, 0.0 = as fast as possible
    
    def __post_init__(self):
        if self.realtime_factor < 0:
            raise ValueError("realtime_factor cannot be negative")
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SimulationConfig':
        """Create SimulationConfig from dictionary"""
        sim_data = data.get('simulation', data)
        
        # Parse building config
        building_data = sim_data.get('building', {})
        building = BuildingConfig(
            num_floors=building_data.get('num_floors', 10),
            floor_height=building_data.get('floor_height', 3.5),
            lobby_floor=building_data.get('lobby_floor', 1),
            floors=building_data.get('floors')
        )
        
        # Parse elevator config
        elevator_data = sim_data.get('elevator', {})
        elevator = ElevatorConfig(
            num_elevators=elevator_data.get('num_elevators', 4),
            max_capacity=elevator_data.get('max_capacity', 10),
            rated_speed=elevator_data.get('rated_speed', 2.5),
            acceleration=elevator_data.get('acceleration', 1.0),
            jerk=elevator_data.get('jerk', 2.0),
            full_load_bypass=elevator_data.get('full_load_bypass', True),
            home_floor=elevator_data.get('home_floor', 1),
            main_direction=elevator_data.get('main_direction', 'UP'),
            service_floors=elevator_data.get('service_floors'),
            per_elevator=elevator_data.get('per_elevator')
        )
        
        # Parse door config
        door_data = sim_data.get('door', {})
        door = DoorConfig(
            open_time=door_data.get('open_time', 2.0),
            close_time=door_data.get('close_time', 2.0),
            reopen_delay=door_data.get('reopen_delay', 0.5)
        )
        
        # Parse traffic config
        traffic_data = sim_data.get('traffic', {})
        traffic = TrafficConfig(
            pattern=traffic_data.get('pattern', 'uniform'),
            simulation_duration=traffic_data.get('simulation_duration', 300.0),
            passenger_generation_rate=traffic_data.get('passenger_generation_rate', 0.1),
            od_matrix=traffic_data.get('od_matrix'),
            avg_boarding_time=traffic_data.get('avg_boarding_time', 1.0),
            avg_alighting_time=traffic_data.get('avg_alighting_time', 0.8)
        )
        
        return cls(
            building=building,
            elevator=elevator,
            door=door,
            traffic=traffic,
            random_seed=sim_data.get('random_seed'),
            realtime_factor=sim_data.get('realtime_factor', 1.0)
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        result = {
            'simulation': {
                'building': {
                    'num_floors': self.building.num_floors,
                    'floor_height': self.building.floor_height,
                    'lobby_floor': self.building.lobby_floor
                },
                'elevator': {
                    'num_elevators': self.elevator.num_elevators,
                    'max_capacity': self.elevator.max_capacity,
                    'rated_speed': self.elevator.rated_speed,
                    'acceleration': self.elevator.acceleration,
                    'jerk': self.elevator.jerk,
                    'full_load_bypass': self.elevator.full_load_bypass,
                    'home_floor': self.elevator.home_floor,
                    'main_direction': self.elevator.main_direction
                },
                'door': {
                    'open_time': self.door.open_time,
                    'close_time': self.door.close_time,
                    'reopen_delay': self.door.reopen_delay
                },
                'traffic': {
                    'pattern': self.traffic.pattern,
                    'simulation_duration': self.traffic.simulation_duration,
                    'passenger_generation_rate': self.traffic.passenger_generation_rate,
                    'od_matrix': self.traffic.od_matrix,
                    'avg_boarding_time': self.traffic.avg_boarding_time,
                    'avg_alighting_time': self.traffic.avg_alighting_time
                },
                'realtime_factor': self.realtime_factor
            }
        }
        
        if self.random_seed is not None:
            result['simulation']['random_seed'] = self.random_seed
        
        return result
    
    def validate(self):
        """Validate configuration consistency"""
        # Cross-validation between configs
        if self.elevator.home_floor > self.building.num_floors:
            raise ValueError(f"elevator.home_floor ({self.elevator.home_floor}) cannot exceed building.num_floors ({self.building.num_floors})")
        
        # OD matrix size should match num_floors
        if self.traffic.od_matrix is not None:
            if len(self.traffic.od_matrix) != self.building.num_floors:
                raise ValueError(f"od_matrix size ({len(self.traffic.od_matrix)}) must match num_floors ({self.building.num_floors})")

