import math
import numpy as np
import matplotlib.pyplot as plt

class PhysicsEngine:
    """
    【v18.1】グラフ職人(matplotlib)を雇い、自分の計算結果を可視化できるようになった大預言者
    """
    def __init__(self, floor_heights: list, max_speed: float, acceleration: float):
        self.floor_heights = floor_heights
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.num_floors = len(floor_heights)
        self.flight_profiles = {}

    def get_distance(self, floor1, floor2):
        return abs(self.floor_heights[floor1] - self.floor_heights[floor2])

    def precompute_flight_profiles(self):
        print("[PhysicsEngine] Pre-computing all flight profiles...")
        for start_floor in range(1, self.num_floors):
            for end_floor in range(1, self.num_floors):
                if start_floor == end_floor:
                    continue
                
                profile = self._calculate_flight_profile(start_floor, end_floor)
                self.flight_profiles[(start_floor, end_floor)] = profile
        print("[PhysicsEngine] All flight profiles computed.")
        return self.flight_profiles

    def _calculate_flight_profile(self, start_floor, end_floor):
        direction = 1 if end_floor > start_floor else -1
        total_distance = self.get_distance(start_floor, end_floor)

        time_to_reach_max_speed = self.max_speed / self.acceleration
        dist_to_reach_max_speed = 0.5 * self.acceleration * (time_to_reach_max_speed ** 2)

        timeline = []
        last_time = 0.0
        
        path = range(start_floor, end_floor + direction, direction)
        for physical_floor in path:
            dist_from_start = self.get_distance(start_floor, physical_floor)
            
            dist_to_start_decel = total_distance - dist_to_reach_max_speed
            
            if dist_from_start < dist_to_reach_max_speed:
                current_speed = math.sqrt(2 * self.acceleration * dist_from_start)
            elif dist_from_start > dist_to_start_decel:
                dist_from_end = total_distance - dist_from_start
                current_speed = math.sqrt(2 * self.acceleration * dist_from_end)
            else:
                current_speed = self.max_speed
            
            braking_distance = (current_speed ** 2) / (2 * self.acceleration)
            braking_floors = math.ceil(braking_distance / self.get_distance(1, 2))
            advanced_position = physical_floor + direction * braking_floors
            advanced_position = max(1, min(self.num_floors, advanced_position))

            time_at_this_floor = self._calculate_travel_time(dist_from_start)
            time_delta = time_at_this_floor - last_time

            if time_delta > 1e-6 or physical_floor == start_floor:
                timeline.append({
                    "time_delta": time_delta, 
                    "physical_floor": physical_floor,
                    "advanced_position": advanced_position
                })
                last_time = time_at_this_floor

        total_time = last_time
        return {"total_time": total_time, "timeline": timeline}
    
    def _calculate_travel_time(self, distance: float) -> float:
        time_to_reach_max_speed = self.max_speed / self.acceleration
        distance_to_reach_max_speed = 0.5 * self.acceleration * (time_to_reach_max_speed ** 2)
        if distance <= 2 * distance_to_reach_max_speed:
            return 2 * math.sqrt(distance / self.acceleration) if distance > 0 else 0
        else:
            time_for_accel_decel = 2 * time_to_reach_max_speed
            cruise_distance = distance - (2 * distance_to_reach_max_speed)
            time_for_cruise = cruise_distance / self.max_speed
            return time_for_accel_decel + time_for_cruise

    def plot_velocity_profile(self, start_floor, end_floor):
        """【師匠新設】グラフ職人による速度プロファイルの可視化"""
        profile = self.flight_profiles.get((start_floor, end_floor))
        if not profile:
            print(f"Profile for {start_floor}F -> {end_floor}F not found.")
            return

        total_time = profile['total_time']
        total_distance = self.get_distance(start_floor, end_floor)
        
        time_to_reach_max_speed = self.max_speed / self.acceleration
        dist_to_reach_max_speed = 0.5 * self.acceleration * (time_to_reach_max_speed ** 2)
        
        t_vals = np.linspace(0, total_time, 200)
        v_vals = []

        for t in t_vals:
            if t < time_to_reach_max_speed: # 加速
                # d = 0.5at^2, v = at
                dist_covered = 0.5 * self.acceleration * t**2
                if dist_covered > total_distance / 2 and total_distance < 2 * dist_to_reach_max_speed:
                    # 短距離で減速に入る場合
                    v = self.acceleration * (total_time - t)
                else:
                    v = self.acceleration * t
            elif t > total_time - time_to_reach_max_speed and total_distance > 2 * dist_to_reach_max_speed: # 減速
                v = self.max_speed - self.acceleration * (t - (total_time - time_to_reach_max_speed))
            else: # 巡航 or 短距離の頂点
                v = self.max_speed

            v_vals.append(v)

        plt.figure(figsize=(10, 6))
        plt.plot(t_vals, v_vals, label=f"Velocity Profile ({start_floor}F -> {end_floor}F)")
        plt.title("Elevator Velocity Profile")
        plt.xlabel("Time (s)")
        plt.ylabel("Velocity (m/s)")
        plt.grid(True)
        plt.legend()
        plt.show()

# --- このファイルのテスト用コード ---
if __name__ == '__main__':
    floor_heights_test = [0] + [i * 3.5 for i in range(1, 11)] 
    max_speed_test = 4.0
    acceleration_test = 1.0

    engine = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test)
    profiles = engine.precompute_flight_profiles()

    print("\n--- Sample Flight Profile: 1F -> 10F ---")
    profile_1_10 = profiles[(1, 10)]
    print(f"Total time: {profile_1_10['total_time']:.2f}s")
    current_time = 0
    for event in profile_1_10['timeline']:
        phys_pos = event['physical_floor']
        adv_pos = event['advanced_position']
        print(f"  - T={current_time:.2f}s -> T={current_time + event['time_delta']:.2f}s: Phys Pos @ {phys_pos}F -> Adv Pos is {adv_pos}F")
        current_time += event['time_delta']

    # グラフの表示
    engine.plot_velocity_profile(1, 10)
    engine.plot_velocity_profile(1, 3)

