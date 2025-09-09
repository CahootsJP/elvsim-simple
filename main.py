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
    JERK = 2.0 # 【師匠新設】躍度 (m/s^3)

    print("--- Simulation Setup ---")
    env = simpy.Environment()
    broker = MessageBroker(env)

    # --- 物理エンジンの準備 ---
    floor_heights = [0] + [i * FLOOR_HEIGHT for i in range(1, NUM_FLOORS + 1)]
    physics_engine = PhysicsEngine(floor_heights, MAX_SPEED, ACCELERATION, JERK)
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
    elevator1 = Elevator(env, "Elevator_1", broker, NUM_FLOORS, floor_queues, door=door1, flight_profiles=flight_profiles)
    
    gcs.register_elevator(elevator1)

    # --- プロセスの開始 ---
    env.process(passenger_generator(env, broker, hall_buttons, floor_queues))

    print("\n--- Simulation Start ---")
    env.run(until=SIM_DURATION)
    print("--- Simulation End ---")

def passenger_generator(env, broker, hall_buttons, floor_queues):
    """【師匠改造】真の割り込みテスト用の乗客生成プロセス"""
    print("--- Passenger Generation for REAL Interrupt Test ---")

    # シナリオ1： Saburoが10階へ向かう
    yield env.timeout(5)
    Passenger(env, "Saburo", broker, hall_buttons, floor_queues, 
              arrival_floor=2, destination_floor=10, move_speed=1.0)

    # シナリオ2： Saburoを乗せたエレベータが2階->10階へ飛行中の【15秒】に割り込みをかける！
    yield env.timeout(9) # 5秒 + 9秒 = 14秒にShiroが登場 -> 15秒にボタンを押す
    Passenger(env, "Shiro", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.2)

    # シナリオ3： さらにGoroとRokuroが反対方向の呼びを登録
    yield env.timeout(3)
    Passenger(env, "Goro", broker, hall_buttons, floor_queues,
              arrival_floor=8, destination_floor=1, move_speed=2.5)
    
    yield env.timeout(3)
    Passenger(env, "Rokuro", broker, hall_buttons, floor_queues,
              arrival_floor=5, destination_floor=3, move_speed=0.8)

if __name__ == '__main__':
    run_simulation()

