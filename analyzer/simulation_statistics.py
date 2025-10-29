from .statistics import Statistics

class SimulationStatistics(Statistics):
    """
    Simulator-only statistics with "God's view" access.
    
    Features:
    - Access to individual passenger objects
    - Detailed per-passenger metrics
    - Perfect information about passenger behavior
    
    Use cases:
    - Research papers
    - Algorithm comparison
    - Performance evaluation
    - Debugging
    
    ⚠️  NOT compatible with real hardware.
    """
    def __init__(self, env, broadcast_pipe, websocket_server=None):
        super().__init__(env, broadcast_pipe, websocket_server)
        
        # God's view data (simulation-only)
        self.passengers = []  # Direct access to Passenger objects
    
    def register_passenger(self, passenger):
        """
        Register a passenger object for detailed metrics collection.
        
        ⚠️  WARNING: This method is SIMULATION-ONLY.
        Real hardware cannot access passenger objects.
        
        Args:
            passenger: Passenger object to register
        """
        self.passengers.append(passenger)
    
    def print_passenger_metrics_summary(self):
        """
        Print detailed per-passenger metrics.
        
        Metrics include:
        - Waiting time (hall to boarding)
        - Waiting time (hall to door open)
        - Riding time
        - Total journey time
        
        ⚠️  WARNING: This method uses SIMULATION-ONLY data.
        Real hardware cannot collect these metrics.
        """
        print("\n" + "="*80)
        print("   PASSENGER METRICS SUMMARY (SIMULATION ONLY)")
        print("="*80)
        print("⚠️  These metrics require direct passenger object access")
        print("⚠️  NOT available in real hardware deployments")
        print("="*80)
        
        # Collect metrics from all registered passengers
        waiting_to_boarding = []
        waiting_to_door = []
        riding_times = []
        total_journey_times = []
        
        for passenger in self.passengers:
            # Waiting Time (1): Hall to Boarding
            wait_boarding = passenger.get_waiting_time_to_boarding()
            if wait_boarding is not None:
                waiting_to_boarding.append(wait_boarding)
            
            # Waiting Time (2): Hall to Door Open
            wait_door = passenger.get_waiting_time_to_door_open()
            if wait_door is not None:
                waiting_to_door.append(wait_door)
            
            # Riding Time
            ride = passenger.get_riding_time()
            if ride is not None:
                riding_times.append(ride)
            
            # Total Journey Time
            total = passenger.get_total_journey_time()
            if total is not None:
                total_journey_times.append(total)
        
        # Display Waiting Time (1): Hall to Boarding
        if waiting_to_boarding:
            print(f"\nWaiting Time (Hall to Boarding):")
            print(f"  Count:   {len(waiting_to_boarding):>6} passengers")
            print(f"  Average: {sum(waiting_to_boarding) / len(waiting_to_boarding):>6.2f} seconds")
            print(f"  Min:     {min(waiting_to_boarding):>6.2f} seconds")
            print(f"  Max:     {max(waiting_to_boarding):>6.2f} seconds")
        
        # Display Waiting Time (2): Hall to Door Open
        if waiting_to_door:
            print(f"\nWaiting Time (Hall to Door Open):")
            print(f"  Count:   {len(waiting_to_door):>6} passengers")
            print(f"  Average: {sum(waiting_to_door) / len(waiting_to_door):>6.2f} seconds")
            print(f"  Min:     {min(waiting_to_door):>6.2f} seconds")
            print(f"  Max:     {max(waiting_to_door):>6.2f} seconds")
        
        # Display Riding Time
        if riding_times:
            print(f"\nRiding Time:")
            print(f"  Count:   {len(riding_times):>6} passengers")
            print(f"  Average: {sum(riding_times) / len(riding_times):>6.2f} seconds")
            print(f"  Min:     {min(riding_times):>6.2f} seconds")
            print(f"  Max:     {max(riding_times):>6.2f} seconds")
        
        # Display Total Journey Time
        if total_journey_times:
            print(f"\nTotal Journey Time:")
            print(f"  Count:   {len(total_journey_times):>6} passengers")
            print(f"  Average: {sum(total_journey_times) / len(total_journey_times):>6.2f} seconds")
            print(f"  Min:     {min(total_journey_times):>6.2f} seconds")
            print(f"  Max:     {max(total_journey_times):>6.2f} seconds")
        
        print("="*80)

