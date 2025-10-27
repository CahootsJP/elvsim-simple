import simpy

# Simulator components
from simulator.infrastructure.message_broker import MessageBroker
from simulator.core.elevator import Elevator
from simulator.core.hall_button import HallButton
from simulator.core.passenger import Passenger
from simulator.core.door import Door
from simulator.physics.physics_engine import PhysicsEngine

# Controller
from controller.group_control import GroupControlSystem

# Analyzer
from analyzer.statistics import Statistics

def run_simulation():
    """Set up and run the entire simulation"""
    # --- Simulation constants ---
    SIM_DURATION = 600  # Extended from 200 to 600 seconds (10 minutes)
    NUM_FLOORS = 10

    # --- Physical world definition ---
    FLOOR_HEIGHT = 3.5  # Height of each floor (m)
    MAX_SPEED = 2.5     # Maximum speed (m/s)
    ACCELERATION = 1.0  # Acceleration (m/s^2)
    JERK = 2.0  # Jerk (m/s^3)

    print("--- Simulation Setup ---")
    env = simpy.Environment()
    broker = MessageBroker(env)
    broadcast_pipe = broker.get_broadcast_pipe()
    statistics = Statistics(env, broadcast_pipe)
    env.process(statistics.start_listening())
    
    # Set simulation metadata for JSON Lines log
    import random
    random.seed(42)
    print("Random seed fixed to 42 for reproducible results")
    
    statistics.set_simulation_metadata({
        'num_floors': NUM_FLOORS,
        'num_elevators': 3,
        'elevator_capacity': 10,
        'floor_height': FLOOR_HEIGHT,
        'max_speed': MAX_SPEED,
        'acceleration': ACCELERATION,
        'jerk': JERK,
        'sim_duration': SIM_DURATION,
        'random_seed': 42
    })

    # --- Physics engine preparation ---
    floor_heights = [0] + [i * FLOOR_HEIGHT for i in range(1, NUM_FLOORS + 1)]
    physics_engine = PhysicsEngine(floor_heights, MAX_SPEED, ACCELERATION, JERK)
    
    # Use practical table method by default
    flight_profiles = physics_engine.precompute_flight_profiles()

    # --- Shared resource creation ---
    floor_queues = [
        {"UP": simpy.Store(env), "DOWN": simpy.Store(env)}
        for _ in range(NUM_FLOORS + 1)
    ]

    # --- Entity creation ---
    gcs = GroupControlSystem(env, "GCS", broker)
    
    hall_buttons = [
        {'UP': HallButton(env, floor, "UP", broker), 
         'DOWN': HallButton(env, floor, "DOWN", broker)}
        for floor in range(NUM_FLOORS + 1)
    ]

    # Create Elevator 1
    door1 = Door(env, "Elevator_1_Door")
    elevator1 = Elevator(env, "Elevator_1", broker, NUM_FLOORS, floor_queues, door=door1, flight_profiles=flight_profiles, physics_engine=physics_engine, hall_buttons=hall_buttons, max_capacity=10)
    gcs.register_elevator(elevator1)
    
    # Create Elevator 2
    door2 = Door(env, "Elevator_2_Door")
    elevator2 = Elevator(env, "Elevator_2", broker, NUM_FLOORS, floor_queues, door=door2, flight_profiles=flight_profiles, physics_engine=physics_engine, hall_buttons=hall_buttons, max_capacity=10)
    gcs.register_elevator(elevator2)
    
    # Create Elevator 3
    door3 = Door(env, "Elevator_3_Door")
    elevator3 = Elevator(env, "Elevator_3", broker, NUM_FLOORS, floor_queues, door=door3, flight_profiles=flight_profiles, physics_engine=physics_engine, hall_buttons=hall_buttons, max_capacity=10)
    gcs.register_elevator(elevator3)

    # --- Process startup ---
    # For normal testing
    # env.process(passenger_generator(env, broker, hall_buttons, floor_queues))
    
    # For integrated testing (boarding/alighting on same floor)
    env.process(passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues))

    print("\n--- Simulation Start ---")
    env.run(until=SIM_DURATION)
    print("--- Simulation End ---")
    
    # Save event log
    statistics.save_event_log('simulation_log.jsonl')
    
    # Generate trajectory diagram
    statistics.plot_trajectory_diagram()

def passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues):
    """Continuous passenger generation for extended simulation"""
    import random
    
    print("--- Continuous Passenger Generation (Extended) ---")
    
    passenger_id = 0
    base_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", 
                 "Ivy", "Jack", "Kate", "Leo", "Mary", "Nick", "Olivia", "Paul", "Quinn", 
                 "Rachel", "Steve", "Tina", "Uma", "Victor", "Wendy", "Xavier", "Yuki", "Zack"]
    
    while True:
        # Wait random interval between passengers (1-5 seconds) - high frequency
        yield env.timeout(random.uniform(1, 5))
        
        passenger_id += 1
        name = f"{base_names[passenger_id % len(base_names)]}_{passenger_id}"
        
        # Random floor selection
        arrival_floor = random.randint(1, 10)
        destination_floor = random.randint(1, 10)
        while destination_floor == arrival_floor:
            destination_floor = random.randint(1, 10)
        
        move_speed = random.uniform(0.8, 1.5)
        
        # Create passenger
        Passenger(env, name, broker, hall_buttons, floor_queues, 
                 arrival_floor=arrival_floor, destination_floor=destination_floor, 
                 move_speed=move_speed)

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
    run_simulation()

