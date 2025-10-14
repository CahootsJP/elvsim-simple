import simpy
import matplotlib.pyplot as plt
import re

class Statistics:
    """
    シミュレーション世界の全ての通信を傍受し、
    必要な情報を分析・記録する、独立した「記録係」。
    """
    def __init__(self, env, broadcast_pipe):
        self.env = env
        self.broadcast_pipe = broadcast_pipe
        self.elevator_trajectories = {}
        self.hall_calls_history = {}  # エレベータ別のhall_calls履歴
        self.car_calls_history = {}   # エレベータ別のcar_calls履歴

    def start_listening(self):
        """
        全局放送の傍受を開始するメインプロセス。
        """
        while True:
            data = yield self.broadcast_pipe.get()
            
            topic = data.get('topic', '')
            message = data.get('message', {})

            # エレベーターの状態報告の中から、先行位置だけを記録する
            status_match = re.search(r'elevator/(.*?)/status', topic)
            if status_match and 'advanced_position' in message:
                elevator_name = status_match.group(1)
                if elevator_name not in self.elevator_trajectories:
                    self.elevator_trajectories[elevator_name] = []
                
                timestamp = message.get('timestamp')
                advanced_position = message.get('advanced_position')

                # 最後のデータ点と全く同じでなければ、記録する
                if not self.elevator_trajectories[elevator_name] or self.elevator_trajectories[elevator_name][-1] != (timestamp, advanced_position):
                    self.elevator_trajectories[elevator_name].append((timestamp, advanced_position))
            
            # hall_calls情報を記録する
            hall_calls_match = re.search(r'elevator/(.*?)/hall_calls', topic)
            if hall_calls_match:
                elevator_name = hall_calls_match.group(1)
                if elevator_name not in self.hall_calls_history:
                    self.hall_calls_history[elevator_name] = []
                
                timestamp = message.get('timestamp')
                hall_calls_up = message.get('hall_calls_up', [])
                hall_calls_down = message.get('hall_calls_down', [])
                
                # hall_calls情報を記録
                self.hall_calls_history[elevator_name].append({
                    'timestamp': timestamp,
                    'hall_calls_up': hall_calls_up.copy(),
                    'hall_calls_down': hall_calls_down.copy()
                })
            
            # 新規car_call登録を記録する（可視化用）
            new_car_call_match = re.search(r'elevator/(.*?)/new_car_call', topic)
            if new_car_call_match:
                elevator_name = new_car_call_match.group(1)
                if elevator_name not in self.car_calls_history:
                    self.car_calls_history[elevator_name] = []
                
                # 新規登録されたcar_callのみを記録
                timestamp = message.get('timestamp')
                destination = message.get('destination')
                passenger_name = message.get('passenger_name')
                
                if destination is not None and timestamp is not None:
                    self.car_calls_history[elevator_name].append({
                        'timestamp': timestamp,
                        'car_calls': [destination],  # 新規登録された1つの階のみ
                        'passenger_name': passenger_name
                    })

    def plot_trajectory_diagram(self):
        """シミュレーション終了後、運行線図を描画する"""
        print("\n--- Plotting: Elevator Trajectory Diagram ---")
        plt.figure(figsize=(14, 8))

        for name, trajectory in self.elevator_trajectories.items():
            if not trajectory: continue
            
            sorted_trajectory = sorted(trajectory, key=lambda x: x[0])
            times, floors = zip(*sorted_trajectory)
            
            plt.step(times, floors, where='post', label=name)
            
            # hall_calls矢印を描画
            self._plot_hall_calls_arrows(name)
            
            # car_calls丸印を描画
            self._plot_car_calls_circles(name)

        plt.title("Elevator Trajectory Diagram (Travel Diagram, Advanced Position)")
        plt.xlabel("Time (s)")
        plt.ylabel("Advanced Position (Floor)")
        plt.grid(True, which='both', linestyle='--', alpha=0.7)
        
        all_floors = [floor for _, trajectory in self.elevator_trajectories.items() for _, floor in trajectory]
        if all_floors:
            min_floor = int(min(all_floors))
            max_floor = int(max(all_floors))
            plt.yticks(range(min_floor, max_floor + 2))

        #plt.legend()
        plt.show()
    
    def _plot_hall_calls_arrows(self, elevator_name):
        """指定されたエレベータのhall_calls矢印を描画する"""
        if elevator_name not in self.hall_calls_history:
            return
        
        for hall_call_data in self.hall_calls_history[elevator_name]:
            timestamp = hall_call_data['timestamp']
            hall_calls_up = hall_call_data['hall_calls_up']
            hall_calls_down = hall_call_data['hall_calls_down']
            
            # 上向き矢印（緑色）
            for floor in hall_calls_up:
                plt.annotate('↑', (timestamp, floor), 
                           fontsize=12, color='green', fontweight='bold',
                           ha='center', va='center',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='lightgreen', alpha=0.7))
            
            # 下向き矢印（赤色）
            for floor in hall_calls_down:
                plt.annotate('↓', (timestamp, floor), 
                           fontsize=12, color='red', fontweight='bold',
                           ha='center', va='center',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='lightcoral', alpha=0.7))
    
    def _plot_car_calls_circles(self, elevator_name):
        """指定されたエレベータのcar_calls丸印を描画する（重複回避版）"""
        if elevator_name not in self.car_calls_history:
            return
        
        # 既に描画した(timestamp, floor)の組み合わせを追跡
        plotted_positions = set()
        
        for car_call_data in self.car_calls_history[elevator_name]:
            timestamp = car_call_data['timestamp']
            car_calls = car_call_data['car_calls']
            
            # 丸印（青色）でcar_callsを表示（重複回避）
            for floor in car_calls:
                position_key = (round(timestamp, 2), floor)  # 時刻を丸めて重複判定
                
                if position_key not in plotted_positions:
                    plt.scatter(timestamp, floor, 
                              s=80, c='blue', marker='o', alpha=0.7, 
                              edgecolors='darkblue', linewidth=1.5,
                              label='Car Calls' if not hasattr(self, '_car_calls_legend_added') else "")
                    plotted_positions.add(position_key)
        
        # 凡例の重複を防ぐ
        if not hasattr(self, '_car_calls_legend_added'):
            self._car_calls_legend_added = True