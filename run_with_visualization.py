#!/usr/bin/env python3
"""
Launcher script to run simulation with real-time visualization
Runs both WebSocket server and SimPy simulation together
"""
import asyncio
import threading
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from visualizer.server import VisualizerServer

def run_websocket_server(server):
    """Run WebSocket server in asyncio event loop"""
    asyncio.run(server.start())

def run_simulation(server):
    """Run SimPy simulation with WebSocket integration"""
    import simpy
    from MessageBroker import MessageBroker
    from Statistics import Statistics
    from Elevator import Elevator
    from Door import Door
    from HallButton import HallButton
    from Passenger import Passenger
    from PhysicsEngine import PhysicsEngine
    from GroupControlSystem import GroupControlSystem
    
    print("Initializing simulation...")
    
    # Create simulation environment
    env = simpy.Environment()
    broker = MessageBroker(env)
    
    # Initialize Statistics with WebSocket server reference
    stats = Statistics(env, broker.broadcast_pipe, websocket_server=server)
    env.process(stats.start_listening())
    
    # Simulation parameters
    NUM_FLOORS = 10
    
    # Create floor queues
    floor_queues = {
        floor: {"UP": simpy.Store(env), "DOWN": simpy.Store(env)}
        for floor in range(1, NUM_FLOORS + 1)
    }
    
    # Create hall buttons
    hall_buttons = {floor: {} for floor in range(1, NUM_FLOORS + 1)}
    for floor in range(1, NUM_FLOORS + 1):
        if floor < NUM_FLOORS:
            hall_buttons[floor]["UP"] = HallButton(env, floor, "UP", broker)
        if floor > 1:
            hall_buttons[floor]["DOWN"] = HallButton(env, floor, "DOWN", broker)
    
    # Create Group Control System
    gcs = GroupControlSystem(env, "GCS", broker)
    
    # Create physics engine
    floor_heights = [0] + [3.5 * i for i in range(NUM_FLOORS)]  # 0, 3.5, 7.0, 10.5, ...
    physics_engine = PhysicsEngine(
        floor_heights=floor_heights,
        max_speed=3.0,
        acceleration=1.0,
        jerk=1.5
    )
    physics_engine.precompute_flight_profiles()
    
    # Create elevator
    door_1 = Door(env, "Door_1", open_time=1.5, close_time=1.5)
    
    flight_profiles_elevator_1 = {
        (1, 2): {'accel_time': 1.0, 'max_speed': 1.0, 'decel_time': 1.0},
        (2, 3): {'accel_time': 1.0, 'max_speed': 1.0, 'decel_time': 1.0},
        (3, 4): {'accel_time': 1.5, 'max_speed': 1.5, 'decel_time': 1.5},
        (1, 3): {'accel_time': 1.5, 'max_speed': 2.0, 'decel_time': 1.5},
        (1, 4): {'accel_time': 2.0, 'max_speed': 2.5, 'decel_time': 2.0},
        (2, 4): {'accel_time': 1.5, 'max_speed': 2.0, 'decel_time': 1.5},
    }
    
    elevator_1 = Elevator(
        env, 
        "Elevator_1", 
        broker, 
        NUM_FLOORS, 
        floor_queues, 
        door_1, 
        flight_profiles_elevator_1,
        physics_engine=physics_engine,
        hall_buttons=hall_buttons,
        max_capacity=50  # Increased capacity to prevent deadlock
    )
    
    # Register elevator with Group Control System
    gcs.register_elevator(elevator_1)
    
    # Note: elevator_1.run() is already started automatically by Entity.__init__
    
    # Create passengers (with delayed start via process)
    def create_passenger_delayed(env, name, arrival_floor, destination_floor, delay, floor_queues, hall_buttons, broker, move_speed=0.5):
        """Create passenger after delay"""
        yield env.timeout(delay)
        # Note: passenger.run() is already started automatically by Entity.__init__
        passenger = Passenger(env, name, broker, hall_buttons, floor_queues, arrival_floor, destination_floor, move_speed)
    
    # Continuous passenger generator for extended simulation
    import random
    
    def continuous_passenger_generator(env, floor_queues, hall_buttons, broker):
        """Generate passengers continuously throughout the simulation"""
        passenger_id = 0
        base_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Henry", 
                     "Ivy", "Jack", "Kate", "Leo", "Mary", "Nick", "Olivia", "Paul"]
        
        while True:
            # Wait random interval between passengers (20-40 seconds)
            yield env.timeout(random.uniform(20, 40))
            
            passenger_id += 1
            name = f"{base_names[passenger_id % len(base_names)]}_{passenger_id}"
            
            # Random floors
            arrival_floor = random.randint(1, NUM_FLOORS)
            destination_floor = random.randint(1, NUM_FLOORS)
            while destination_floor == arrival_floor:
                destination_floor = random.randint(1, NUM_FLOORS)
            
            # Create passenger immediately (no additional delay)
            # Note: passenger.run() is already started automatically by Entity.__init__
            passenger = Passenger(env, name, broker, hall_buttons, floor_queues, arrival_floor, destination_floor, 0.5)
    
    # Start continuous passenger generation
    env.process(continuous_passenger_generator(env, floor_queues, hall_buttons, broker))
    
    print("Starting simulation...")
    print("Open http://localhost:8080/static/index.html in your browser to view visualization")
    print("\n⏰ Simulation will run indefinitely (press Ctrl+C to stop)")
    print("=" * 60 + "\n")
    
    # Run simulation indefinitely (until user stops it)
    try:
        env.run()  # Run forever
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point"""
    print("=" * 60)
    print("Elevator Simulator - Real-time Visualization")
    print("=" * 60)
    
    # Create WebSocket server
    server = VisualizerServer(host='localhost', port=8765)
    
    # Start WebSocket server in separate thread
    ws_thread = threading.Thread(target=run_websocket_server, args=(server,), daemon=True)
    ws_thread.start()
    
    # Wait a moment for WebSocket server to start
    import time
    time.sleep(1)
    
    print("\nWebSocket server started on ws://localhost:8765")
    print("Starting simulation in main thread...")
    print("\nTo view visualization:")
    print("  1. Open visualizer/static/index.html in your browser")
    print("  2. Or run: python -m http.server 8080 --directory visualizer")
    print("     Then open: http://localhost:8080/static/index.html")
    print("\n" + "=" * 60 + "\n")
    
    try:
        # Run simulation in main thread
        run_simulation(server)
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\n\nError during simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "=" * 60)
        print("Shutting down WebSocket server...")
        print("=" * 60)
        # WebSocket server thread is daemon, so it will automatically stop
        import sys
        sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Program interrupted by user (Ctrl+C). Exiting...")
        import sys
        sys.exit(0)

