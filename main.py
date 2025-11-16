import simpy
import random
import sys

# Configuration
from config import load_group_control_config, load_simulation_config

# Simulator components
from simulator.infrastructure.message_broker import MessageBroker
from simulator.core.elevator import Elevator
from simulator.core.hall_button import HallButton
from simulator.core.passenger import Passenger
from simulator.core.door import Door
from simulator.core.building import Building, FloorDefinition
from simulator.core.floor_queue_manager import FloorQueueManager
from simulator.physics.physics_engine import PhysicsEngine

# Call system and behavior interfaces
from simulator.implementations.traditional.call_system import TraditionalCallSystem
from simulator.implementations.dcs.call_system import FullDCSCallSystem
from simulator.implementations.hybrid.call_system import LobbyDCSCallSystem, ZonedCallSystem
from simulator.interfaces.call_system import ICallSystem
from simulator.implementations.traditional.passenger_behavior import AdaptivePassengerBehavior

# Controller and allocation strategy
from controller.group_control import GroupControlSystem
from controller.algorithms.nearest_car import NearestCarStrategy
from controller.algorithms.test_forced_move import TestForcedMoveStrategy

# Analyzer
from analyzer.simulation_statistics import SimulationStatistics

def run_simulation(sim_config_path="scenarios/simulation/office_morning_rush.yaml",
                   gc_config_path="scenarios/group_control/test_forced_move.yaml"):
    """
    Set up and run the entire simulation
    
    Args:
        sim_config_path: Path to simulation configuration YAML file
        gc_config_path: Path to group control configuration YAML file
    """
    print("--- Loading Configuration ---")
    
    # Load configurations
    sim_config = load_simulation_config(sim_config_path)
    gc_config = load_group_control_config(gc_config_path)
    
    print(f"Simulation Config: {sim_config_path}")
    print(f"Group Control Config: {gc_config_path}")
    
    # Extract configuration values for easier access
    NUM_FLOORS = sim_config.building.num_floors
    FLOOR_HEIGHT = sim_config.building.floor_height
    NUM_ELEVATORS = sim_config.elevator.num_elevators
    MAX_CAPACITY = sim_config.elevator.max_capacity
    MAX_SPEED = sim_config.elevator.rated_speed
    ACCELERATION = sim_config.elevator.acceleration
    JERK = sim_config.elevator.jerk
    FULL_LOAD_BYPASS = sim_config.elevator.full_load_bypass
    HOME_FLOOR = sim_config.elevator.home_floor
    MAIN_DIRECTION = sim_config.elevator.main_direction
    
    DOOR_OPEN_TIME = sim_config.door.open_time
    DOOR_CLOSE_TIME = sim_config.door.close_time
    MAX_REOPENS_PER_STOP = sim_config.door.max_reopens_per_stop if hasattr(sim_config.door, 'max_reopens_per_stop') else None
    
    SIM_DURATION = sim_config.traffic.simulation_duration
    PASSENGER_GENERATION_RATE = sim_config.traffic.passenger_generation_rate
    
    # Set random seed if specified
    if sim_config.random_seed is not None:
        random.seed(sim_config.random_seed)
        print(f"Random seed fixed to {sim_config.random_seed} for reproducible results")
    else:
        print("Random seed not set - results will vary")

    print("\n--- Simulation Setup ---")
    env = simpy.Environment()
    broker = MessageBroker(env)
    broadcast_pipe = broker.get_broadcast_pipe()
    
    # Create statistics collector
    sim_stats = SimulationStatistics(env, broadcast_pipe)
    env.process(sim_stats.start_listening())
    
    # --- Call system configuration ---
    # Create call system based on configuration
    if sim_config.call_system is None or sim_config.call_system.call_system_type == "TRADITIONAL":
        call_system: ICallSystem = TraditionalCallSystem(num_floors=NUM_FLOORS)
        print(f"Using Traditional call system (all floors have UP/DOWN buttons)")
    elif sim_config.call_system.call_system_type == "FULL_DCS":
        call_system = FullDCSCallSystem(num_floors=NUM_FLOORS)
        print(f"Using FULL DCS call system (all floors have destination panels)")
    elif sim_config.call_system.call_system_type == "LOBBY_DCS":
        lobby_floor = sim_config.call_system.lobby_floor or sim_config.building.lobby_floor
        call_system = LobbyDCSCallSystem(num_floors=NUM_FLOORS, lobby_floor=lobby_floor)
        print(f"Using Lobby DCS call system (floor {lobby_floor} has DCS panel, others have UP/DOWN buttons)")
    elif sim_config.call_system.call_system_type == "ZONED_DCS":
        if sim_config.call_system.dcs_floors is None:
            raise ValueError("dcs_floors must be specified for ZONED_DCS")
        call_system = ZonedCallSystem(num_floors=NUM_FLOORS, dcs_floors=sim_config.call_system.dcs_floors)
        print(f"Using Zoned DCS call system (DCS floors: {sim_config.call_system.dcs_floors})")
    else:
        raise ValueError(f"Unknown call system type: {sim_config.call_system.call_system_type}")
    
    passenger_behavior = AdaptivePassengerBehavior()
    
    # --- Create strategies from config ---
    # Allocation strategy
    alloc_strategy_name = gc_config.allocation_strategy.name
    if alloc_strategy_name == "NearestCar":
        allocation_strategy = NearestCarStrategy(num_floors=NUM_FLOORS)
    else:
        raise ValueError(f"Unknown allocation strategy: {alloc_strategy_name}")
    
    # Repositioning strategy
    repos_strategy_name = gc_config.repositioning_strategy.name
    if repos_strategy_name == "TestForcedMove":
        repositioning_strategy = TestForcedMoveStrategy()
    elif repos_strategy_name == "None":
        repositioning_strategy = None
    else:
        raise ValueError(f"Unknown repositioning strategy: {repos_strategy_name}")

    # --- Building floor definitions ---
    # Create Building object from configuration
    if sim_config.building.floors is not None:
        # Use explicit floor definitions from config
        floor_defs = [
            FloorDefinition(
                control_floor=f['control_floor'],
                display_name=f['display_name'],
                floor_height=f.get('floor_height', FLOOR_HEIGHT)
            )
            for f in sim_config.building.floors
        ]
    else:
        # Auto-generate simple floor definitions (1="1F", 2="2F", etc.)
        floor_defs = [
            FloorDefinition(
                control_floor=i,
                display_name=f"{i}F",
                floor_height=FLOOR_HEIGHT
            )
            for i in range(1, NUM_FLOORS + 1)
        ]
    
    building = Building(floor_defs)
    print(f"Building created with {building.num_floors} floors: {building.all_floors}")
    
    # Set simulation metadata for JSON Lines log (after building is created)
    sim_stats.set_simulation_metadata({
        'num_floors': NUM_FLOORS,
        'num_elevators': NUM_ELEVATORS,
        'elevator_capacity': MAX_CAPACITY,
        'full_load_bypass': FULL_LOAD_BYPASS,
        'floor_height': FLOOR_HEIGHT,
        'max_speed': MAX_SPEED,
        'acceleration': ACCELERATION,
        'jerk': JERK,
        'sim_duration': SIM_DURATION,
        'random_seed': sim_config.random_seed,
        'config_files': {
            'simulation': sim_config_path,
            'group_control': gc_config_path
        },
        'building': {
            'floors': [
                {
                    'control_floor': f.control_floor,
                    'display_name': f.display_name,
                    'floor_height': f.floor_height
                }
                for f in building.floors
            ]
        }
    })

    # --- Physics engine preparation ---
    # Use actual floor heights from building definition
    floor_heights = [0]  # Ground level
    for i in range(1, NUM_FLOORS + 1):
        prev_height = floor_heights[-1]
        floor_height = building.get_floor_height(i)
        floor_heights.append(prev_height + floor_height)
    
    physics_engine = PhysicsEngine(floor_heights, MAX_SPEED, ACCELERATION, JERK)
    flight_profiles = physics_engine.precompute_flight_profiles()

    # --- Shared resource creation ---
    # Create FloorQueueManager for unified queue handling
    # Traditional floors: queue[floor][direction]
    # DCS floors: queue[floor][elevator_name]
    floor_queue_manager = FloorQueueManager(env, NUM_FLOORS, NUM_ELEVATORS, call_system)
    
    # Backward compatibility: Create old-style floor_queues structure for existing code
    # This will be gradually replaced with floor_queue_manager
    floor_queues = floor_queue_manager._queues

    # --- Entity creation ---
    gcs = GroupControlSystem("GCS", broker, allocation_strategy, repositioning_strategy)
    
    # Create hall buttons only for Traditional system (not for DCS)
    if call_system.has_physical_buttons():
        hall_buttons = [
            {'UP': HallButton(env, floor, "UP", broker), 
             'DOWN': HallButton(env, floor, "DOWN", broker)}
            for floor in range(NUM_FLOORS + 1)
        ]
    else:
        # DCS system: no physical hall buttons
        hall_buttons = None

    # Create elevators dynamically based on config
    elevators = []
    
    # Check if per-elevator configuration exists
    if hasattr(sim_config.elevator, 'per_elevator') and sim_config.elevator.per_elevator:
        # Use individual elevator configurations
        for elev_config in sim_config.elevator.per_elevator:
            elev_name = elev_config['name']
            elev_service_floors = elev_config.get('service_floors', None)
            elev_home_floor = elev_config.get('home_floor', HOME_FLOOR)
            elev_main_dir = elev_config.get('main_direction', MAIN_DIRECTION)
            
            door = Door(env, f"{elev_name}_Door", open_time=DOOR_OPEN_TIME, close_time=DOOR_CLOSE_TIME, max_reopens_per_stop=MAX_REOPENS_PER_STOP)
            elevator = Elevator(
                env, elev_name, broker, NUM_FLOORS, floor_queues,
                door=door,
                flight_profiles=flight_profiles,
                physics_engine=physics_engine,
                hall_buttons=hall_buttons,
                max_capacity=MAX_CAPACITY,
                full_load_bypass=FULL_LOAD_BYPASS,
                home_floor=elev_home_floor,
                main_direction=elev_main_dir,
                service_floors=elev_service_floors,
                building=building,
                call_system=call_system,
                floor_queue_manager=floor_queue_manager
            )
            gcs.register_elevator(elevator)
            elevators.append(elevator)
            print(f"Created {elev_name} with service floors: {elev_service_floors or 'all'}")
    else:
        # Use uniform configuration for all elevators
        common_service_floors = getattr(sim_config.elevator, 'service_floors', None)
        
        for i in range(1, NUM_ELEVATORS + 1):
            door = Door(env, f"Elevator_{i}_Door")
            elevator = Elevator(
                env, f"Elevator_{i}", broker, NUM_FLOORS, floor_queues,
                door=door,
                flight_profiles=flight_profiles,
                physics_engine=physics_engine,
                hall_buttons=hall_buttons,
                max_capacity=MAX_CAPACITY,
                full_load_bypass=FULL_LOAD_BYPASS,
                home_floor=HOME_FLOOR,
                floor_queue_manager=floor_queue_manager,
                main_direction=MAIN_DIRECTION,
                service_floors=common_service_floors,
                building=building,
                call_system=call_system
            )
            gcs.register_elevator(elevator)
            elevators.append(elevator)
        
        if common_service_floors:
            print(f"All elevators created with service floors: {common_service_floors}")
        else:
            print(f"All elevators created with full floor service")
    
    # Start GCS processes
    env.process(gcs.run())
    for elevator in elevators:
        env.process(gcs.start_status_listener(elevator.name))

    # --- Process startup ---
    # For normal testing
    # env.process(passenger_generator(env, broker, hall_buttons, floor_queues))
    
    # For integrated testing (boarding/alighting on same floor)
    env.process(passenger_generator_integrated_test(
        env, broker, hall_buttons, floor_queues, 
        call_system, passenger_behavior, sim_stats,
        generation_rate=PASSENGER_GENERATION_RATE,
        num_floors=NUM_FLOORS,
        od_matrix=sim_config.traffic.od_matrix,
        elevators=elevators,  # Pass elevators for service floor validation
        move_speed_config=sim_config.traffic.passenger_move_speed,
        floor_queue_manager=floor_queue_manager
    ))

    print("\n--- Simulation Start ---")
    env.run(until=SIM_DURATION)
    print("--- Simulation End ---")
    
    # Save event log (common functionality)
    sim_stats.save_event_log('simulation_log.jsonl')
    
    # Display simulation metrics
    print("\n" + "="*80)
    print("📊 SIMULATION METRICS (God's View - Research/Debug)")
    print("="*80)
    sim_stats.print_passenger_metrics_summary()
    
    # Generate trajectory diagram
    sim_stats.plot_trajectory_diagram()

def passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues, 
                                       call_system, passenger_behavior, statistics,
                                       generation_rate=0.1, num_floors=10, od_matrix=None, elevators=None,
                                       move_speed_config=1.0, floor_queue_manager=None):
    """
    Continuous passenger generation for extended simulation
    
    Args:
        generation_rate: Passengers per second (e.g., 0.1 = 1 passenger every 10 seconds average)
        num_floors: Number of floors in the building
        od_matrix: Origin-Destination matrix (num_floors x num_floors). If None, uses uniform distribution.
        elevators: List of Elevator objects (for service floor validation)
    """
    print(f"--- Continuous Passenger Generation (Rate: {generation_rate} passengers/sec) ---")
    if od_matrix is not None:
        print(f"    Using OD matrix ({len(od_matrix)}x{len(od_matrix[0])}) for traffic pattern")
    else:
        print(f"    Using uniform distribution (no OD matrix)")
    
    passenger_id = 0
    base_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", 
                 "Ivy", "Jack", "Kate", "Leo", "Mary", "Nick", "Olivia", "Paul", "Quinn", 
                 "Rachel", "Steve", "Tina", "Uma", "Victor", "Wendy", "Xavier", "Yuki", "Zack"]
    
    while True:
        # Wait based on generation rate (exponential distribution)
        if generation_rate > 0:
            wait_time = random.expovariate(generation_rate)
        else:
            wait_time = random.uniform(1, 5)  # Fallback
        yield env.timeout(wait_time)
        
        passenger_id += 1
        name = f"{base_names[passenger_id % len(base_names)]}_{passenger_id}"
        
        # Floor selection based on OD matrix or uniform distribution
        if od_matrix is not None and len(od_matrix) == num_floors:
            # Use OD matrix to determine origin and destination
            # 1. Select origin floor based on total outgoing traffic from each floor
            origin_weights = [sum(row) for row in od_matrix]
            arrival_floor = random.choices(range(1, num_floors + 1), weights=origin_weights, k=1)[0]
            
            # 2. Select destination floor based on OD matrix row for the origin floor
            od_row = od_matrix[arrival_floor - 1]  # 0-indexed
            # Exclude same-floor trips (set probability to 0)
            destination_weights = od_row.copy()
            destination_weights[arrival_floor - 1] = 0.0
            
            # Normalize weights
            total_weight = sum(destination_weights)
            if total_weight > 0:
                destination_weights = [w / total_weight for w in destination_weights]
                destination_floor = random.choices(range(1, num_floors + 1), weights=destination_weights, k=1)[0]
            else:
                # Fallback: random destination (excluding origin)
                destination_floor = random.randint(1, num_floors)
                while destination_floor == arrival_floor:
                    destination_floor = random.randint(1, num_floors)
        else:
            # Fallback: Uniform random distribution
            arrival_floor = random.randint(1, num_floors)
            destination_floor = random.randint(1, num_floors)
        while destination_floor == arrival_floor:
                destination_floor = random.randint(1, num_floors)
        
        # Service floor validation: ensure at least one elevator can serve both floors
        if elevators:
            serviceable = any(
                elev.can_serve_floor(arrival_floor) and elev.can_serve_floor(destination_floor)
                for elev in elevators
            )
            if not serviceable:
                # Skip this passenger generation (no elevator can serve this trip)
                print(f"{env.now:.2f} [PassengerGen] Skipped passenger {name}: No elevator can serve {arrival_floor} -> {destination_floor}")
                continue
        
        # Determine move_speed based on configuration
        if isinstance(move_speed_config, dict):
            # Random range
            move_speed = random.uniform(move_speed_config['min'], move_speed_config['max'])
        else:
            # Fixed value
            move_speed = move_speed_config
        
        # Create passenger (using call_system and unique behavior instance)
        # Each passenger needs their own behavior instance to avoid state sharing
        passenger_behavior_instance = AdaptivePassengerBehavior()
        passenger = Passenger(env, name, broker, hall_buttons, floor_queues,
                             call_system=call_system, behavior=passenger_behavior_instance,
                             arrival_floor=arrival_floor, destination_floor=destination_floor, 
                             move_speed=move_speed, floor_queue_manager=floor_queue_manager)
        
        # Register passenger with Statistics for metrics collection
        statistics.register_passenger(passenger)

def passenger_generator(env, broker, hall_buttons, floor_queues):
    """Passenger generation process for real interrupt testing"""
    print("--- Passenger Generation for REAL Interrupt Test ---")

    # Scenario 1: Saburo heads to 10th floor
    yield env.timeout(5)
    Passenger(env, "Saburo", broker, hall_buttons, floor_queues, 
              arrival_floor=2, destination_floor=10, move_speed=1.0)

    # Scenario 2: Interrupt the elevator carrying Saburo at 15 seconds while traveling from 2nd->10th floor!
    yield env.timeout(9)  # 5 seconds + 9 seconds = Shiro appears at 14 seconds -> presses button at 15 seconds
    Passenger(env, "Shiro", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.2)

    # Scenario 3: Goro and Rokuro register calls in opposite direction
    yield env.timeout(3)
    Passenger(env, "Goro", broker, hall_buttons, floor_queues,
              arrival_floor=8, destination_floor=1, move_speed=2.5)
    
    yield env.timeout(3)
    Passenger(env, "Rokuro", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=3, move_speed=0.8)

if __name__ == '__main__':
    # Accept command line arguments for config files
    sim_config_path = sys.argv[1] if len(sys.argv) > 1 else "scenarios/simulation/office_morning_rush.yaml"
    gc_config_path = sys.argv[2] if len(sys.argv) > 2 else "scenarios/group_control/test_forced_move.yaml"
    run_simulation(sim_config_path=sim_config_path, gc_config_path=gc_config_path)

