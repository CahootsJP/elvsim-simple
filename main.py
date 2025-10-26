import simpy
from MessageBroker import MessageBroker
from GroupControlSystem import GroupControlSystem
from Elevator import Elevator
from HallButton import HallButton
from Passenger import Passenger
from Door import Door
from PhysicsEngine import PhysicsEngine
from Statistics import Statistics

def run_simulation():
    """Set up and run the entire simulation"""
    # --- Simulation constants ---
    SIM_DURATION = 200
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
    statistics.set_simulation_metadata({
        'num_floors': NUM_FLOORS,
        'num_elevators': 2,
        'elevator_capacity': 10,
        'floor_height': FLOOR_HEIGHT,
        'max_speed': MAX_SPEED,
        'acceleration': ACCELERATION,
        'jerk': JERK,
        'sim_duration': SIM_DURATION
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
    """Passenger generation process for integrated boarding/alighting test on same floor"""
    print("--- Passenger Generation for INTEGRATED Boarding & Exit Test ---")

    # === Test Case 1: 3 people board from 3rd floor → 3 people alight at 8th floor ===
    yield env.timeout(5)
    Passenger(env, "Alice", broker, hall_buttons, floor_queues, 
              arrival_floor=3, destination_floor=8, move_speed=1.0)
    
    yield env.timeout(1)  # Arrive at same floor 1 second later
    Passenger(env, "Bob", broker, hall_buttons, floor_queues,
              arrival_floor=3, destination_floor=8, move_speed=1.2)
    
    yield env.timeout(2)  # Arrive at same floor 2 seconds later
    Passenger(env, "Charlie", broker, hall_buttons, floor_queues,
              arrival_floor=3, destination_floor=8, move_speed=0.8)

    # === Test Case 2: 2 people board from 6th floor → 2 people alight at 9th floor ===
    yield env.timeout(8)
    Passenger(env, "Diana", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.5)
    
    yield env.timeout(1.5)  # Arrive at same floor 1.5 seconds later
    Passenger(env, "Eve", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.3)

    # === Test Case 3: Complex case - 4 people board from 5th floor → 4 people alight at 2nd floor ===
    yield env.timeout(10)
    Passenger(env, "Frank", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=2, move_speed=1.1)
    
    yield env.timeout(0.5)
    Passenger(env, "Grace", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=2, move_speed=1.4)
    
    yield env.timeout(1)
    Passenger(env, "Henry", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=2, move_speed=1.0)
    
    yield env.timeout(1.5)
    Passenger(env, "Ivy", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=2, move_speed=0.9)

    # === Test Case 4: Mixed case - board from different floors → alight at same floor ===
    yield env.timeout(15)
    Passenger(env, "Jack", broker, hall_buttons, floor_queues,
              arrival_floor=1, destination_floor=7, move_speed=1.2)
    
    yield env.timeout(2)
    Passenger(env, "Kate", broker, hall_buttons, floor_queues,
              arrival_floor=4, destination_floor=7, move_speed=1.0)
    
    yield env.timeout(1)
    Passenger(env, "Leo", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=7, move_speed=1.3)

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

