from .statistics import Statistics
import re

class RealtimePerformanceMonitor(Statistics):
    """
    Real-time performance monitoring using SENSOR DATA ONLY.
    
    Features:
    - Compatible with real hardware
    - Uses only observable sensor data
    - Estimates aggregate metrics (not per-passenger)
    
    Available sensors:
    - Hall buttons (press time)
    - Door sensors (open/close time)
    - Weight sensors (passenger count)
    - Position sensors (elevator location)
    
    Use cases:
    - Real building deployments
    - Live performance monitoring
    - Dashboard displays
    - Alert generation
    
    ✅ FULLY compatible with real hardware.
    """
    def __init__(self, env, broadcast_pipe, websocket_server=None):
        super().__init__(env, broadcast_pipe, websocket_server)
        
        # Sensor-based tracking (real hardware compatible)
        self.hall_button_press_times = {}  # {(floor, direction): press_time}
        self.service_times = {}  # {(floor, direction): [(press_time, service_time), ...]}
    
    def start_listening(self):
        """
        Subscribe to sensor-based events and calculate performance metrics.
        
        This extends the parent's start_listening() by adding service time tracking.
        All visualization-related events are handled by the parent class.
        """
        while True:
            data = yield self.broadcast_pipe.get()
            
            topic = data.get('topic', '')
            message = data.get('message', {})
            
            # Track hall button presses for service time calculation
            new_hall_call_match = re.search(r'hall_button/floor_(.*?)/new_hall_call', topic)
            if new_hall_call_match:
                floor = int(new_hall_call_match.group(1))
                direction = message.get('direction')
                timestamp = message.get('timestamp')
                
                if direction and timestamp is not None:
                    key = (floor, direction)
                    # Only record if not already pressed (avoid duplicates)
                    if key not in self.hall_button_press_times:
                        self.hall_button_press_times[key] = timestamp
            
            # Track hall call service completion (button OFF)
            call_off_match = re.search(r'hall_button/floor_(.*?)/call_off', topic)
            if call_off_match:
                floor = int(call_off_match.group(1))
                direction = message.get('direction')
                timestamp = message.get('timestamp')
                action = message.get('action')
                
                if direction and timestamp is not None and action == 'OFF':
                    key = (floor, direction)
                    
                    # Calculate service time if we have the press time
                    if key in self.hall_button_press_times:
                        press_time = self.hall_button_press_times[key]
                        service_time = timestamp - press_time
                        
                        if key not in self.service_times:
                            self.service_times[key] = []
                        
                        self.service_times[key].append((press_time, service_time))
                        
                        # Clear the press time (ready for next call)
                        del self.hall_button_press_times[key]
    
    def print_performance_summary(self):
        """
        Print aggregate performance metrics using sensor data only.
        
        Metrics include:
        - Average service time (button press to service completion)
        - Service time by floor
        - Service time by direction
        - Call volume statistics
        
        ✅ These metrics are REAL HARDWARE COMPATIBLE
        """
        print("\n" + "="*80)
        print("   PERFORMANCE SUMMARY (REAL HARDWARE COMPATIBLE)")
        print("="*80)
        print("✅ These metrics use sensor data only")
        print("✅ Available in real building deployments")
        print("="*80)
        
        if not self.service_times:
            print("\n⚠️  No service time data collected.")
            print("   (Ensure hall buttons are being pressed and serviced)")
            return
        
        # Calculate aggregate statistics
        all_service_times = []
        for key, times_list in self.service_times.items():
            for press_time, service_time in times_list:
                all_service_times.append(service_time)
        
        if all_service_times:
            print(f"\nAggregate Service Time (Hall Button Press → Service Completion):")
            print(f"  Count:   {len(all_service_times):>6} calls")
            print(f"  Average: {sum(all_service_times) / len(all_service_times):>6.2f} seconds")
            print(f"  Min:     {min(all_service_times):>6.2f} seconds")
            print(f"  Max:     {max(all_service_times):>6.2f} seconds")
        
        # Per-floor analysis
        print(f"\nService Time by Floor:")
        floor_data = {}
        for (floor, direction), times_list in self.service_times.items():
            if floor not in floor_data:
                floor_data[floor] = []
            for press_time, service_time in times_list:
                floor_data[floor].append(service_time)
        
        for floor in sorted(floor_data.keys()):
            floor_times = floor_data[floor]
            avg_time = sum(floor_times) / len(floor_times)
            print(f"  Floor {floor:>2}: {avg_time:>6.2f}s (n={len(floor_times):>3})")
        
        # Per-direction analysis
        print(f"\nService Time by Direction:")
        direction_data = {'UP': [], 'DOWN': []}
        for (floor, direction), times_list in self.service_times.items():
            for press_time, service_time in times_list:
                if direction in direction_data:
                    direction_data[direction].append(service_time)
        
        for direction, times in direction_data.items():
            if times:
                avg_time = sum(times) / len(times)
                print(f"  {direction:>4}: {avg_time:>6.2f}s (n={len(times):>3})")
        
        print("="*80)
    
    def get_realtime_metrics(self):
        """
        Get current metrics for dashboard display.
        
        Returns:
            dict: Real-time metrics dictionary with recent performance data
        """
        # Calculate recent service times (last 5 minutes)
        recent_threshold = self.env.now - 300  # 5 minutes
        recent_service_times = []
        
        for key, times_list in self.service_times.items():
            for press_time, service_time in times_list:
                if press_time >= recent_threshold:
                    recent_service_times.append(service_time)
        
        return {
            'average_service_time': sum(recent_service_times) / len(recent_service_times) if recent_service_times else None,
            'total_calls_served': len(recent_service_times),
            'timestamp': self.env.now,
            'pending_calls': len(self.hall_button_press_times)  # Calls not yet serviced
        }

