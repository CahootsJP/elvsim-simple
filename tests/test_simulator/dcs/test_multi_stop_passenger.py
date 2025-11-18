"""
Multi-Stop Passenger Test Script

Tests passenger with multiple journeys:
- Journey 1: DCS floor -> Traditional floor (using DCS)
- Journey 2: Traditional floor -> DCS floor (using traditional UP/DOWN)
- Journey 3: DCS floor -> DCS floor (using DCS)

This demonstrates that a single passenger can use both DCS and traditional systems
in a hybrid DCS building.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import simpy
from simulator.infrastructure.message_broker import MessageBroker
from simulator.core.elevator import Elevator
from simulator.core.hall_button import HallButton
from simulator.core.passenger import Passenger
from simulator.core.door import Door
from simulator.core.building import Building, FloorDefinition
from simulator.physics.physics_engine import PhysicsEngine
from simulator.implementations.hybrid.call_system import LobbyDCSCallSystem
from simulator.implementations.traditional.passenger_behavior import AdaptivePassengerBehavior
from group_control.system import GroupControlSystem
from group_control.algorithms.nearest_car import NearestCarStrategy

def test_multi_stop_passenger():
    """Test passenger with multiple journeys using both DCS and traditional systems"""
    print("=== Multi-Stop Passenger Test ===\n")
    
    # Setup
    env = simpy.Environment()
    broker = MessageBroker(env)
    
    NUM_FLOORS = 10
    NUM_ELEVATORS = 2
    
    # Create call system (Lobby DCS - floor 1 is DCS, others are traditional)
    call_system = LobbyDCSCallSystem(num_floors=NUM_FLOORS, lobby_floor=1)
    passenger_behavior = AdaptivePassengerBehavior()
    
    # Create building
    floor_defs = [
        FloorDefinition(control_floor=i, display_name=f"{i}F", floor_height=3.5)
        for i in range(1, NUM_FLOORS + 1)
    ]
    building = Building(floor_defs)
    
    # Create hall buttons and floor queues
    hall_buttons = [None]
    floor_queues = [None]
    for floor in range(1, NUM_FLOORS + 1):
        hall_buttons.append({
            "UP": HallButton(env, floor, "UP", broker),
            "DOWN": HallButton(env, floor, "DOWN", broker)
        })
        floor_queues.append({
            "UP": simpy.Store(env),
            "DOWN": simpy.Store(env)
        })
    
    # Create elevators
    elevators = []
    floor_heights = [0]
    for i in range(1, NUM_FLOORS + 1):
        prev_height = floor_heights[-1]
        floor_height = building.get_floor_height(i)
        floor_heights.append(prev_height + floor_height)
    
    physics_engine = PhysicsEngine(floor_heights, 2.5, 1.0, 2.0)
    flight_profiles = physics_engine.precompute_flight_profiles()
    
    for i in range(1, NUM_ELEVATORS + 1):
        door = Door(env, f"Elevator_{i}_Door", open_time=2.0, close_time=2.0, 
                    broker=broker, elevator_name=f"Elevator_{i}")
        elevator = Elevator(
            env, f"Elevator_{i}", broker, NUM_FLOORS, floor_queues, door,
            flight_profiles, physics_engine, hall_buttons,
            max_capacity=10, full_load_bypass=True, home_floor=1, 
            main_direction="UP", building=building, call_system=call_system
        )
        door.set_broker_and_elevator(broker, f"Elevator_{i}", elevator)
        elevators.append(elevator)
        env.process(elevator.run())
        env.process(door.run())
    
    # Create GCS
    allocation_strategy = NearestCarStrategy(num_floors=NUM_FLOORS)
    gcs = GroupControlSystem("GCS", broker, allocation_strategy)
    
    for elevator in elevators:
        gcs.register_elevator(elevator)
        env.process(gcs.start_status_listener(elevator.name))
    
    env.process(gcs.run())
    
    # Create test passenger with multiple journeys
    def passenger_generator():
        yield env.timeout(5.0)
        
        # Multi-stop passenger:
        # Journey 1: 1F (DCS) -> 5F (Traditional) - uses DCS
        # Journey 2: 5F (Traditional) -> 1F (DCS) - uses traditional UP/DOWN
        # Journey 3: 1F (DCS) -> 7F (Traditional) - uses DCS
        journeys = [
            {'arrival_floor': 1, 'destination_floor': 5},  # DCS -> Traditional
            {'arrival_floor': 5, 'destination_floor': 1},  # Traditional -> DCS
            {'arrival_floor': 1, 'destination_floor': 7}  # DCS -> Traditional
        ]
        
        passenger = Passenger(
            env, "MultiStopPassenger", broker, hall_buttons, floor_queues,
            call_system=call_system, behavior=passenger_behavior,
            move_speed=1.0, journeys=journeys
        )
        print(f"{env.now:.2f} [Test] Created multi-stop passenger with {len(journeys)} journeys\n")
    
    env.process(passenger_generator())
    
    print("Starting simulation...\n")
    env.run(until=120.0)
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_multi_stop_passenger()

