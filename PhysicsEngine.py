import math
import numpy as np
import matplotlib.pyplot as plt
import sympy as sp

class PhysicsEngine:
    """
    [v21.2] Format timeline numerical values for beautiful log output
    """
    def __init__(self, floor_heights: list, max_speed: float, acceleration: float, jerk: float):
        self.floor_heights = floor_heights
        self.max_speed = max_speed
        self.acceleration = acceleration
        self.jerk = jerk
        self.num_floors = len(floor_heights)
        self.flight_profiles = {}
        
        # [Realistic flight time calculation] Pre-computation tables
        self.cruise_table = {}      # Cruise time table
        self.brake_table = {}       # Brake time table
        self.flight_time_table = {} # Total flight time table
        
        # Delay time parameters (realistic flight time calculation)
        self.start_response_time = 0.2   # Response time (200ms)
        self.start_delay_time = 0.2   # Start delay time  
        self.stop_adjustable_time = 0.0   # Stop adjustment time
        self.use_realistic_method = True  # Enable/disable flag for realistic flight time calculation (default: realistic method)

    def get_distance(self, floor1, floor2):
        return abs(self.floor_heights[floor1] - self.floor_heights[floor2])

    def precompute_flight_profiles(self):
        """Maintain existing interface while making internal implementation selectable"""
        if self.use_realistic_method:
            # [Realistic flight time calculation] Use new implementation
            self.precompute_flight_tables()
            
            # Generate profiles in existing format (for compatibility)
            for start_floor in range(1, self.num_floors):
                for end_floor in range(1, self.num_floors):
                    if start_floor != end_floor:
                        profile = self._build_timeline_from_table(start_floor, end_floor)
                        self.flight_profiles[(start_floor, end_floor)] = profile
            
            print("[PhysicsEngine] Flight profiles computed using realistic method.")
            return self.flight_profiles
        else:
            # Use SymPy implementation
            print("[PhysicsEngine] Pre-computing all S-curve flight profiles...")
            validation_errors = []
            
            for start_floor in range(1, self.num_floors):
                for end_floor in range(1, self.num_floors):
                    if start_floor == end_floor:
                        continue
                    
                    profile = self._calculate_s_curve_profile(start_floor, end_floor)
                    self.flight_profiles[(start_floor, end_floor)] = profile
                    
                    # Execute detailed validation
                    errors = self._detailed_validation(profile, start_floor, end_floor)
                    if errors:
                        validation_errors.extend(errors)
            
            print("[PhysicsEngine] All flight profiles computed.")
            
            # Report validation results
            if validation_errors:
                print(f"[PhysicsEngine] WARNING: Found {len(validation_errors)} validation issues:")
                for error in validation_errors[:10]:  # Display only first 10
                    print(f"   {error}")
                if len(validation_errors) > 10:
                    print(f"   ... and {len(validation_errors) - 10} more issues")
            else:
                print("[PhysicsEngine] All flight profiles passed validation.")
                
            return self.flight_profiles

    def _calculate_s_curve_profile(self, start_floor, end_floor):
        """
        Calculate S-curve velocity profile timeline using SymPy.
        """
        j_max, a_max, v_max = self.jerk, self.acceleration, self.max_speed
        D = self.get_distance(start_floor, end_floor)

        # --- Calculate time for each phase of S-curve profile ---
        
        # Case 1: Long distance movement reaching maximum speed (v_max)
        dist_to_reach_max_speed = v_max * (v_max / a_max + a_max / j_max)
        
        if D >= dist_to_reach_max_speed:
            t1 = a_max / j_max
            t2 = v_max / a_max - t1
            t4 = (D - dist_to_reach_max_speed) / v_max
        # Case 2: Short distance movement not reaching maximum speed
        else:
            t4 = 0
            # This calculation is complex, so use simplified stable formula
            # Avoid complex calculation to find v_peak
            t_accel_to_v_peak = math.sqrt(D/a_max) if D*j_max < a_max**2 else (a_max/j_max + math.sqrt( (a_max/j_max)**2 + 4*D/a_max ))/2
            v_peak = a_max * (t_accel_to_v_peak - a_max/j_max)
            
            t1 = a_max/j_max
            t2 = v_peak/a_max - t1
            if(t2 < 0):
                t1 = math.sqrt(v_peak/j_max)
                t2 = 0
                
            # Correct minute negative values of t2 in rare cases
            if t2 < 0: t2 = 0

        total_time = 2 * t1 + 2 * t2 + t4

        # --- Define mathematical expressions once in SymPy ---
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

        # --- Ultra-high-speed support: Convert expressions to fast numerical functions ---
        v_func = sp.lambdify(t, v_t, 'numpy')
        d_func = sp.lambdify(t, d_t, 'numpy')

        # --- Generate timeline ---
        timeline = []
        direction = 1 if end_floor > start_floor else -1
        
        dt = 0.05 # Time step can be slightly coarse
        last_timeline_time = 0
        last_floor = -1
        last_adv_floor = -1

        time_points = np.arange(0, total_time, dt)
        if total_time not in time_points:
            time_points = np.append(time_points, total_time) # Add endpoint at the end

        last_advanced_position = start_floor  # Previous value to maintain continuity
        
        for time_step in time_points:
            dist = d_func(time_step)
            vel = v_func(time_step)
            
            physical_floor = start_floor + direction * math.floor(dist / self.get_distance(1, 2) + 1e-9)
            physical_floor = max(1, min(self.num_floors, physical_floor))

            # Improve calculation accuracy of advanced position
            dist_to_stop = (vel**2) / (2 * a_max) if a_max > 0 else 0
            adv_dist = dist + dist_to_stop
            advanced_position = start_floor + direction * math.ceil(adv_dist / self.get_distance(1, 2) - 1e-9)
            advanced_position = max(1, min(self.num_floors, advanced_position))
            
            # Enforce continuity: prevent reversal from previous value
            original_advanced_position = advanced_position
            if direction == 1:  # Ascending
                advanced_position = max(advanced_position, last_advanced_position)
            elif direction == -1:  # Descending
                advanced_position = min(advanced_position, last_advanced_position)
            
            # Output error only when correction is applied
            if original_advanced_position != advanced_position:
                print(f"[PhysicsEngine] WARNING: Applied fix {start_floor}F->{end_floor}F at time={time_step:.3f}, {original_advanced_position}->{advanced_position}")
            
            # [Fix] Also enforce continuity of physical floor
            if direction == 1:  # Ascending
                physical_floor = max(physical_floor, start_floor)
            elif direction == -1:  # Descending
                physical_floor = min(physical_floor, start_floor)
            
            # Detect abnormal values
            if start_floor != end_floor:
                if direction == 1 and advanced_position < start_floor:
                    print(f"[PhysicsEngine] ERROR: UP movement but adv_pos={advanced_position} < start={start_floor}")
                elif direction == -1 and advanced_position > start_floor:
                    print(f"[PhysicsEngine] ERROR: DOWN movement but adv_pos={advanced_position} > start={start_floor}")

            # Update previous value
            last_advanced_position = advanced_position

            if physical_floor != last_floor or advanced_position != last_adv_floor or time_step == 0:
                time_delta = time_step - last_timeline_time
                if time_delta > 1e-9:
                    timeline.append({
                        "time_delta": float(time_delta), # Convert to float here
                        "physical_floor": int(physical_floor),
                        "advanced_position": int(advanced_position)
                    })
                    last_timeline_time = time_step
                
                last_floor = physical_floor
                last_adv_floor = advanced_position

        # Adjust remaining time of last event
        if timeline:
            current_total_time = sum(e['time_delta'] for e in timeline)
            remaining_time = total_time - current_total_time
            if remaining_time > 1e-9:
                 timeline.append({
                        "time_delta": float(remaining_time), # Convert to float here
                        "physical_floor": int(end_floor),
                        "advanced_position": int(end_floor)
                    })

        # Validate timeline validity
        self._validate_timeline(timeline, start_floor, end_floor)
        
        # Continuity check (output errors only)
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
        Verify that the timeline's advanced_position is physically correct
        """
        if not timeline:
            return
            
        direction = 1 if end_floor > start_floor else -1
        prev_advanced_position = None
        
        for i, event in enumerate(timeline):
            current_advanced_position = event['advanced_position']
            
            # Skip first event
            if prev_advanced_position is not None:
                # Values should increase during ascent, decrease during descent
                if direction == 1:  # Ascending
                    if current_advanced_position < prev_advanced_position:
                        print(f"[PhysicsEngine] WARNING: Advanced position decreased during UP movement!")
                        print(f"   Event {i}: {prev_advanced_position} -> {current_advanced_position}")
                        print(f"   Start: {start_floor}F, End: {end_floor}F")
                elif direction == -1:  # Descending
                    if current_advanced_position > prev_advanced_position:
                        print(f"[PhysicsEngine] WARNING: Advanced position increased during DOWN movement!")
                        print(f"   Event {i}: {prev_advanced_position} -> {current_advanced_position}")
                        print(f"   Start: {start_floor}F, End: {end_floor}F")
            
            prev_advanced_position = current_advanced_position

    def _detailed_validation(self, profile, start_floor, end_floor):
        """
        Execute more detailed validation and return a list of error messages
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
            
            # Range check
            if not (1 <= current_advanced_position <= self.num_floors):
                errors.append(f"Advanced position out of range: {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
            
            if not (1 <= current_physical_floor <= self.num_floors):
                errors.append(f"Physical floor out of range: {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
            
            # Monotonicity check
            if prev_advanced_position is not None:
                if direction == 1 and current_advanced_position < prev_advanced_position:
                    errors.append(f"Advanced position decreased during UP: {prev_advanced_position} -> {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
                elif direction == -1 and current_advanced_position > prev_advanced_position:
                    errors.append(f"Advanced position increased during DOWN: {prev_advanced_position} -> {current_advanced_position} (event {i}, {start_floor}F->{end_floor}F)")
            
            # Physical consistency check
            if prev_physical_floor is not None:
                if direction == 1 and current_physical_floor < prev_physical_floor:
                    errors.append(f"Physical floor decreased during UP: {prev_physical_floor} -> {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
                elif direction == -1 and current_physical_floor > prev_physical_floor:
                    errors.append(f"Physical floor increased during DOWN: {prev_physical_floor} -> {current_physical_floor} (event {i}, {start_floor}F->{end_floor}F)")
            
            prev_advanced_position = current_advanced_position
            prev_physical_floor = current_physical_floor
        
        # Final position check
        if timeline:
            final_event = timeline[-1]
            if final_event['physical_floor'] != end_floor:
                errors.append(f"Final physical floor mismatch: expected {end_floor}, got {final_event['physical_floor']} ({start_floor}F->{end_floor}F)")
            if final_event['advanced_position'] != end_floor:
                errors.append(f"Final advanced position mismatch: expected {end_floor}, got {final_event['advanced_position']} ({start_floor}F->{end_floor}F)")
        
        return errors

    # ========== [Realistic Method] ==========
    
    def _calc_flight_time(self, start_floor, end_floor):
        """Realistic flight time calculation"""
        span = self.get_distance(start_floor, end_floor) * 1000  # Convert to mm units
        if span == 0:
            return 0.1, 0  # Same floor case
        
        # Optimal speed calculation
        alpha = self.acceleration * 1000  # Convert to mm/s²
        beta = self.jerk * 1000          # Convert to mm/s³
        rated_vel = self.max_speed * 60   # Convert to m/min units
        
        t = (alpha * alpha) / (beta * 2)
        optimal_vel = ((t*t + alpha * span) ** 0.5 - t) * 60 / 1000
        
        # Rated speed limitation
        if optimal_vel > rated_vel:
            vel = rated_vel
            dtime = alpha * 1000 / beta  # Acceleration time when reaching rated speed
        else:
            vel = optimal_vel
            dtime = 2 * alpha * 1000 / beta  # Acceleration time under jerk limitation
        
        # Total travel time calculation (realistic flight time calculation)
        accel_time = vel * 1000 * 1000 / (alpha * 60)
        jerk_time = alpha * 1000 / beta
        travel_time = span * 60 / vel
        
        total_time_ms = self.start_delay_time * 1000 + travel_time + accel_time + jerk_time + self.stop_adjustable_time * 1000
        total_time = total_time_ms / 1000  # Convert to seconds
        
        return max(0.1, total_time), vel
    
    def _calc_brake_time(self, vel):
        """Brake time calculation"""
        if vel == 0:
            return 0.1
        
        alpha = self.acceleration * 1000
        beta = self.jerk * 1000
        
        # Brake time = same as acceleration time
        brake_time_ms = vel * 1000 * 1000 / (alpha * 60) + alpha * 1000 / beta
        return max(0.1, brake_time_ms / 1000)
    
    def precompute_flight_tables(self):
        """
        Realistic pre-computation table method
        

## cruise_table array: "Additional time" for each segment
What is stored in cruise_table[(i, j)] is not the total travel time from floor i to floor j.
This is the "time it takes to travel from passing floor j-1 to arriving at floor j (additional time)"
under the assumption that the elevator departs from floor i and travels non-stop.

To use an analogy, it's like train segment times.
Suppose there's a non-stop "Nozomi" train from Tokyo Station to Hakata Station.
cruise_table[(Tokyo, Nagoya)] = Travel time from Tokyo → Nagoya
cruise_table[(Tokyo, Kyoto)] = Additional time from passing Nagoya to arriving at Kyoto
cruise_table[(Tokyo, Shin-Osaka)] = Additional time from passing Kyoto to arriving at Shin-Osaka

In this way, depending on where the departure station (i) is, the speed of passing through intermediate sections changes,
so the values of cruise_table[(Kyoto, Shin-Osaka)] and cruise_table[(Tokyo, Shin-Osaka)] are completely different.
The latter takes less time because it's already traveling at high speed.

To calculate this "additional time", the code uses a variable called cruise_time to
remember (accumulate) the time taken so far and subtract it from the total time.

## brake_table array: Final "deceleration time"
brake_table[(i, j)] is simpler.
This is the time it takes from when the elevator starts decelerating to arrive at destination floor j
after departing from floor i, until it comes to a complete stop - the duration of the final deceleration phase.

Using the train analogy from earlier, brake_table[(Tokyo, Hakata)] corresponds to the time it takes
from starting to brake to arrive at Hakata Station until coming to a complete stop at the platform.

## Summary: Relationship between the two
Using these two arrays, the simulator can easily calculate the total travel time from floor i to floor j.
For example, the total travel time from 1st floor to 4th floor would be:

Total travel time (1→4F) = cruise_table[(1,2)] + cruise_table[(1,3)] + cruise_table[(1,4)] + brake_table[(1,4)]
cruise_table[(1,2)]: Time to reach 2nd floor from 1st floor
cruise_table[(1,3)]: Time to reach 3rd floor after passing 2nd floor (while traveling from 1st floor...)
cruise_table[(1,4)]: Time to reach 4th floor after passing 3rd floor (while traveling from 1st floor...)
brake_table[(1,4)]: Final deceleration time to arrive at 4th floor

In this way, by adding up the "additional time" to each passing floor and the "deceleration time" at the destination floor,
the entire flight time is constructed.
        """
        print("[PhysicsEngine] Computing flight tables (realistic style)...")
        
        for i in range(1, self.num_floors):
            # Ascending direction calculation
            cruise_time = 0
            for j in range(i + 1, self.num_floors):
                total_time, vel = self._calc_flight_time(i, j)
                brake_time = self._calc_brake_time(vel)
                
                # Cruise time = grace time until deceleration starts
                #
                # Total travel time (1→4F) = cruise_table[(1,2)] + cruise_table[(1,3)] 
                #                           + cruise_table[(1,4)] + brake_table[(1,4)]
                # cruise_table[(1,2)]: Time to reach 2nd floor from 1st floor
                # cruise_table[(1,3)]: Time to reach 3rd floor after passing 2nd floor (while traveling from 1st floor...)
                # cruise_table[(1,4)]: Time to reach 4th floor after passing 3rd floor (while traveling from 1st floor...)
                # brake_table[(1,4)]: Final deceleration time to arrive at 4th floor
                cruise_duration = total_time - cruise_time - brake_time
                
                self.cruise_table[(i, j)] = max(0.05, cruise_duration)
                self.brake_table[(i, j)] = brake_time
                self.flight_time_table[(i, j)] = total_time
                
                cruise_time += self.cruise_table[(i, j)]
            
            # Descending direction calculation
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
        """Build timeline from pre-computed tables"""
        if start_floor == end_floor:
            return {'total_time': 0.1, 'timeline': []}
        
        timeline = []
        direction = 1 if end_floor > start_floor else -1
        
        # Segment division for movement at each floor
        current_floor = start_floor
        while current_floor != end_floor:
            next_floor = current_floor + direction
            
            # Get time from table
            cruise_time = self.cruise_table.get((start_floor, next_floor), 0.1)
            
            timeline.append({
                'time_delta': cruise_time,
                'physical_floor': current_floor,
                'advanced_position': next_floor
            })
            
            current_floor = next_floor
        
        # Final braking segment
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
        """Modified to enable S-curve profile visualization"""
        profile = self.flight_profiles.get((start_floor, end_floor))
        if not profile:
            print(f"Profile for {start_floor}F -> {end_floor}F not found.")
            return

        total_time = profile['total_time']
        
        # --- Reconstruct SymPy expressions (for plotting) ---
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
        
        # --- Execute plotting ---
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

# --- Test code for this file ---
if __name__ == '__main__':
    floor_heights_test = [0] + [i * 3.5 for i in range(1, 11)] 
    max_speed_test = 2.5
    acceleration_test = 1.0
    jerk_test = 1.0

    print("=== Traditional method (SymPy) test ===")
    engine_old = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test, jerk_test)
    engine_old.use_realistic_method = False
    profiles_old = engine_old.precompute_flight_profiles()

    print("\n=== New method (realistic flight time calculation) test ===")
    engine_new = PhysicsEngine(floor_heights_test, max_speed_test, acceleration_test, jerk_test)
    engine_new.use_realistic_method = True
    profiles_new = engine_new.precompute_flight_profiles()

    print("\n--- Comparison test: 1F -> 10F ---")
    profile_old = profiles_old.get((1, 10))
    profile_new = profiles_new.get((1, 10))
    
    if profile_old and profile_new:
        print(f"Traditional method: Total time: {profile_old['total_time']:.2f}s, Events: {len(profile_old['timeline'])}")
        print(f"New method:         Total time: {profile_new['total_time']:.2f}s, Events: {len(profile_new['timeline'])}")
        
        # Timeline comparison
        print("\n--- Timeline comparison (first 5 events) ---")
        print("Traditional method:")
        for i, event in enumerate(profile_old['timeline'][:5]):
            print(f"  Event {i}: Δt={event['time_delta']:.3f}s, Floor={event['physical_floor']}, Adv={event['advanced_position']}")
        
        print("New method:")
        for i, event in enumerate(profile_new['timeline'][:5]):
            print(f"  Event {i}: Δt={event['time_delta']:.3f}s, Floor={event['physical_floor']}, Adv={event['advanced_position']}")
    
    print("\n--- Realistic pre-computation table contents (sample) ---")
    print("Cruise table (1F -> ascending):")
    for j in range(2, min(6, engine_new.num_floors)):
        cruise_time = engine_new.cruise_table.get((1, j), 0)
        brake_time = engine_new.brake_table.get((1, j), 0)
        total_time = engine_new.flight_time_table.get((1, j), 0)
        print(f"  1F -> {j}F: cruise={cruise_time:.3f}s, brake={brake_time:.3f}s, total={total_time:.3f}s")
    
    # Graph display (traditional method only)
    # engine_old.plot_velocity_profile(1, 10)
    # engine_old.plot_velocity_profile(1, 3)

