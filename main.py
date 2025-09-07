import simpy
from MessageBroker import MessageBroker
from GroupControlSystem import GroupControlSystem
from Elevator import Elevator
from HallButton import HallButton
from Passenger import Passenger
from Door import Door
from PhysicsEngine import PhysicsEngine # 物理エンジンをインポート

def run_simulation():
    """シミュレーション全体をセットアップして実行する"""
    # --- シミュレーション定数 ---
    SIM_DURATION = 200
    NUM_FLOORS = 10

    # --- 物理世界の定義 ---
    FLOOR_HEIGHT = 3.5  # 各階の高さ (m)
    MAX_SPEED = 2.5     # 最高速度 (m/s)
    ACCELERATION = 1.0  # 加速度 (m/s^2)

    print("--- Simulation Setup ---")
    env = simpy.Environment()
    broker = MessageBroker(env)

    # --- 物理エンジンの準備 ---
    floor_heights = [0] + [i * FLOOR_HEIGHT for i in range(1, NUM_FLOORS + 1)]
    physics_engine = PhysicsEngine(floor_heights, MAX_SPEED, ACCELERATION)
    flight_profiles = physics_engine.precompute_flight_profiles()

    # --- 共有リソースの作成 ---
    floor_queues = [
        {"UP": simpy.Store(env), "DOWN": simpy.Store(env)}
        for _ in range(NUM_FLOORS + 1)
    ]

    # --- エンティティの作成 ---
    gcs = GroupControlSystem(env, "GCS", broker)
    
    hall_buttons = [
        {'UP': HallButton(env, floor, "UP", broker), 
         'DOWN': HallButton(env, floor, "DOWN", broker)}
        for floor in range(NUM_FLOORS + 1)
    ]

    door1 = Door(env, "Elevator_1_Door")
    # 【師匠改造】運転手に、計算済みの「運命の書」を渡してやる
    elevator1 = Elevator(env, "Elevator_1", broker, NUM_FLOORS, floor_queues, door=door1, flight_profiles=flight_profiles)
    
    gcs.register_elevator(elevator1)

    # --- プロセスの開始 ---
    env.process(passenger_generator(env, broker, hall_buttons, floor_queues))

    print("\n--- Simulation Start ---")
    env.run(until=SIM_DURATION)
    print("--- Simulation End ---")

def passenger_generator(env, broker, hall_buttons, floor_queues):
    """乗客を時間差で生成するプロセス"""
    yield env.timeout(5)
    Passenger(env, "Taro", broker, hall_buttons, floor_queues, 
              arrival_floor=3, destination_floor=8, move_speed=1.0)

    yield env.timeout(5)
    Passenger(env, "Hanako", broker, hall_buttons, floor_queues,
              arrival_floor=9, destination_floor=2, move_speed=1.2)

    yield env.timeout(1)
    Passenger(env, "Paul", broker, hall_buttons, floor_queues,
              arrival_floor=9, destination_floor=2, move_speed=2.5)

    yield env.timeout(1)
    Passenger(env, "Jiro", broker, hall_buttons, floor_queues,
              arrival_floor=2, destination_floor=10, move_speed=0.8)

if __name__ == '__main__':
    run_simulation()

