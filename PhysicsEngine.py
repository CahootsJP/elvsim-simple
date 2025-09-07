import math

class PhysicsEngine:
    """
    【v18.0】「先行位置」のタイムテーブルを事前計算する、大預言者となった物理エンジン
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
        """
        【師匠大改造】先行位置のタイムテーブルを含む「運命の書」を作成する
        """
        direction = 1 if end_floor > start_floor else -1
        total_distance = self.get_distance(start_floor, end_floor)

        time_to_reach_max_speed = self.max_speed / self.acceleration
        dist_to_reach_max_speed = 0.5 * self.acceleration * (time_to_reach_max_speed ** 2)

        timeline = []
        last_time = 0.0
        
        path = range(start_floor, end_floor + direction, direction)
        for physical_floor in path:
            dist_from_start = self.get_distance(start_floor, physical_floor)
            
            # 1. 現在の物理位置での速度を計算
            #    - 加速中か、巡航中か、減速中かで場合分け
            dist_to_start_decel = total_distance - dist_to_reach_max_speed
            
            if dist_from_start < dist_to_reach_max_speed: # 加速フェーズ
                # v^2 = 2ad -> v = sqrt(2ad)
                current_speed = math.sqrt(2 * self.acceleration * dist_from_start)
            elif dist_from_start > dist_to_start_decel: # 減速フェーズ
                dist_from_end = total_distance - dist_from_start
                current_speed = math.sqrt(2 * self.acceleration * dist_from_end)
            else: # 巡航フェーズ
                current_speed = self.max_speed
            
            # 2. その速度から止まるのに必要な制動距離を計算
            #    d = v^2 / 2a
            braking_distance = (current_speed ** 2) / (2 * self.acceleration)
            
            # 3. 先行位置を計算
            #    制動距離を階数に変換（ざっくりと）
            braking_floors = math.ceil(braking_distance / self.get_distance(1, 2)) # 階高は一定と仮定
            advanced_position = physical_floor + direction * braking_floors
            
            # 階の範囲内に収める
            advanced_position = max(1, min(self.num_floors - 1, advanced_position))

            # 4. タイムラインに記録
            time_at_this_floor = self._calculate_travel_time(dist_from_start)
            time_delta = time_at_this_floor - last_time

            if time_delta > 1e-6:
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

# --- このファイルのテスト用コード ---
if __name__ == '__main__':
    floor_heights_test = [0] + [i * 3.5 for i in range(1, 11)] 
    max_speed_test = 4.0 # ちょっと速めにしてみる
    acceleration_test = 1.0

    engine = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test)
    profiles = engine.precompute_flight_profiles()

    print("\n--- Sample Flight Profile: 1F -> 10F ---")
    profile_1_10 = profiles[(1, 10)]
    print(f"Total time: {profile_1_10['total_time']:.2f}s")
    current_time = 0
    for event in profile_1_10['timeline']:
        current_time += event['time_delta']
        phys_pos = event['physical_floor']
        adv_pos = event['advanced_position']
        print(f"  - T={current_time:.2f}s: Physical Pos @ {phys_pos}F -> Advanced Pos is {adv_pos}F")

