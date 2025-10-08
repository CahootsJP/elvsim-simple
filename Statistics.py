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

    def start_listening(self):
        """
        全局放送の傍受を開始するメインプロセス。
        """
        while True:
            data = yield self.broadcast_pipe.get()
            
            topic = data.get('topic', '')
            message = data.get('message', {})

            # エレベーターの状態報告の中から、先行位置だけを記録する
            match = re.search(r'elevator/(.*?)/status', topic)
            if match and 'advanced_position' in message:
                elevator_name = match.group(1)
                if elevator_name not in self.elevator_trajectories:
                    self.elevator_trajectories[elevator_name] = []
                
                timestamp = message.get('timestamp')
                advanced_position = message.get('advanced_position')

                # 最後のデータ点と全く同じでなければ、記録する
                if not self.elevator_trajectories[elevator_name] or self.elevator_trajectories[elevator_name][-1] != (timestamp, advanced_position):
                    self.elevator_trajectories[elevator_name].append((timestamp, advanced_position))

    def plot_trajectory_diagram(self):
        """シミュレーション終了後、運行線図を描画する"""
        print("\n--- Plotting: Elevator Trajectory Diagram ---")
        plt.figure(figsize=(14, 8))

        for name, trajectory in self.elevator_trajectories.items():
            if not trajectory: continue
            
            sorted_trajectory = sorted(trajectory, key=lambda x: x[0])
            times, floors = zip(*sorted_trajectory)
            
            plt.step(times, floors, where='post', label=name)

        plt.title("Elevator Trajectory Diagram (Travel Diagram, Advanced Position)")
        plt.xlabel("Time (s)")
        plt.ylabel("Advanced Position (Floor)")
        plt.grid(True, which='both', linestyle='--', alpha=0.7)
        
        all_floors = [floor for _, trajectory in self.elevator_trajectories.items() for _, floor in trajectory]
        if all_floors:
            min_floor = int(min(all_floors))
            max_floor = int(max(all_floors))
            plt.yticks(range(min_floor, max_floor + 2))

        plt.legend()
        plt.show()