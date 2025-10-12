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
        
        # 【実用的な移動時間計算】事前計算テーブル
        self.cruise_table = {}      # 巡航時間テーブル
        self.brake_table = {}       # 制動時間テーブル
        self.flight_time_table = {} # 総移動時間テーブル
        
        # 遅れ時間パラメータ（実用的な移動時間計算）
        self.start_response_time = 0.2   # 応答時間 (200ms)
        self.start_delay_time = 0.2   # 起動遅延時間  
        self.stop_adjustable_time = 0.0   # 停止調整時間
        self.use_realistic_method = True  # 実用的な移動時間計算の有効/無効フラグ（デフォルト：実用的方式）

    def get_distance(self, floor1, floor2):
        return abs(self.floor_heights[floor1] - self.floor_heights[floor2])

    def precompute_flight_profiles(self):
        """既存のインターフェースを維持しつつ、内部実装を選択可能にする"""
        if self.use_realistic_method:
            # 【実用的な移動時間計算】新実装を使用
            self.precompute_flight_tables()
            
            # 既存の形式でプロファイル生成（互換性のため）
            for start_floor in range(1, self.num_floors):
                for end_floor in range(1, self.num_floors):
                    if start_floor != end_floor:
                        profile = self._build_timeline_from_table(start_floor, end_floor)
                        self.flight_profiles[(start_floor, end_floor)] = profile
            
            print("[PhysicsEngine] Flight profiles computed using realistic method.")
            return self.flight_profiles
        else:
            # 【従来方式】SymPy実装を使用
            print("[PhysicsEngine] Pre-computing all S-curve flight profiles...")
            validation_errors = []
            
            for start_floor in range(1, self.num_floors):
                for end_floor in range(1, self.num_floors):
                    if start_floor == end_floor:
                        continue
                    
                    profile = self._calculate_s_curve_profile(start_floor, end_floor)
                    self.flight_profiles[(start_floor, end_floor)] = profile
                    
                    # 詳細な検証を実行
                    errors = self._detailed_validation(profile, start_floor, end_floor)
                    if errors:
                        validation_errors.extend(errors)
            
            print("[PhysicsEngine] All flight profiles computed.")
            
            # 検証結果を報告
            if validation_errors:
                print(f"[PhysicsEngine] WARNING: Found {len(validation_errors)} validation issues:")
                for error in validation_errors[:10]:  # 最初の10個のみ表示
                    print(f"   {error}")
                if len(validation_errors) > 10:
                    print(f"   ... and {len(validation_errors) - 10} more issues")
            else:
                print("[PhysicsEngine] All flight profiles passed validation.")
                
            return self.flight_profiles

    def _calculate_s_curve_profile(self, start_floor, end_floor):
        """
        SymPyを使ってS字速度プロファイルのタイムラインを計算する。
        エラーと速度低下の問題を修正
        """
        j_max, a_max, v_max = self.jerk, self.acceleration, self.max_speed
        D = self.get_distance(start_floor, end_floor)

        # --- S字プロファイルの各フェーズの時間を計算 ---
        # 短距離移動でも計算が破綻しないようにロジックを全面改修
        
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

        # --- 超高速化対応！数式を高速な数値計算関数に変換 ---
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

        last_advanced_position = start_floor  # 連続性を保つための前回値
        
        for time_step in time_points:
            dist = d_func(time_step)
            vel = v_func(time_step)
            
            physical_floor = start_floor + direction * math.floor(dist / self.get_distance(1, 2) + 1e-9)
            physical_floor = max(1, min(self.num_floors, physical_floor))

            # 先行位置の計算精度を向上
            dist_to_stop = (vel**2) / (2 * a_max) if a_max > 0 else 0
            adv_dist = dist + dist_to_stop
            advanced_position = start_floor + direction * math.ceil(adv_dist / self.get_distance(1, 2) - 1e-9)
            advanced_position = max(1, min(self.num_floors, advanced_position))
            
            # 連続性を強制：前回値より逆戻りしないようにする
            original_advanced_position = advanced_position
            if direction == 1:  # 上昇
                advanced_position = max(advanced_position, last_advanced_position)
            elif direction == -1:  # 下降
                advanced_position = min(advanced_position, last_advanced_position)
            
            # 修正が適用された場合のみエラー出力
            if original_advanced_position != advanced_position:
                print(f"[PhysicsEngine] WARNING: Applied fix {start_floor}F->{end_floor}F at time={time_step:.3f}, {original_advanced_position}->{advanced_position}")
            
            # 【修正】物理フロアの連続性も強制
            if direction == 1:  # 上昇
                physical_floor = max(physical_floor, start_floor)
            elif direction == -1:  # 下降
                physical_floor = min(physical_floor, start_floor)
            
            # 異常値検出
            if start_floor != end_floor:
                if direction == 1 and advanced_position < start_floor:
                    print(f"[PhysicsEngine] ERROR: UP movement but adv_pos={advanced_position} < start={start_floor}")
                elif direction == -1 and advanced_position > start_floor:
                    print(f"[PhysicsEngine] ERROR: DOWN movement but adv_pos={advanced_position} > start={start_floor}")

            # 前回値を更新
            last_advanced_position = advanced_position

            if physical_floor != last_floor or advanced_position != last_adv_floor or time_step == 0:
                time_delta = time_step - last_timeline_time
                if time_delta > 1e-9:
                    timeline.append({
                        "time_delta": float(time_delta), # ここでfloatに変換
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
                        "time_delta": float(remaining_time), # ここでfloatに変換
                        "physical_floor": int(end_floor),
                        "advanced_position": int(end_floor)
                    })

        # タイムラインの妥当性を検証
        self._validate_timeline(timeline, start_floor, end_floor)
        
        # 連続性チェック（エラーのみ出力）
        if timeline and start_floor != end_floor:
            prev_adv_pos = None
            for i, event in enumerate(timeline):
                adv_pos = event['advanced_position']
                if prev_adv_pos is not None:
                    if direction == 1 and adv_pos < prev_adv_pos:
                        print(f"[PhysicsEngine] ERROR: Timeline {start_floor}F->{end_floor}F Event {i}: REVERSAL {prev_adv_pos} -> {adv_pos}")
                    elif direction == -1 and adv_pos > prev_adv_pos:
                        print(f"[PhysicsEngine] ERROR: Timeline {start_floor}F->{end_floor}F Event {i}: REVERSAL {prev_adv_pos} -> {adv_pos}")
                prev_adv_pos = adv_pos
        
        return {"total_time": float(total_time), "timeline": timeline}

    def _validate_timeline(self, timeline, start_floor, end_floor):
        """
        タイムラインのadvanced_positionが物理的に正しいか検証する
        """
        if not timeline:
            return
            
        direction = 1 if end_floor > start_floor else -1
        prev_advanced_position = None
        
        for i, event in enumerate(timeline):
            current_advanced_position = event['advanced_position']
            
            # 最初のイベントはスキップ
            if prev_advanced_position is not None:
                # 上昇中は値が増加、下降中は値が減少する必要がある
                if direction == 1:  # 上昇
                    if current_advanced_position < prev_advanced_position:
                        print(f"[PhysicsEngine] WARNING: Advanced position decreased during UP movement!")
                        print(f"   Event {i}: {prev_advanced_position} -> {current_advanced_position}")
                        print(f"   Start: {start_floor}F, End: {end_floor}F")
                elif direction == -1:  # 下降
                    if current_advanced_position > prev_advanced_position:
                        print(f"[PhysicsEngine] WARNING: Advanced position increased during DOWN movement!")
                        print(f"   Event {i}: {prev_advanced_position} -> {current_advanced_position}")
                        print(f"   Start: {start_floor}F, End: {end_floor}F")
            
            prev_advanced_position = current_advanced_position

    def _detailed_validation(self, profile, start_floor, end_floor):
        """
        より詳細な検証を実行し、エラーメッセージのリストを返す
        """
        errors = []
        timeline = profile.get('timeline', [])
        
        if not timeline:
            errors.append(f"Empty timeline for {start_floor}F -> {end_floor}F")
            return errors
            
        direction = 1 if end_floor > start_floor else -1
        prev_advanced_position = None
        prev_physical_floor = None
        
        for i, event in enumerate(timeline):
            current_advanced_position = event['advanced_position']
            current_physical_floor = event['physical_floor']
            
            # 範囲チェック
            if not (1 <= current_advanced_position <= self.num_floors):
                errors.append(f"Advanced position out of range: {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
            
            if not (1 <= current_physical_floor <= self.num_floors):
                errors.append(f"Physical floor out of range: {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
            
            # 単調性チェック
            if prev_advanced_position is not None:
                if direction == 1 and current_advanced_position < prev_advanced_position:
                    errors.append(f"Advanced position decreased during UP: {prev_advanced_position} -> {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
                elif direction == -1 and current_advanced_position > prev_advanced_position:
                    errors.append(f"Advanced position increased during DOWN: {prev_advanced_position} -> {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
            
            # 物理的整合性チェック
            if prev_physical_floor is not None:
                if direction == 1 and current_physical_floor < prev_physical_floor:
                    errors.append(f"Physical floor decreased during UP: {prev_physical_floor} -> {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
                elif direction == -1 and current_physical_floor > prev_physical_floor:
                    errors.append(f"Physical floor increased during DOWN: {prev_physical_floor} -> {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
            
            prev_advanced_position = current_advanced_position
            prev_physical_floor = current_physical_floor
        
        # 最終位置のチェック
        if timeline:
            final_event = timeline[-1]
            if final_event['physical_floor'] != end_floor:
                errors.append(f"Final physical floor mismatch: expected {end_floor}, got {final_event['physical_floor']} ({start_floor}F->{end_floor}F)")
            if final_event['advanced_position'] != end_floor:
                errors.append(f"Final advanced position mismatch: expected {end_floor}, got {final_event['advanced_position']} ({start_floor}F->{end_floor}F)")
        
        return errors

    # ========== 【実用的方式】 ==========
    
    def _calc_flight_time(self, start_floor, end_floor):
        """実用的な移動時間計算"""
        span = self.get_distance(start_floor, end_floor) * 1000  # mm単位に変換
        if span == 0:
            return 0.1, 0  # 同一階の場合
        
        # 最適速度計算
        alpha = self.acceleration * 1000  # mm/s²に変換
        beta = self.jerk * 1000          # mm/s³に変換
        rated_vel = self.max_speed * 60   # m/min単位に変換
        
        t = (alpha * alpha) / (beta * 2)
        optimal_vel = ((t*t + alpha * span) ** 0.5 - t) * 60 / 1000
        
        # 定格速度制限
        if optimal_vel > rated_vel:
            vel = rated_vel
            dtime = alpha * 1000 / beta  # 定格速度到達時の加速時間
        else:
            vel = optimal_vel
            dtime = 2 * alpha * 1000 / beta  # ジャーク制限時の加速時間
        
        # 総移動時間計算（実用的な移動時間計算）
        accel_time = vel * 1000 * 1000 / (alpha * 60)
        jerk_time = alpha * 1000 / beta
        travel_time = span * 60 / vel
        
        total_time_ms = self.start_delay_time * 1000 + travel_time + accel_time + jerk_time + self.stop_adjustable_time * 1000
        total_time = total_time_ms / 1000  # 秒単位に変換
        
        return max(0.1, total_time), vel
    
    def _calc_brake_time(self, vel):
        """制動時間の計算"""
        if vel == 0:
            return 0.1
        
        alpha = self.acceleration * 1000
        beta = self.jerk * 1000
        
        # 制動時間 = 加速時間と同じ
        brake_time_ms = vel * 1000 * 1000 / (alpha * 60) + alpha * 1000 / beta
        return max(0.1, brake_time_ms / 1000)
    
    def precompute_flight_tables(self):
        """実用的な事前計算テーブル方式"""
        print("[PhysicsEngine] Computing flight tables (realistic style)...")
        
        for i in range(1, self.num_floors):
            # 上昇方向の計算
            cruise_time = 0
            for j in range(i + 1, self.num_floors):
                total_time, vel = self._calc_flight_time(i, j)
                brake_time = self._calc_brake_time(vel)
                
                # 巡航時間 = 制動開始までの猶予時間
                cruise_duration = total_time - cruise_time - brake_time
                
                self.cruise_table[(i, j)] = max(0.05, cruise_duration)
                self.brake_table[(i, j)] = brake_time
                self.flight_time_table[(i, j)] = total_time
                
                cruise_time += self.cruise_table[(i, j)]
            
            # 下降方向の計算
            cruise_time = 0
            for j in range(i - 1, 0, -1):
                total_time, vel = self._calc_flight_time(i, j)
                brake_time = self._calc_brake_time(vel)
                
                cruise_duration = total_time - cruise_time - brake_time
                
                self.cruise_table[(i, j)] = max(0.05, cruise_duration)
                self.brake_table[(i, j)] = brake_time
                self.flight_time_table[(i, j)] = total_time
                
                cruise_time += self.cruise_table[(i, j)]
        
        print("[PhysicsEngine] Flight tables computed (realistic method).")
    
    def _build_timeline_from_table(self, start_floor, end_floor):
        """事前計算テーブルからタイムラインを構築"""
        if start_floor == end_floor:
            return {'total_time': 0.1, 'timeline': []}
        
        timeline = []
        direction = 1 if end_floor > start_floor else -1
        
        # 各階層での移動を区間分割
        current_floor = start_floor
        while current_floor != end_floor:
            next_floor = current_floor + direction
            
            # テーブルから時間を取得
            cruise_time = self.cruise_table.get((start_floor, next_floor), 0.1)
            
            timeline.append({
                'time_delta': cruise_time,
                'physical_floor': current_floor,
                'advanced_position': next_floor
            })
            
            current_floor = next_floor
        
        # 最終制動区間
        brake_time = self.brake_table.get((start_floor, end_floor), 0.1)
        if brake_time > 0.05:
            timeline.append({
                'time_delta': brake_time,
                'physical_floor': end_floor,
                'advanced_position': end_floor
            })
        
        total_time = sum(e['time_delta'] for e in timeline)
        return {'total_time': total_time, 'timeline': timeline}

    def plot_velocity_profile(self, start_floor, end_floor):
        """S字プロファイルを可視化できるように改造"""
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

    print("=== 従来方式（SymPy）のテスト ===")
    engine_old = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test, jerk_test)
    engine_old.use_realistic_method = False
    profiles_old = engine_old.precompute_flight_profiles()

    print("\n=== 新方式（実用的な移動時間計算）のテスト ===")
    engine_new = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test, jerk_test)
    engine_new.use_realistic_method = True
    profiles_new = engine_new.precompute_flight_profiles()

    print("\n--- 比較テスト: 1F -> 10F ---")
    profile_old = profiles_old.get((1, 10))
    profile_new = profiles_new.get((1, 10))
    
    if profile_old and profile_new:
        print(f"従来方式: Total time: {profile_old['total_time']:.2f}s, Events: {len(profile_old['timeline'])}")
        print(f"新方式:   Total time: {profile_new['total_time']:.2f}s, Events: {len(profile_new['timeline'])}")
        
        # タイムライン比較
        print("\n--- タイムライン比較（最初の5イベント） ---")
        print("従来方式:")
        for i, event in enumerate(profile_old['timeline'][:5]):
            print(f"  Event {i}: Δt={event['time_delta']:.3f}s, Floor={event['physical_floor']}, Adv={event['advanced_position']}")
        
        print("新方式:")
        for i, event in enumerate(profile_new['timeline'][:5]):
            print(f"  Event {i}: Δt={event['time_delta']:.3f}s, Floor={event['physical_floor']}, Adv={event['advanced_position']}")
    
    print("\n--- 実用的な事前計算テーブル内容（サンプル） ---")
    print("Cruise table (1F -> 上昇):")
    for j in range(2, min(6, engine_new.num_floors)):
        cruise_time = engine_new.cruise_table.get((1, j), 0)
        brake_time = engine_new.brake_table.get((1, j), 0)
        total_time = engine_new.flight_time_table.get((1, j), 0)
        print(f"  1F -> {j}F: cruise={cruise_time:.3f}s, brake={brake_time:.3f}s, total={total_time:.3f}s")
    
    # グラフの表示（従来方式のみ）
    # engine_old.plot_velocity_profile(1, 10)
    # engine_old.plot_velocity_profile(1, 3)

