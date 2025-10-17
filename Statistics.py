import simpy
import matplotlib.pyplot as plt
import re

class Statistics:
    """
    Receives all communications and
    analyzes and records necessary information as an independent "recorder".
    """
    def __init__(self, env, broadcast_pipe):
        self.env = env
        self.broadcast_pipe = broadcast_pipe
        self.elevator_trajectories = {}
        self.hall_calls_history = {}  # Hall calls history by elevator
        self.car_calls_history = {}   # Car calls history by elevator
        self.hall_call_off_history = {}  # Hall call OFF events history
        self.car_call_off_history = {}   # Car call OFF events history
        self.door_events_history = {}  # Door events history by elevator

    def start_listening(self):
        """
        Main process to start intercepting global broadcasts.
        """
        while True:
            data = yield self.broadcast_pipe.get()
            
            topic = data.get('topic', '')
            message = data.get('message', {})

            # Record only advanced position from elevator status reports
            status_match = re.search(r'elevator/(.*?)/status', topic)
            if status_match and 'advanced_position' in message:
                elevator_name = status_match.group(1)
                if elevator_name not in self.elevator_trajectories:
                    self.elevator_trajectories[elevator_name] = []
                
                timestamp = message.get('timestamp')
                advanced_position = message.get('advanced_position')

                # Record if not exactly the same as the last data point
                if not self.elevator_trajectories[elevator_name] or self.elevator_trajectories[elevator_name][-1] != (timestamp, advanced_position):
                    self.elevator_trajectories[elevator_name].append((timestamp, advanced_position))
            
            # Record hall_calls information
            hall_calls_match = re.search(r'elevator/(.*?)/hall_calls', topic)
            if hall_calls_match:
                elevator_name = hall_calls_match.group(1)
                if elevator_name not in self.hall_calls_history:
                    self.hall_calls_history[elevator_name] = []
                
                timestamp = message.get('timestamp')
                hall_calls_up = message.get('hall_calls_up', [])
                hall_calls_down = message.get('hall_calls_down', [])
                
                # Record hall_calls information
                self.hall_calls_history[elevator_name].append({
                    'timestamp': timestamp,
                    'hall_calls_up': hall_calls_up.copy(),
                    'hall_calls_down': hall_calls_down.copy()
                })
            
            # Record new hall_call registrations (for visualization)
            new_hall_call_match = re.search(r'hall_button/floor_(.*?)/new_hall_call', topic)
            if new_hall_call_match:
                floor = int(new_hall_call_match.group(1))
                
                # Record only newly registered hall_calls
                timestamp = message.get('timestamp')
                direction = message.get('direction')
                passenger_name = message.get('passenger_name')
                
                if timestamp is not None and direction is not None:
                    # Add as new registration to hall_calls_history (unified as elevator name 'ALL')
                    elevator_name = 'ALL'  # Hall Calls are not elevator-specific
                    if elevator_name not in self.hall_calls_history:
                        self.hall_calls_history[elevator_name] = []
                    
                    # Data structure dedicated to new registrations
                    new_hall_call_data = {
                        'timestamp': timestamp,
                        'floor': floor,
                        'direction': direction,
                        'passenger_name': passenger_name,
                        'is_new_registration': True  # New registration flag
                    }
                    self.hall_calls_history[elevator_name].append(new_hall_call_data)
            
            # Record new car_call registrations (for visualization)
            new_car_call_match = re.search(r'elevator/(.*?)/new_car_call', topic)
            if new_car_call_match:
                elevator_name = new_car_call_match.group(1)
                if elevator_name not in self.car_calls_history:
                    self.car_calls_history[elevator_name] = []
                
                # Record only newly registered car_calls
                timestamp = message.get('timestamp')
                destination = message.get('destination')
                passenger_name = message.get('passenger_name')
                
                if destination is not None and timestamp is not None:
                    self.car_calls_history[elevator_name].append({
                        'timestamp': timestamp,
                        'car_calls': [destination],  # Only the one newly registered floor
                        'passenger_name': passenger_name
                    })
            
            # Record hall call OFF events (for visualization)
            hall_call_off_match = re.search(r'hall_button/floor_(.*?)/call_off', topic)
            if hall_call_off_match:
                floor = int(hall_call_off_match.group(1))
                
                timestamp = message.get('timestamp')
                direction = message.get('direction')
                action = message.get('action')
                
                if timestamp is not None and direction is not None and action == 'OFF':
                    # Store hall call OFF events under 'ALL' key (same as ON events)
                    elevator_name = 'ALL'
                    if elevator_name not in self.hall_call_off_history:
                        self.hall_call_off_history[elevator_name] = []
                    
                    hall_call_off_data = {
                        'timestamp': timestamp,
                        'floor': floor,
                        'direction': direction,
                        'action': 'OFF'
                    }
                    self.hall_call_off_history[elevator_name].append(hall_call_off_data)
            
            # Record car call OFF events (for visualization)
            car_call_off_match = re.search(r'elevator/(.*?)/car_call_off', topic)
            if car_call_off_match:
                elevator_name = car_call_off_match.group(1)
                if elevator_name not in self.car_call_off_history:
                    self.car_call_off_history[elevator_name] = []
                
                timestamp = message.get('timestamp')
                destination = message.get('destination')
                action = message.get('action')
                
                if destination is not None and timestamp is not None and action == 'OFF':
                    self.car_call_off_history[elevator_name].append({
                        'timestamp': timestamp,
                        'destination': destination,
                        'action': 'OFF'
                    })
            
            # Record door events (for visualization)
            door_events_match = re.search(r'elevator/(.*?)/door_events', topic)
            if door_events_match:
                elevator_name = door_events_match.group(1)
                if elevator_name not in self.door_events_history:
                    self.door_events_history[elevator_name] = []
                
                timestamp = message.get('timestamp')
                event_type = message.get('event_type')
                floor = message.get('floor')
                door_id = message.get('door_id')
                
                if timestamp is not None and event_type is not None:
                    self.door_events_history[elevator_name].append({
                        'timestamp': timestamp,
                        'event_type': event_type,
                        'floor': floor,
                        'door_id': door_id
                    })

    def plot_trajectory_diagram(self):
        """Draw trajectory diagram after simulation ends"""
        print("\n--- Plotting: Elevator Trajectory Diagram ---")
        plt.figure(figsize=(14, 8))

        for name, trajectory in self.elevator_trajectories.items():
            if not trajectory: continue
            
            sorted_trajectory = sorted(trajectory, key=lambda x: x[0])
            times, floors = zip(*sorted_trajectory)
            
            plt.step(times, floors, where='post', label=name)
            
            # Draw hall_calls arrows
            self._plot_hall_calls_arrows(name)
            
            # Draw car_calls circles
            self._plot_car_calls_circles(name)
            
            # Draw hall_calls OFF events
            self._plot_hall_calls_off_events(name)
            
            # Draw car_calls OFF events
            self._plot_car_calls_off_events(name)
            
            # Draw door events
            self._plot_door_events(name)

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
        """Draw only new hall_call registrations with arrows"""
        # New registration data is stored under 'ALL' key
        if 'ALL' not in self.hall_calls_history:
            return
        
        # Track already drawn (timestamp, floor, direction) combinations
        plotted_positions = set()
        
        for hall_call_data in self.hall_calls_history['ALL']:
            # Process only data with new registration flag
            if not hall_call_data.get('is_new_registration', False):
                continue
                
            timestamp = hall_call_data['timestamp']
            floor = hall_call_data['floor']
            direction = hall_call_data['direction']
            
            position_key = (round(timestamp, 2), floor, direction)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                if direction == 'UP':
                    # Upward arrow (green)
                    plt.annotate('↑', (timestamp, floor), 
                               fontsize=12, color='green', fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor='lightgreen', alpha=0.7))
                elif direction == 'DOWN':
                    # Downward arrow (red)
                    plt.annotate('↓', (timestamp, floor), 
                               fontsize=12, color='red', fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor='lightcoral', alpha=0.7))
                
                plotted_positions.add(position_key)
    
    def _plot_car_calls_circles(self, elevator_name):
        """Draw car_calls circles for the specified elevator"""
        if elevator_name not in self.car_calls_history:
            return
        
        # Track already drawn (timestamp, floor) combinations
        plotted_positions = set()
        
        for car_call_data in self.car_calls_history[elevator_name]:
            timestamp = car_call_data['timestamp']
            car_calls = car_call_data['car_calls']
            
            # Display car_calls with circles (blue)
            for floor in car_calls:
                position_key = (round(timestamp, 2), floor)  # Round time for duplicate detection
                
                if position_key not in plotted_positions:
                    plt.scatter(timestamp, floor, 
                              s=80, c='blue', marker='o', alpha=0.7, 
                              edgecolors='darkblue', linewidth=1.5,
                              label='Car Calls' if not hasattr(self, '_car_calls_legend_added') else "")
                    plotted_positions.add(position_key)
        
        # Prevent duplicate legends
        if not hasattr(self, '_car_calls_legend_added'):
            self._car_calls_legend_added = True
    
    def _plot_hall_calls_off_events(self, elevator_name):
        """Draw hall call OFF events with X marks"""
        # OFF events are stored under 'ALL' key
        if 'ALL' not in self.hall_call_off_history:
            return
        
        # Track already drawn (timestamp, floor, direction) combinations
        plotted_positions = set()
        
        for hall_call_off_data in self.hall_call_off_history['ALL']:
            timestamp = hall_call_off_data['timestamp']
            floor = hall_call_off_data['floor']
            direction = hall_call_off_data['direction']
            
            position_key = (round(timestamp, 2), floor, direction)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                if direction == 'UP':
                    # Upward OFF mark (dark green X)
                    plt.annotate('✕', (timestamp, floor), 
                               fontsize=10, color='darkgreen', fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.1', facecolor='lightgreen', alpha=0.5))
                elif direction == 'DOWN':
                    # Downward OFF mark (dark red X)
                    plt.annotate('✕', (timestamp, floor), 
                               fontsize=10, color='darkred', fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.1', facecolor='lightcoral', alpha=0.5))
                
                plotted_positions.add(position_key)
    
    def _plot_car_calls_off_events(self, elevator_name):
        """Draw car call OFF events with X marks"""
        if elevator_name not in self.car_call_off_history:
            return
        
        # Track already drawn (timestamp, floor) combinations
        plotted_positions = set()
        
        for car_call_off_data in self.car_call_off_history[elevator_name]:
            timestamp = car_call_off_data['timestamp']
            destination = car_call_off_data['destination']
            
            position_key = (round(timestamp, 2), destination)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                # Car call OFF mark (dark blue X)
                plt.scatter(timestamp, destination, 
                          s=60, c='darkblue', marker='x', alpha=0.8, 
                          linewidth=2,
                          label='Car Calls OFF' if not hasattr(self, '_car_calls_off_legend_added') else "")
                plotted_positions.add(position_key)
        
        # Prevent duplicate legends
        if not hasattr(self, '_car_calls_off_legend_added'):
            self._car_calls_off_legend_added = True

    def _plot_door_events(self, elevator_name):
        """Draw door events with different markers for each event type"""
        if elevator_name not in self.door_events_history:
            return
        
        # Track already drawn (timestamp, floor, event_type) combinations
        plotted_positions = set()
        
        # Vertical offset for door events (shift slightly above floor)
        door_event_offset = 0.15
        
        for door_event in self.door_events_history[elevator_name]:
            timestamp = door_event['timestamp']
            floor = door_event['floor']
            event_type = door_event['event_type']
            
            position_key = (round(timestamp, 2), floor, event_type)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                if event_type == "DOOR_OPENING_START":
                    # Door opening start (green triangle) - slightly above stop position
                    plt.scatter(timestamp, floor + door_event_offset, 
                              s=100, facecolors='none', marker='<', alpha=0.8, 
                              edgecolors='green', linewidth=1.5,
                              label='Door Opening Start' if not hasattr(self, '_door_opening_start_legend_added') else "")
                    if not hasattr(self, '_door_opening_start_legend_added'):
                        self._door_opening_start_legend_added = True
                        
                elif event_type == "DOOR_OPENING_COMPLETE":
                    # Door opening complete (green square) - slightly above stop position
                    plt.scatter(timestamp, floor + door_event_offset, 
                              s=100, facecolors='none', marker='>', alpha=0.8, 
                              edgecolors='green', linewidth=1.5,
                              label='Door Opening Complete' if not hasattr(self, '_door_opening_complete_legend_added') else "")
                    if not hasattr(self, '_door_opening_complete_legend_added'):
                        self._door_opening_complete_legend_added = True
                        
                elif event_type == "DOOR_CLOSING_START":
                    # Door closing start (red triangle) - slightly above stop position
                    plt.scatter(timestamp, floor + door_event_offset, 
                              s=100, facecolors='none', marker='>', alpha=0.8, 
                              edgecolors='red', linewidth=1.5,
                              label='Door Closing Start' if not hasattr(self, '_door_closing_start_legend_added') else "")
                    if not hasattr(self, '_door_closing_start_legend_added'):
                        self._door_closing_start_legend_added = True
                        
                elif event_type == "DOOR_CLOSING_COMPLETE":
                    # Door closing complete (red square) - slightly above stop position
                    plt.scatter(timestamp, floor + door_event_offset, 
                              s=100, facecolors='none', marker='<', alpha=0.8, 
                              edgecolors='red', linewidth=1.5,
                              label='Door Closing Complete' if not hasattr(self, '_door_closing_complete_legend_added') else "")
                    if not hasattr(self, '_door_closing_complete_legend_added'):
                        self._door_closing_complete_legend_added = True
                
                plotted_positions.add(position_key)