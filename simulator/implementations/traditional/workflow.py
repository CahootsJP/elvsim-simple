"""
Traditional Passenger Workflow Implementation

Implements the traditional UP/DOWN button elevator workflow.
"""

from typing import Generator
from simulator.interfaces.passenger_workflow import IPassengerWorkflow


class TraditionalWorkflow(IPassengerWorkflow):
    """
    Traditional elevator workflow
    
    Steps:
    1. Press UP/DOWN hall button
    2. Join queue and wait
    3. Board elevator when door opens
    4. Press car button for destination
    5. Exit at destination
    
    Usage:
        workflow = TraditionalWorkflow()
        yield from workflow.execute(passenger, arrival_floor, destination_floor)
    """
    
    def execute(self, passenger, arrival_floor: int, destination_floor: int) -> Generator:
        """
        Execute traditional elevator workflow
        """
        print(f"{passenger.env.now:.2f} [{passenger.name}] Using TRADITIONAL at floor {arrival_floor}.")
        
        direction = "UP" if destination_floor > arrival_floor else "DOWN"
        button = passenger.hall_buttons[arrival_floor][direction]
        
        boarded_successfully = False
        
        # 1. Press hall button (with duplicate check functionality)
        if button.is_lit():
            print(f"{passenger.env.now:.2f} [{passenger.name}] Hall button at floor {arrival_floor} ({direction}) already lit. No need to press.")
        else:
            button.press(passenger_name=passenger.name)

        # 2. Join the queue in the correct direction
        current_queue = passenger.floor_queues[arrival_floor][direction]
        print(f"{passenger.env.now:.2f} [{passenger.name}] Now waiting in '{direction}' queue at floor {arrival_floor}.")
        
        # Record waiting start time (self-tracking)
        passenger.waiting_start_time = passenger.env.now
        
        # Notify Statistics that a passenger is waiting
        waiting_message = {
            "floor": arrival_floor,
            "direction": direction,
            "passenger_name": passenger.name
        }
        passenger.broker.put("passenger/waiting", waiting_message)
        
        yield current_queue.put(passenger)

        # 3. Periodic check loop: monitor queue position, button state, and boarding events
        CHECK_INTERVAL = passenger.behavior.get_check_interval()
        
        while not boarded_successfully:
            # Wait for next check interval
            yield passenger.env.timeout(CHECK_INTERVAL)
            
            # Check 1: Use behavior to decide if should press button
            if passenger.behavior.should_press_button(passenger, button, current_queue):
                print(f"{passenger.env.now:.2f} [{passenger.name}] I'm at front and button is OFF. Pressing button!")
                button.press(passenger_name=passenger.name)
            
            # Check 2: Has boarding permission arrived?
            if len(passenger.board_permission_event.items) > 0:
                # Collect all available permissions (may be multiple elevators)
                available_permissions = []
                while len(passenger.board_permission_event.items) > 0:
                    permission = yield passenger.board_permission_event.get()
                    available_permissions.append(permission)
                
                # Select the best elevator using behavior strategy
                selected_permission = passenger.behavior.select_best_elevator(passenger, available_permissions)
                
                if selected_permission is None:
                    # All elevators were rejected - put back permissions and continue waiting
                    for perm in available_permissions:
                        perm['completion_event'].succeed()  # Notify doors
                    continue
                
                # Reject other elevators
                for perm in available_permissions:
                    if perm != selected_permission:
                        print(f"{passenger.env.now:.2f} [{passenger.name}] Rejecting elevator {perm.get('elevator_name')} (chose another).")
                        perm['completion_event'].succeed()  # Notify door
                
                # Board the selected elevator
                completion_event = selected_permission['completion_event']
                elevator_name = selected_permission.get('elevator_name', None)
                door_open_time = selected_permission.get('door_open_time', None)
                
                print(f"{passenger.env.now:.2f} [{passenger.name}] Boarding elevator {elevator_name}.")
                
                # Record door open time (self-tracking)
                if door_open_time is not None:
                    passenger.door_open_time = door_open_time
                
                # Publish passenger boarding event
                passenger.broker.put('passenger/boarding', {
                    'passenger_name': passenger.name,
                    'floor': arrival_floor,
                    'direction': direction,
                    'elevator_name': elevator_name,
                    'timestamp': passenger.env.now,
                    'wait_time': passenger.get_waiting_time_to_door_open(),
                    'wait_time_to_boarding': passenger.get_waiting_time_to_boarding()
                })
                
                yield passenger.env.timeout(passenger.move_speed)

                # Record boarding time (self-tracking)
                passenger.boarding_time = passenger.env.now
                passenger.boarded_elevator_name = elevator_name

                # Board the elevator and press destination button (if car buttons exist)
                # FULL DCS: No car buttons (destinations registered automatically by photoelectric sensor)
                # Hybrid DCS / Traditional: Has car buttons (press manually)
                if passenger.call_system.has_car_buttons():
                    print(f"{passenger.env.now:.2f} [{passenger.name}] Pressed car button for floor {destination_floor}.")
                    car_call_topic = f"elevator/{elevator_name}/car_call"
                    passenger.broker.put(car_call_topic, {'destination': destination_floor, 'passenger_name': passenger.name})
                else:
                    print(f"{passenger.env.now:.2f} [{passenger.name}] Boarded {elevator_name}. Car call for {destination_floor} will be registered automatically (FULL DCS).")

                # Report to Door that "boarding is complete"
                completion_event.succeed()
                
                boarded_successfully = True
            
            # Check 3: Has boarding failed?
            elif len(passenger.boarding_failed_event.items) > 0:
                # Get failure notification and discard it
                yield passenger.boarding_failed_event.get()
                print(f"{passenger.env.now:.2f} [{passenger.name}] Failed to board (capacity full). Will keep waiting and monitoring...")

        # 4. Wait for "please exit" permission from Door at destination
        permission_data = yield passenger.exit_permission_event.get()
        completion_event = permission_data['completion_event']

        # 5. Exit the elevator at own pace
        print(f"{passenger.env.now:.2f} [{passenger.name}] Exiting elevator.")
        yield passenger.env.timeout(passenger.move_speed)
        
        # Record alighting time (self-tracking)
        passenger.alighting_time = passenger.env.now
        
        # 6. Report to Door that "exiting is complete"
        completion_event.succeed()
        
        # 7. Publish passenger alighting event (for metrics)
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

