import simpy
from MessageBroker import MessageBroker
from GroupControlSystem import GroupControlSystem
from Elevator import Elevator
from Door import Door  # Doorをインポート
from HallButton import HallButton
from Passenger import Passenger

def run_simulation():
    """シミュレーション全体をセットアップして実行する"""
    SIM_DURATION = 100
    NUM_FLOORS = 10

    print("--- Simulation Setup ---")
    env = simpy.Environment()
    broker = MessageBroker(env)

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

    # 【師匠修正】まずドア（警備員）を作成する
    door1 = Door(env, "Elevator_1_Door", broker)
    # 【師匠修正】作成したドアをエレベータ（運転手）に割り当てる
    elevator1 = Elevator(env, "Elevator_1", broker, NUM_FLOORS, floor_queues, door1)
    
    gcs.register_elevator(elevator1)

    # --- プロセスの開始 ---
    env.process(passenger_generator(env, broker, hall_buttons, floor_queues))

    print("--- Simulation Start ---")
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
              arrival_floor=9, destination_floor=2, move_speed=2.5) # 車いすの利用者

    yield env.timeout(1)
    Passenger(env, "Jiro", broker, hall_buttons, floor_queues,
              arrival_floor=2, destination_floor=10, move_speed=0.8)


if __name__ == '__main__':
    run_simulation()

