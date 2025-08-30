import simpy
from MessageBroker import MessageBroker
from GroupControlSystem import GroupControlSystem
from Elevator import Elevator
from HallButton import HallButton
from Passenger import Passenger

# --- シミュレーション設定 ---
RANDOM_SEED = 42
SIM_DURATION = 100  # シミュレーション時間
NUM_ELEVATORS = 1
NUM_FLOORS = 10

def run_simulation():
    """
    シミュレーション全体をセットアップして実行するメイン関数
    """
    print("--- Simulation Setup ---")
    
    # 1. 環境と主要コンポーネントの作成
    env = simpy.Environment()
    broker = MessageBroker(env)
    gcs = GroupControlSystem(env, "GCS", broker)

    # 2. エレベータと関連コンポーネントの作成
    elevators = []
    hall_buttons = []
    for i in range(NUM_ELEVATORS):
        elevator_name = f"Elevator_{i+1}"
        elevator = Elevator(env, elevator_name, broker, num_floors=NUM_FLOORS)
        elevators.append(elevator)
        gcs.register_elevator(elevator) # GCSにエレベータを登録

    # 各階にホールボタンを設置
    for floor in range(1, NUM_FLOORS + 1):
        # 最上階にはUPボタンは不要
        if floor < NUM_FLOORS:
            hall_buttons.append(HallButton(env, broker, floor, "UP"))
        # 1階にはDOWNボタンは不要
        if floor > 1:
            hall_buttons.append(HallButton(env, broker, floor, "DOWN"))

    print("--- Simulation Start ---")
    
    # 3. 乗客を生成するプロセスを開始
    env.process(passenger_generator(env, broker, hall_buttons))

    # 4. シミュレーションを実行
    env.run(until=SIM_DURATION)
    
    print("--- Simulation End ---")

def passenger_generator(env, broker, hall_buttons):
    """
    シミュレーション中に乗客を生成するプロセス
    """
    # テストシナリオ：3人の乗客を異なる時間に登場させる
    
    # 1人目：太郎 (5秒後に3階から8階へ)
    yield env.timeout(5)
    Passenger(env, "Taro", broker, hall_buttons, 
              arrival_floor=3, destination_floor=8)

    # 2人目：花子 (10秒後に9階から2階へ)
    yield env.timeout(5) # 太郎の登場から5秒後 (シミュレーション開始から10秒後)
    Passenger(env, "Hanako", broker, hall_buttons,
              arrival_floor=9, destination_floor=2)
    
    # 3人目：次郎 (12秒後に2階から10階へ)
    yield env.timeout(2) # 花子の登場から2秒後 (シミュレーション開始から12秒後)
    Passenger(env, "Jiro", broker, hall_buttons,
              arrival_floor=2, destination_floor=10)


if __name__ == '__main__':
    run_simulation()
