import simpy
import matplotlib.pyplot as plt
import re
import json
import asyncio
import threading
from datetime import datetime

class Statistics:
    """
    Receives all communications and
    analyzes and records necessary information as an independent "recorder".
    Also sends real-time data to WebSocket server for visualization.
    Collects all events in JSON Lines format for offline playback.
    """
    def __init__(self, env, broadcast_pipe, websocket_server=None):
        self.env = env
        self.broadcast_pipe = broadcast_pipe
        self.websocket_server = websocket_server  # Optional WebSocket server reference
        self.elevator_trajectories = {}
        self.hall_calls_history = {}  # Hall calls history by elevator
        self.car_calls_history = {}   # Car calls history by elevator
        self.hall_call_off_history = {}  # Hall call OFF events history
        self.car_call_off_history = {}   # Car call OFF events history
        self.door_events_history = {}  # Door events history by elevator
        self.passenger_count_history = {}  # Passenger count history by elevator for visualization
        self.waiting_passengers = {}  # Current waiting passengers by floor and direction
        
        # Track current elevator states for real-time updates
        self.current_elevator_states = {}  # {elevator_name: {floor, state, passengers, etc.}}
        
        # JSON Lines event log for offline playback
        self.event_log = []  # List of events in standardized format
        self.simulation_metadata = {}  # Metadata about the simulation
        
        # Note: Passenger-specific metrics are now handled by SimulationStatistics
        # This base class only handles sensor-based data collection
    
    def _send_to_websocket(self, message):
        """
        Send message to WebSocket server (if connected).
        Thread-safe method to queue messages for WebSocket broadcast.
        """
        if self.websocket_server:
            try:
                # Queue message using thread-safe queue
                self.websocket_server.queue_message(message)
            except Exception as e:
                # Silently ignore errors to not disrupt simulation
                pass
    
    def _add_event_log(self, event_type, event_data):
        """
        Add an event to the JSON Lines log.
        
        Args:
            event_type (str): Type of event (e.g., 'elevator_status', 'hall_call', etc.)
            event_data (dict): Event-specific data
        """
        event = {
            "time": self.env.now,
            "type": event_type,
            "data": event_data
        }
        self.event_log.append(event)
    
    def set_simulation_metadata(self, metadata):
        """
        Set simulation metadata (called before simulation starts).
        
        Args:
            metadata (dict): Simulation configuration (num_floors, elevators, etc.)
        """
        self.simulation_metadata = {
            "format_version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "config": metadata
        }

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
                
                # Record passenger count for visualization
                passengers_count = message.get('passengers_count', 0)
                max_capacity = message.get('max_capacity', 50)
                if elevator_name not in self.passenger_count_history:
                    self.passenger_count_history[elevator_name] = []
                
                # Record passenger count changes
                if not self.passenger_count_history[elevator_name] or self.passenger_count_history[elevator_name][-1] != (timestamp, passengers_count, max_capacity):
                    self.passenger_count_history[elevator_name].append((timestamp, passengers_count, max_capacity))
                
                # Update current state and send to WebSocket
                current_floor = message.get('current_floor', advanced_position)
                state = message.get('state', 'IDLE')
                passengers_count = message.get('passengers_count', 0)
                max_capacity = message.get('max_capacity', 10)
                num_floors = message.get('num_floors', 10)
                
                self.current_elevator_states[elevator_name] = {
                    'elevator_name': elevator_name,
                    'floor': current_floor,
                    'state': state,
                    'passengers': passengers_count,
                    'capacity': max_capacity,
                    'num_floors': num_floors,
                    'timestamp': timestamp,
                    'car_calls': self.current_elevator_states.get(elevator_name, {}).get('car_calls', []),  # Preserve car_calls
                    'hall_calls_up': self.current_elevator_states.get(elevator_name, {}).get('hall_calls_up', []),  # Preserve hall_calls_up
                    'hall_calls_down': self.current_elevator_states.get(elevator_name, {}).get('hall_calls_down', [])  # Preserve hall_calls_down
                }
                
                # Log event for JSON Lines
                self._add_event_log('elevator_status', {
                    'elevator': elevator_name,
                    'floor': current_floor,
                    'advanced_position': advanced_position,
                    'state': state,
                    'passengers': passengers_count,
                    'capacity': max_capacity
                })
                
                # Send to WebSocket
                self._send_to_websocket({
                    'type': 'elevator_update',
                    'data': self.current_elevator_states[elevator_name]
                })
                
                # Send simulation time update
                self._send_to_websocket({
                    'type': 'simulation_time',
                    'data': {'time': timestamp}
                })
            
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
                
                # Update current elevator state with hall_calls for real-time display
                if elevator_name in self.current_elevator_states:
                    self.current_elevator_states[elevator_name]['hall_calls_up'] = hall_calls_up
                    self.current_elevator_states[elevator_name]['hall_calls_down'] = hall_calls_down
                    
                    # Send updated state to WebSocket
                    self._send_to_websocket({
                        'type': 'elevator_update',
                        'data': self.current_elevator_states[elevator_name]
                    })
            
            # Record hall call assignments (for color-coded visualization)
            if topic == 'gcs/hall_call_assignment':
                timestamp = message.get('timestamp')
                floor = message.get('floor')
                direction = message.get('direction')
                assigned_elevator = message.get('assigned_elevator')
                
                if timestamp is not None and floor is not None and direction is not None and assigned_elevator is not None:
                    # Store assignment with elevator-specific key
                    if assigned_elevator not in self.hall_calls_history:
                        self.hall_calls_history[assigned_elevator] = []
                    
                    assignment_data = {
                        'timestamp': timestamp,
                        'floor': floor,
                        'direction': direction,
                        'assigned_elevator': assigned_elevator,
                        'is_assignment': True
                    }
                    self.hall_calls_history[assigned_elevator].append(assignment_data)
                    
                    # Log event for JSON Lines
                    self._add_event_log('hall_call_assignment', {
                        'floor': floor,
                        'direction': direction,
                        'elevator': assigned_elevator
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
                    
                    # Log event for JSON Lines
                    self._add_event_log('hall_call_registered', {
                        'floor': floor,
                        'direction': direction,
                        'passenger': passenger_name
                    })
                    
                    # Don't update waiting passengers here - it's now handled in passenger/waiting
                    # to avoid double counting
            
            # Track when passengers start waiting (join the queue) - more reliable
            if topic == 'passenger/waiting':
                floor = message.get('floor')
                direction = message.get('direction')
                passenger_name = message.get('passenger_name')
                
                if floor is not None and direction is not None:
                    # Increment waiting passengers when they join the queue
                    self._update_waiting_passengers(floor, direction, 1)
                    print(f"[Statistics] {passenger_name} started waiting at floor {floor} ({direction}).")
                    
                    # Log event for JSON Lines
                    self._add_event_log('passenger_waiting', {
                        'passenger': passenger_name,
                        'floor': floor,
                        'direction': direction
                    })
            
            # Track car_calls status for real-time display
            car_calls_match = re.search(r'elevator/(.*?)/car_calls', topic)
            if car_calls_match:
                elevator_name = car_calls_match.group(1)
                car_calls_list = message.get('car_calls', [])
                
                # Update current elevator state with car_calls
                if elevator_name in self.current_elevator_states:
                    self.current_elevator_states[elevator_name]['car_calls'] = car_calls_list
                    
                    # Send updated state to WebSocket
                    self._send_to_websocket({
                        'type': 'elevator_update',
                        'data': self.current_elevator_states[elevator_name]
                    })
            
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
                    
                    # Log event for JSON Lines
                    self._add_event_log('car_call_registered', {
                        'elevator': elevator_name,
                        'floor': destination,
                        'passenger': passenger_name
                    })
            
            # Record hall call OFF events (for visualization)
            hall_call_off_match = re.search(r'hall_button/floor_(.*?)/call_off', topic)
            if hall_call_off_match:
                floor = int(hall_call_off_match.group(1))
                
                timestamp = message.get('timestamp')
                direction = message.get('direction')
                action = message.get('action')
                serviced_by = message.get('serviced_by')  # Get elevator name that serviced this call
                
                if timestamp is not None and direction is not None and action == 'OFF' and serviced_by is not None:
                    # Store hall call OFF events under the elevator that serviced it
                    if serviced_by not in self.hall_call_off_history:
                        self.hall_call_off_history[serviced_by] = []
                    
                    hall_call_off_data = {
                        'timestamp': timestamp,
                        'floor': floor,
                        'direction': direction,
                        'action': 'OFF',
                        'serviced_by': serviced_by
                    }
                    self.hall_call_off_history[serviced_by].append(hall_call_off_data)
                    
                    # Log event for JSON Lines
                    self._add_event_log('hall_call_off', {
                        'floor': floor,
                        'direction': direction,
                        'elevator': serviced_by
                    })
                    
                    # Note: Waiting passengers are now removed individually when each passenger boards
                    # (see 'passenger/boarding' event handler above)
            
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
                    
                    # Log event for JSON Lines
                    self._add_event_log('car_call_off', {
                        'elevator': elevator_name,
                        'floor': destination
                    })
                    
                    # Remove car call from current state and send to WebSocket
                    if elevator_name in self.current_elevator_states:
                        car_calls = self.current_elevator_states[elevator_name].get('car_calls', [])
                        if destination in car_calls:
                            car_calls.remove(destination)
                            self.current_elevator_states[elevator_name]['car_calls'] = car_calls
                            
                            # Send updated state to WebSocket
                            self._send_to_websocket({
                                'type': 'elevator_update',
                                'data': self.current_elevator_states[elevator_name]
                            })
            
            # Record passenger boarding events
            if topic == 'passenger/boarding':
                floor = message.get('floor')
                direction = message.get('direction')
                passenger_name = message.get('passenger_name')
                elevator_name = message.get('elevator_name')
                
                if floor is not None and direction is not None:
                    # Remove one waiting passenger when someone boards
                    self._update_waiting_passengers(floor, direction, -1)
                    print(f"[Statistics] {passenger_name} boarded at floor {floor} ({direction}). Waiting passengers decreased.")
                    
                    # Log event for JSON Lines
                    self._add_event_log('passenger_boarding', {
                        'passenger': passenger_name,
                        'floor': floor,
                        'direction': direction,
                        'elevator': elevator_name
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
                    
                    # Log event for JSON Lines
                    self._add_event_log('door_event', {
                        'elevator': elevator_name,
                        'event': event_type,
                        'floor': floor
                    })
                    
                    # Send door event to WebSocket for real-time animation
                    self._send_to_websocket({
                        'type': 'event',
                        'data': {
                            'event_type': event_type,
                            'elevator_name': elevator_name,
                            'floor': floor,
                            'timestamp': timestamp,
                            'details': door_id
                        }
                    })
            
            # Record passenger alighting events (for JSON Lines log)
            if topic == 'passenger/alighting':
                passenger_name = message.get('passenger_name')
                floor = message.get('floor')
                elevator_name = message.get('elevator_name')
                
                # Log event for JSON Lines
                if passenger_name and floor and elevator_name:
                    self._add_event_log('passenger_alighting', {
                        'passenger': passenger_name,
                        'floor': floor,
                        'elevator': elevator_name
                    })

    def _get_elevator_color(self, elevator_name):
        """Get color for a specific elevator"""
        # Define colors for different elevators
        elevator_colors = {
            'Elevator_1': '#1f77b4',  # Sky blue
            'Elevator_2': '#ff7f0e',  # Orange
            'Elevator_3': '#2ca02c',  # Green
            'Elevator_4': '#d62728',  # Red
            'Elevator_5': '#9467bd',  # Purple
            'Elevator_6': '#8c564b',  # Brown
        }
        return elevator_colors.get(elevator_name, '#1f77b4')  # Default to sky blue
    
    def plot_trajectory_diagram(self, show_passenger_boxes=False):
        """Draw trajectory diagram after simulation ends
        
        Args:
            show_passenger_boxes: If True, show passenger occupancy boxes (can be cluttered with multiple elevators)
        """
        print("\n--- Plotting: Elevator Trajectory Diagram ---")
        plt.figure(figsize=(14, 8))

        # Define colors for different elevators
        elevator_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        elevator_names = sorted(self.elevator_trajectories.keys())
        
        for idx, name in enumerate(elevator_names):
            trajectory = self.elevator_trajectories[name]
            if not trajectory:
                continue
            
            sorted_trajectory = sorted(trajectory, key=lambda x: x[0])
            times, floors = zip(*sorted_trajectory)
            
            # Use distinct color and wider line for each elevator
            color = elevator_colors[idx % len(elevator_colors)]
            plt.step(times, floors, where='post', label=name, linewidth=2.5, color=color, alpha=0.8)
            
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
            
            # Draw passenger visualization boxes (optional, disabled by default for clarity)
            if show_passenger_boxes:
                self._plot_passenger_boxes(name)

        plt.title("Elevator Trajectory Diagram (Travel Diagram, Advanced Position)")
        plt.xlabel("Time (s)")
        plt.ylabel("Advanced Position (Floor)")
        plt.grid(True, which='both', linestyle='--', alpha=0.7)
        
        all_floors = [floor for _, trajectory in self.elevator_trajectories.items() for _, floor in trajectory]
        if all_floors:
            min_floor = int(min(all_floors))
            max_floor = int(max(all_floors))
            plt.yticks(range(min_floor, max_floor + 2))

        plt.legend(loc='upper right', fontsize=10)
        
        # Save to file
        output_filename = 'elevator_trajectory_diagram.png'
        plt.savefig(output_filename, dpi=150, bbox_inches='tight')
        print(f"Trajectory diagram saved to: {output_filename}")
        
        plt.show()
    
    def _plot_hall_calls_arrows(self, elevator_name):
        """Draw hall_call assignments with arrows (color-coded by assigned elevator)"""
        # Assignment data is stored under each elevator's key
        if elevator_name not in self.hall_calls_history:
            return
        
        # Get elevator-specific color
        elevator_color = self._get_elevator_color(elevator_name)
        
        # Determine lighter background color based on elevator color
        if elevator_name == 'Elevator_1':
            bg_color = 'lightblue'  # Light blue for sky blue
        elif elevator_name == 'Elevator_2':
            bg_color = 'navajowhite'  # Light orange
        else:
            bg_color = 'lightgray'
        
        # Track already drawn (timestamp, floor, direction) combinations
        plotted_positions = set()
        
        for hall_call_data in self.hall_calls_history[elevator_name]:
            # Process only assignment data
            if not hall_call_data.get('is_assignment', False):
                continue
                
            timestamp = hall_call_data['timestamp']
            floor = hall_call_data['floor']
            direction = hall_call_data['direction']
            
            position_key = (round(timestamp, 2), floor, direction)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                if direction == 'UP':
                    # Upward arrow (elevator-specific color)
                    plt.annotate('↑', (timestamp, floor), 
                               fontsize=12, color=elevator_color, fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor=bg_color, alpha=0.7))
                elif direction == 'DOWN':
                    # Downward arrow (elevator-specific color)
                    plt.annotate('↓', (timestamp, floor), 
                               fontsize=12, color=elevator_color, fontweight='bold',
                               ha='center', va='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor=bg_color, alpha=0.7))
                
                plotted_positions.add(position_key)
    
    def _plot_car_calls_circles(self, elevator_name):
        """Draw car_calls circles for the specified elevator"""
        if elevator_name not in self.car_calls_history:
            return
        
        # Get elevator-specific color
        elevator_color = self._get_elevator_color(elevator_name)
        
        # Track already drawn (timestamp, floor) combinations
        plotted_positions = set()
        
        for car_call_data in self.car_calls_history[elevator_name]:
            timestamp = car_call_data['timestamp']
            car_calls = car_call_data['car_calls']
            
            # Display car_calls with circles (elevator-specific color)
            for floor in car_calls:
                position_key = (round(timestamp, 2), floor)  # Round time for duplicate detection
                
                if position_key not in plotted_positions:
                    plt.scatter(timestamp, floor, 
                              s=80, c=elevator_color, marker='o', alpha=0.7, 
                              edgecolors=elevator_color, linewidth=1.5)
                    plotted_positions.add(position_key)
    
    def _plot_hall_calls_off_events(self, elevator_name):
        """Draw hall call OFF events with X marks (color-coded by servicing elevator)"""
        # OFF events are now stored under each elevator's key
        if elevator_name not in self.hall_call_off_history:
            return
        
        # Get elevator-specific color
        elevator_color = self._get_elevator_color(elevator_name)
        
        # Determine lighter background color based on elevator color
        if elevator_name == 'Elevator_1':
            bg_color = 'lightblue'  # Light blue for sky blue
        elif elevator_name == 'Elevator_2':
            bg_color = 'navajowhite'  # Light orange
        else:
            bg_color = 'lightgray'
        
        # Track already drawn (timestamp, floor, direction) combinations
        plotted_positions = set()
        
        for hall_call_off_data in self.hall_call_off_history[elevator_name]:
            timestamp = hall_call_off_data['timestamp']
            floor = hall_call_off_data['floor']
            direction = hall_call_off_data['direction']
            
            position_key = (round(timestamp, 2), floor, direction)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                # OFF mark with elevator-specific color
                plt.annotate('✕', (timestamp, floor), 
                           fontsize=10, color=elevator_color, fontweight='bold',
                           ha='center', va='center',
                           bbox=dict(boxstyle='round,pad=0.1', facecolor=bg_color, alpha=0.5))
                
                plotted_positions.add(position_key)
    
    def _plot_car_calls_off_events(self, elevator_name):
        """Draw car call OFF events with X marks"""
        if elevator_name not in self.car_call_off_history:
            return
        
        # Get elevator-specific color (darker version)
        elevator_color = self._get_elevator_color(elevator_name)
        
        # Track already drawn (timestamp, floor) combinations
        plotted_positions = set()
        
        for car_call_off_data in self.car_call_off_history[elevator_name]:
            timestamp = car_call_off_data['timestamp']
            destination = car_call_off_data['destination']
            
            position_key = (round(timestamp, 2), destination)  # Round time for duplicate detection
            
            if position_key not in plotted_positions:
                # Car call OFF mark (elevator-specific color X)
                plt.scatter(timestamp, destination, 
                          s=60, c=elevator_color, marker='x', alpha=0.8, 
                          linewidth=2)
                plotted_positions.add(position_key)

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

    def _plot_passenger_boxes(self, elevator_name):
        """Draw passenger visualization boxes below elevator trajectory"""
        if elevator_name not in self.passenger_count_history:
            return
        
        # Get elevator trajectory for positioning
        if elevator_name not in self.elevator_trajectories:
            return
        
        trajectory = self.elevator_trajectories[elevator_name]
        if not trajectory:
            return
        
        # Track already drawn boxes to avoid duplicates
        plotted_positions = set()
        
        for timestamp, passengers_count, max_capacity in self.passenger_count_history[elevator_name]:
            # Find corresponding floor from trajectory
            floor = self._get_floor_at_time(elevator_name, timestamp)
            if floor is None:
                continue
            
            position_key = (round(timestamp, 1), floor)  # Round time for duplicate detection
            if position_key in plotted_positions:
                continue
            
            # Calculate occupancy percentage
            occupancy_rate = passengers_count / max_capacity if max_capacity > 0 else 0
            
            # Determine color based on occupancy
            if occupancy_rate <= 0.3:
                box_color = 'lightgreen'
                square_color = 'green'
            elif occupancy_rate <= 0.7:
                box_color = 'lightyellow'
                square_color = 'orange'
            else:
                box_color = 'lightcoral'
                square_color = 'red'
            
            # Draw passenger box
            box_height = 0.8  # Height of passenger box
            box_offset = -1.2  # Offset below trajectory line
            box_bottom = floor + box_offset
            box_width = 2.0  # Width of passenger box
            
            # Create rectangle for passenger box
            from matplotlib.patches import Rectangle
            box = Rectangle((timestamp - box_width/2, box_bottom), 
                          box_width, box_height, 
                          facecolor=box_color, 
                          edgecolor='black', 
                          alpha=0.7, 
                          linewidth=1)
            plt.gca().add_patch(box)
            
            # Draw passenger squares (■) with spacing
            if passengers_count > 0:
                max_squares_to_show = 5
                squares_to_show = min(passengers_count, max_squares_to_show)
                
                # Calculate positions for squares
                square_size = 0.15
                spacing = 0.05
                total_width = squares_to_show * square_size + (squares_to_show - 1) * spacing
                start_x = timestamp - total_width / 2
                square_y = box_bottom + box_height * 0.7
                
                # Draw squares
                for i in range(squares_to_show):
                    square_x = start_x + i * (square_size + spacing)
                    plt.scatter(square_x, square_y, 
                              s=200, marker='s', c=square_color, 
                              alpha=0.8, edgecolors='black', linewidth=0.5)
                
                # Add "+X" text if more passengers than squares shown
                if passengers_count > max_squares_to_show:
                    extra_count = passengers_count - max_squares_to_show
                    plus_x = start_x + squares_to_show * (square_size + spacing)
                    plt.text(plus_x, square_y, f'+{extra_count}', 
                           fontsize=8, ha='left', va='center', 
                           color=square_color, fontweight='bold')
            
            # Add passenger count and percentage text
            count_text = f'{passengers_count}/{max_capacity}'
            percent_text = f'{occupancy_rate*100:.0f}%'
            
            # Position text in bottom right of box
            text_x = timestamp + box_width/2 - 0.1
            text_y_count = box_bottom + box_height * 0.3
            text_y_percent = box_bottom + box_height * 0.1
            
            plt.text(text_x, text_y_count, count_text, 
                   fontsize=8, ha='right', va='center', 
                   color='black', fontweight='bold')
            plt.text(text_x, text_y_percent, percent_text, 
                   fontsize=7, ha='right', va='center', 
                   color='black')
            
            plotted_positions.add(position_key)
    
    def _get_floor_at_time(self, elevator_name, timestamp):
        """Get elevator floor at specific timestamp"""
        if elevator_name not in self.elevator_trajectories:
            return None
        
        trajectory = self.elevator_trajectories[elevator_name]
        if not trajectory:
            return None
        
        # Find the floor at the given timestamp
        sorted_trajectory = sorted(trajectory, key=lambda x: x[0])
        
        # If timestamp is before first point, return first floor
        if timestamp <= sorted_trajectory[0][0]:
            return sorted_trajectory[0][1]
        
        # If timestamp is after last point, return last floor
        if timestamp >= sorted_trajectory[-1][0]:
            return sorted_trajectory[-1][1]
        
        # Find the appropriate floor using step function behavior
        for i in range(len(sorted_trajectory) - 1):
            if sorted_trajectory[i][0] <= timestamp < sorted_trajectory[i + 1][0]:
                return sorted_trajectory[i][1]
        
        return sorted_trajectory[-1][1]
    
    def _update_waiting_passengers(self, floor, direction, change):
        """Update waiting passengers count for a specific floor and direction"""
        floor_key = str(floor)
        
        if floor_key not in self.waiting_passengers:
            self.waiting_passengers[floor_key] = {'UP': 0, 'DOWN': 0}
        
        # Update count (ensure it doesn't go below 0)
        current_count = self.waiting_passengers[floor_key].get(direction, 0)
        new_count = max(0, current_count + change)
        self.waiting_passengers[floor_key][direction] = new_count
        
        # Debug log
        print(f"[Statistics] Waiting passengers at floor {floor} {direction}: {current_count} -> {new_count} (change: {change:+d})")
        print(f"[Statistics] All waiting passengers: {self.waiting_passengers}")
        
        # Send updated waiting passengers data to WebSocket
        self._send_to_websocket({
            'type': 'waiting_passengers_update',
            'data': self.waiting_passengers
        })
    
    def save_event_log(self, filename='simulation_log.jsonl'):
        """
        Save the event log to a JSON Lines file.
        
        Args:
            filename (str): Name of the output file (default: 'simulation_log.jsonl')
        """
        print(f"\nSaving event log to {filename}...")
        
        with open(filename, 'w', encoding='utf-8') as f:
            # Write metadata as first line
            if self.simulation_metadata:
                f.write(json.dumps({
                    "type": "metadata",
                    "data": self.simulation_metadata
                }) + '\n')
            
            # Write all events (already sorted by time due to sequential processing)
            for event in self.event_log:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        
        print(f"Event log saved: {len(self.event_log)} events written to {filename}")
        return filename
    
    # Note: print_passenger_metrics_summary() has been moved to SimulationStatistics
    # This base class focuses on sensor-based metrics only