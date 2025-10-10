import simpy
from MessageBroker import MessageBroker
from GroupControlSystem import GroupControlSystem
from Elevator import Elevator
from HallButton import HallButton
from Passenger import Passenger
from Door import Door
from PhysicsEngine import PhysicsEngine # 物理エンジンをインポート
from Statistics import Statistics

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
    broadcast_pipe = broker.get_broadcast_pipe()
    statistics = Statistics(env, broadcast_pipe)
    env.process(statistics.start_listening())

    # --- 物理エンジンの準備 ---
    floor_heights = [0] + [i * FLOOR_HEIGHT for i in range(1, NUM_FLOORS + 1)]
    physics_engine = PhysicsEngine(floor_heights, MAX_SPEED, ACCELERATION, JERK)
    
    # 【テスト】実用的な移動時間計算方式を有効化
    physics_engine.use_realistic_method = True
    
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
    # 通常テスト用
    # env.process(passenger_generator(env, broker, hall_buttons, floor_queues))
    
    # 統合テスト用（同じ階での乗車・降車）
    env.process(passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues))

    print("\n--- Simulation Start ---")
    env.run(until=SIM_DURATION)
    print("--- Simulation End ---")
    statistics.plot_trajectory_diagram()

def passenger_generator_integrated_test(env, broker, hall_buttons, floor_queues):
    """同じ階での乗車・降車統合テスト用の乗客生成プロセス"""
    print("--- Passenger Generation for INTEGRATED Boarding & Exit Test ---")

    # === テストケース1: 3階から3人が乗車 → 8階で3人が降車 ===
    yield env.timeout(5)
    Passenger(env, "Alice", broker, hall_buttons, floor_queues, 
              arrival_floor=3, destination_floor=8, move_speed=1.0)
    
    yield env.timeout(1)  # 1秒後に同じ階に到着
    Passenger(env, "Bob", broker, hall_buttons, floor_queues,
              arrival_floor=3, destination_floor=8, move_speed=1.2)
    
    yield env.timeout(2)  # さらに2秒後に同じ階に到着
    Passenger(env, "Charlie", broker, hall_buttons, floor_queues,
              arrival_floor=3, destination_floor=8, move_speed=0.8)

    # === テストケース2: 6階から2人が乗車 → 9階で2人が降車 ===
    yield env.timeout(8)
    Passenger(env, "Diana", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.5)
    
    yield env.timeout(1.5)  # 1.5秒後に同じ階に到着
    Passenger(env, "Eve", broker, hall_buttons, floor_queues,
              arrival_floor=6, destination_floor=9, move_speed=1.3)

    # === テストケース3: 複雑なケース - 5階から4人が乗車 → 2階で4人が降車 ===
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

    # === テストケース4: 混合ケース - 異なる階から乗車 → 同じ階で降車 ===
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
    """真の割り込みテスト用の乗客生成プロセス"""
    print("--- Passenger Generation for REAL Interrupt Test ---")

    # シナリオ1： Saburoが10階へ向かう
    yield env.timeout(5)
    Passenger(env, "Saburo", broker, hall_buttons, floor_queues, 
              arrival_floor=2, destination_floor=10, move_speed=1.0)

    # シナリオ2： Saburoを乗せたエレベータが2階->10階へ飛行中の15秒に割り込みをかける！
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

