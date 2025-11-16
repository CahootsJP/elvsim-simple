"""
DCS (Destination Control System) Passenger Workflow Implementation

Implements the DCS workflow where passengers register destination at a panel
and wait for assigned elevator.
"""

from typing import Generator
from simulator.interfaces.passenger_workflow import IPassengerWorkflow


class DCSWorkflow(IPassengerWorkflow):
    """
    DCS elevator workflow
    
    Steps:
    1. Register destination at DCS panel (send to GCS)
    2. Wait for elevator assignment from GCS
    3. Board assigned elevator only
    4. Exit at destination (car calls registered automatically by photoelectric sensor)
    
    Usage:
        workflow = DCSWorkflow()
        yield from workflow.execute(passenger, arrival_floor, destination_floor)
    """
    
    def execute(self, passenger, arrival_floor: int, destination_floor: int) -> Generator:
        """
        Execute DCS workflow
        """
        print(f"{passenger.env.now:.2f} [{passenger.name}] Using DCS at floor {arrival_floor}.")
        
        # 1. Register destination at DCS panel
        # Use destination_floor parameter (for multi-stop support)
        # passenger.behavior.get_destination_for_dcs() would use passenger.destination_floor
        # which is the final destination, not the current journey destination
        destination = destination_floor
        print(f"{passenger.env.now:.2f} [{passenger.name}] Registering destination: {destination} at DCS panel.")
        
        # Record waiting start time (self-tracking)
        passenger.waiting_start_time = passenger.env.now
        
        # Send DCS hall call to GCS (destination-based, not direction-based)
        dcs_call_message = {
            'floor': arrival_floor,
            'destination': destination,
            'passenger_name': passenger.name,
            'call_type': 'DCS'
        }
        passenger.broker.put("gcs/hall_call", dcs_call_message)
        print(f"{passenger.env.now:.2f} [{passenger.name}] DCS call sent to GCS: Floor {arrival_floor} -> {destination}")
        
        # Notify Statistics that a passenger is waiting
        waiting_message = {
            "floor": arrival_floor,
            "direction": None,  # DCS doesn't use direction
            "passenger_name": passenger.name,
            "destination": destination
        }
        passenger.broker.put("passenger/waiting", waiting_message)
        
        # 2. Wait for elevator assignment from GCS
        assignment_topic = 'gcs/hall_call_assignment'
        assigned_elevator = None
        
        # Listen for assignment message (filter by floor and passenger)
        # Note: We need to filter messages because multiple passengers may be listening
        # to the same topic. If we get a message for another passenger, we need to
        # put it back or wait for the next one.
        while assigned_elevator is None:
            message = yield passenger.broker.get(assignment_topic)
            
            # Check if this assignment is for this passenger
            if (message.get('floor') == arrival_floor and 
                message.get('passenger_name') == passenger.name):
                assigned_elevator = message.get('assigned_elevator')
                print(f"{passenger.env.now:.2f} [{passenger.name}] Assigned to {assigned_elevator} by GCS.")
                
                # Notify behavior about assignment
                passenger.behavior.on_elevator_assigned(passenger, assigned_elevator)
                break
            else:
                # This message is for another passenger - put it back
                # Note: This is a simple approach. In a real system, we might use
                # a more sophisticated message routing mechanism.
                passenger.broker.put(assignment_topic, message)
        
        # 3. Join the queue (DCS: queue per elevator)
        # Use floor_queue_manager to get the correct queue structure
        if passenger.floor_queue_manager:
            current_queue = passenger.floor_queue_manager.get_queue(
                floor=arrival_floor,
                elevator_name=assigned_elevator
            )
        else:
            # Fallback to old structure (backward compatibility)
            direction = "UP" if destination_floor > arrival_floor else "DOWN"
            current_queue = passenger.floor_queues[arrival_floor][direction]
        
        print(f"{passenger.env.now:.2f} [{passenger.name}] Now waiting in {assigned_elevator} queue at floor {arrival_floor}.")
        
        yield current_queue.put(passenger)
        
        # Track current assigned elevator for re-registration if left behind
        current_assigned_elevator = assigned_elevator
        
        # 4. Wait for assigned elevator to arrive and open door
        boarded_successfully = False
        CHECK_INTERVAL = 0.1  # Polling interval
        
        while not boarded_successfully:
            yield passenger.env.timeout(CHECK_INTERVAL)
            
            # Check if boarding permission arrived
            if len(passenger.board_permission_event.items) > 0:
                # Collect all available permissions
                available_permissions = []
                while len(passenger.board_permission_event.items) > 0:
                    permission = yield passenger.board_permission_event.get()
                    available_permissions.append(permission)
                
                # Select elevator (DCS: only assigned elevator)
                selected_permission = passenger.behavior.select_best_elevator(passenger, available_permissions)
                
                if selected_permission is None:
                    # Assigned elevator not available - reject all and continue waiting
                    for perm in available_permissions:
                        perm['completion_event'].succeed()
                    print(f"{passenger.env.now:.2f} [{passenger.name}] Assigned elevator {current_assigned_elevator} not available. Continuing to wait...")
                    continue
                
                # Reject other elevators
                for perm in available_permissions:
                    if perm != selected_permission:
                        print(f"{passenger.env.now:.2f} [{passenger.name}] Rejecting elevator {perm.get('elevator_name')} (waiting for {current_assigned_elevator}).")
                        perm['completion_event'].succeed()
                
                # Board the assigned elevator
                completion_event = selected_permission['completion_event']
                elevator_name = selected_permission.get('elevator_name', None)
                door_open_time = selected_permission.get('door_open_time', None)
                
                print(f"{passenger.env.now:.2f} [{passenger.name}] Boarding assigned elevator {elevator_name}.")
                
                # Record door open time (self-tracking)
                if door_open_time is not None:
                    passenger.door_open_time = door_open_time
                
                # Publish passenger boarding event
                passenger.broker.put('passenger/boarding', {
                    'passenger_name': passenger.name,
                    'floor': arrival_floor,
                    'destination': destination_floor,  # DCS: include destination instead of direction
                    'elevator_name': elevator_name,
                    'timestamp': passenger.env.now,
                    'wait_time': passenger.get_waiting_time_to_door_open(),
                    'wait_time_to_boarding': passenger.get_waiting_time_to_boarding()
                })
                
                yield passenger.env.timeout(passenger.move_speed)

                # Record boarding time (self-tracking)
                passenger.boarding_time = passenger.env.now
                passenger.boarded_elevator_name = elevator_name

                # Note: Car call is registered automatically by photoelectric sensor
                # When first passenger boards at DCS floor, all waiting passengers' destinations
                # are automatically registered as car calls
                print(f"{passenger.env.now:.2f} [{passenger.name}] Boarded {elevator_name}. Car call for {destination_floor} will be registered automatically by photoelectric sensor.")

                # Report to Door that "boarding is complete"
                completion_event.succeed()
                
                boarded_successfully = True
            
            # Check if boarding failed (elevator full - left behind)
            elif len(passenger.boarding_failed_event.items) > 0:
                failed_event = yield passenger.boarding_failed_event.get()
                print(f"{passenger.env.now:.2f} [{passenger.name}] Failed to board {current_assigned_elevator} (capacity full). Re-registering at DCS panel...")
                
                # Passenger was left behind - must re-register at DCS panel
                # This is the correct DCS behavior: GCS cannot detect left-behind passengers
                # Passenger must manually re-register
                
                # Remove from current queue
                if passenger.floor_queue_manager:
                    # Passenger will be removed from queue by Door when it detects no boarding
                    # But we need to ensure we're in the right queue for re-assignment
                    pass
                
                # Re-register at DCS panel (same as initial registration)
                dcs_call_message = {
                    'floor': arrival_floor,
                    'destination': destination_floor,
                    'passenger_name': passenger.name,
                    'call_type': 'DCS',
                    'reason': 'LEFT_BEHIND'
                }
                passenger.broker.put("gcs/hall_call", dcs_call_message)
                print(f"{passenger.env.now:.2f} [{passenger.name}] Re-registered at DCS panel: Floor {arrival_floor} -> {destination_floor}")
                
                # Wait for new assignment
                new_assigned_elevator = None
                assignment_topic = 'gcs/hall_call_assignment'
                
                while new_assigned_elevator is None:
                    message = yield passenger.broker.get(assignment_topic)
                    
                    # Check if this assignment is for this passenger
                    if (message.get('floor') == arrival_floor and 
                        message.get('passenger_name') == passenger.name):
                        new_assigned_elevator = message.get('assigned_elevator')
                        print(f"{passenger.env.now:.2f} [{passenger.name}] Re-assigned to {new_assigned_elevator} by GCS.")
                        
                        # Move to new elevator's queue if different
                        if passenger.floor_queue_manager and new_assigned_elevator != current_assigned_elevator:
                            passenger.floor_queue_manager.move_passenger(
                                passenger,
                                floor=arrival_floor,
                                from_elevator=current_assigned_elevator,
                                to_elevator=new_assigned_elevator
                            )
                        
                        # Update assigned elevator
                        current_assigned_elevator = new_assigned_elevator
                        passenger.behavior.on_elevator_assigned(passenger, new_assigned_elevator)
                        break
                    else:
                        # This message is for another passenger - put it back
                        passenger.broker.put(assignment_topic, message)
                
                # Continue waiting for new assigned elevator
                print(f"{passenger.env.now:.2f} [{passenger.name}] Now waiting for {new_assigned_elevator} after re-registration...")

        # 5. Wait for "please exit" permission from Door at destination
        permission_data = yield passenger.exit_permission_event.get()
        completion_event = permission_data['completion_event']

        # 6. Exit the elevator at own pace
        print(f"{passenger.env.now:.2f} [{passenger.name}] Exiting elevator.")
        yield passenger.env.timeout(passenger.move_speed)
        
        # Record alighting time (self-tracking)
        passenger.alighting_time = passenger.env.now
        
        # 7. Report to Door that "exiting is complete"
        completion_event.succeed()
        
        # 8. Publish passenger alighting event (for metrics)
        passenger.broker.put('passenger/alighting', {
            'timestamp': passenger.env.now,
            'passenger_name': passenger.name,
            'floor': destination_floor,
            'elevator_name': getattr(passenger, 'boarded_elevator_name', None),
            'riding_time': passenger.get_riding_time(),
            'total_journey_time': passenger.get_total_journey_time(),
            'wait_time': passenger.get_waiting_time_to_door_open()
        })
        
        print(f"{passenger.env.now:.2f} [{passenger.name}] Journey complete.")

