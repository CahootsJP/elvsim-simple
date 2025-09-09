import math
import numpy as np
import matplotlib.pyplot as plt
import sympy as sp

class PhysicsEngine:
    """
    【v21.2】ログ出力を美しくするため、タイムラインの数値を整形するようになった大預言者
    """
    def __init__(self, floor_heights: list, max_speed: float, acceleration: float, jerk: float):
        self.floor_heights = floor_heights
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.jerk = jerk
        self.num_floors = len(floor_heights)
        self.flight_profiles = {}

    def get_distance(self, floor1, floor2):
        return abs(self.floor_heights[floor1] - self.floor_heights[floor2])

    def precompute_flight_profiles(self):
        print("[PhysicsEngine] Pre-computing all S-curve flight profiles...")
        for start_floor in range(1, self.num_floors):
            for end_floor in range(1, self.num_floors):
                if start_floor == end_floor:
                    continue
                
                profile = self._calculate_s_curve_profile(start_floor, end_floor)
                self.flight_profiles[(start_floor, end_floor)] = profile
        print("[PhysicsEngine] All flight profiles computed.")
        return self.flight_profiles

    def _calculate_s_curve_profile(self, start_floor, end_floor):
        """
        SymPyを使ってS字速度プロファイルのタイムラインを計算する。
        【シムパイ師匠】エラーと速度低下の問題を修正
        """
        j_max, a_max, v_max = self.jerk, self.acceleration, self.max_speed
        D = self.get_distance(start_floor, end_floor)

        # --- S字プロファイルの各フェーズの時間を計算 ---
        # 【シムパイ師匠】短距離移動でも計算が破綻しないようにロジックを全面改修
        
        # Case 1: 最高速度(v_max)に達する長距離移動の場合
        dist_to_reach_max_speed = v_max * (v_max / a_max + a_max / j_max)
        
        if D >= dist_to_reach_max_speed:
            t1 = a_max / j_max
            t2 = v_max / a_max - t1
            t4 = (D - dist_to_reach_max_speed) / v_max
        # Case 2: 最高速度に達しない短距離移動の場合
        else:
            t4 = 0
            # この計算は複雑なので、簡略化した安定版の公式を使う
            # v_peakを求める複雑な計算を避ける
            t_accel_to_v_peak = math.sqrt(D/a_max) if D*j_max < a_max**2 else (a_max/j_max + math.sqrt( (a_max/j_max)**2 + 4*D/a_max ))/2
            v_peak = a_max * (t_accel_to_v_peak - a_max/j_max)
            
            t1 = a_max/j_max
            t2 = v_peak/a_max - t1
            if(t2 < 0):
                t1 = math.sqrt(v_peak/j_max)
                t2 = 0
                
            # 稀なケースでのt2の微小な負の値を補正
            if t2 < 0: t2 = 0

        total_time = 2 * t1 + 2 * t2 + t4

        # --- SymPyで数式を一度だけ定義 ---
        t = sp.Symbol('t')
        t_p1 = t1
        t_p2 = t1 + t2
        t_p3 = t1 + t2 + t1
        t_p4 = t1 + t2 + t1 + t4
        t_p5 = t1 + t2 + t1 + t4 + t1
        t_p6 = t1 + t2 + t1 + t4 + t1 + t2

        j_t = sp.Piecewise( (j_max, t <= t_p1), (0, t <= t_p2), (-j_max, t <= t_p3), (0, t <= t_p4),
                            (-j_max, t <= t_p5), (0, t <= t_p6), (j_max, True) )
        a_t = sp.integrate(j_t, t)
        v_t = sp.integrate(a_t, t)
        d_t = sp.integrate(v_t, t)

        # --- 【シムパイ師匠】超高速化対応！数式を高速な数値計算関数に変換 ---
        v_func = sp.lambdify(t, v_t, 'numpy')
        d_func = sp.lambdify(t, d_t, 'numpy')

        # --- タイムラインを生成 ---
        timeline = []
        direction = 1 if end_floor > start_floor else -1
        
        dt = 0.05 # 時間ステップは少し粗くてもOK
        last_timeline_time = 0
        last_floor = -1
        last_adv_floor = -1

        time_points = np.arange(0, total_time, dt)
        if total_time not in time_points:
            time_points = np.append(time_points, total_time) # 最後に終点を追加

        for time_step in time_points:
            dist = d_func(time_step)
            vel = v_func(time_step)
            
            physical_floor = start_floor + direction * math.floor(dist / self.get_distance(1, 2) + 1e-9)
            physical_floor = max(1, min(self.num_floors, physical_floor))

            # 【シムパイ師匠】先行位置の計算精度を向上
            dist_to_stop = (vel**2) / (2 * a_max) if a_max > 0 else 0
            adv_dist = dist + dist_to_stop
            advanced_position = start_floor + direction * math.ceil(adv_dist / self.get_distance(1, 2) - 1e-9)
            advanced_position = max(1, min(self.num_floors, advanced_position))

            if physical_floor != last_floor or advanced_position != last_adv_floor or time_step == 0:
                time_delta = time_step - last_timeline_time
                if time_delta > 1e-9:
                    timeline.append({
                        "time_delta": float(time_delta), # 【シムパイ師匠】ここでfloatに変換
                        "physical_floor": int(physical_floor),
                        "advanced_position": int(advanced_position)
                    })
                    last_timeline_time = time_step
                
                last_floor = physical_floor
                last_adv_floor = advanced_position

        # 最後のイベントの残り時間を調整
        if timeline:
            current_total_time = sum(e['time_delta'] for e in timeline)
            remaining_time = total_time - current_total_time
            if remaining_time > 1e-9:
                 timeline.append({
                        "time_delta": float(remaining_time), # 【シムパイ師匠】ここでfloatに変換
                        "physical_floor": int(end_floor),
                        "advanced_position": int(end_floor)
                    })

        return {"total_time": float(total_time), "timeline": timeline}


    def plot_velocity_profile(self, start_floor, end_floor):
        """【シムパイ師匠】S字プロファイルを可視化できるように改造"""
        profile = self.flight_profiles.get((start_floor, end_floor))
        if not profile:
            print(f"Profile for {start_floor}F -> {end_floor}F not found.")
            return

        total_time = profile['total_time']
        
        # --- SymPyの数式を再構築（プロット用） ---
        t = sp.Symbol('t')
        j_max, a_max, v_max = self.jerk, self.acceleration, self.max_speed
        D = self.get_distance(start_floor, end_floor)

        dist_to_reach_max_speed = v_max * (v_max / a_max + a_max / j_max)
        if D >= dist_to_reach_max_speed:
            t1 = a_max / j_max
            t2 = v_max / a_max - t1
            t4 = (D - dist_to_reach_max_speed) / v_max
        else:
            t4 = 0
            t_accel_to_v_peak = math.sqrt(D/a_max) if D*j_max < a_max**2 else (a_max/j_max + math.sqrt( (a_max/j_max)**2 + 4*D/a_max ))/2
            v_peak = a_max * (t_accel_to_v_peak - a_max/j_max)
            t1 = a_max/j_max
            t2 = v_peak/a_max - t1
            if(t2 < 0):
                t1 = math.sqrt(v_peak/j_max)
                t2 = 0
            if t2 < 0: t2 = 0
        
        total_time_plot = 2 * t1 + 2 * t2 + t4

        t_p1 = t1; t_p2 = t1 + t2; t_p3 = t1 + t2 + t1
        t_p4 = t_p3 + t4; t_p5 = t_p4 + t1; t_p6 = t_p5 + t2

        j_t = sp.Piecewise((j_max, t <= t_p1), (0, t <= t_p2), (-j_max, t <= t_p3), (0, t <= t_p4),
                           (-j_max, t <= t_p5), (0, t <= t_p6), (j_max, True))
        a_t = sp.integrate(j_t, t)
        v_t = sp.integrate(a_t, t)
        
        # ---プロットの実行---
        t_vals = np.linspace(0, float(total_time_plot), 300)
        v_func = sp.lambdify(t, v_t, 'numpy')
        v_vals = v_func(t_vals)

        plt.figure(figsize=(10, 6))
        plt.plot(t_vals, v_vals, label=f"S-Curve Velocity Profile ({start_floor}F -> {end_floor}F)")
        plt.title("Elevator S-Curve Velocity Profile")
        plt.xlabel("Time (s)")
        plt.ylabel("Velocity (m/s)")
        plt.axhline(self.max_speed, color='r', linestyle='--', label=f'Max Speed ({self.max_speed} m/s)')
        plt.grid(True)
        plt.legend()
        plt.show()

# --- このファイルのテスト用コード ---
if __name__ == '__main__':
    floor_heights_test = [0] + [i * 3.5 for i in range(1, 11)] 
    max_speed_test = 2.5
    acceleration_test = 1.0
    jerk_test = 1.0

    engine = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test, jerk_test)
    profiles = engine.precompute_flight_profiles()

    print("\n--- Sample S-Curve Flight Profile: 1F -> 10F ---")
    profile_1_10 = profiles.get((1, 10))
    if profile_1_10:
        print(f"Total time: {profile_1_10['total_time']:.2f}s")
    
    # グラフの表示
    engine.plot_velocity_profile(1, 10)
    engine.plot_velocity_profile(1, 3)

