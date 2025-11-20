"""
Arrival Time Predictor

Calculates elevator arrival time predictions based on current state and travel time data.

This module is responsible for CALCULATION ONLY. It does not learn from operations.
Travel time data is provided by external sources (PhysicsEngine or future learning module).

Key Responsibilities:
- Predict arrival times for each elevator to each floor/direction
- Estimate current elevator state (safe to assign, remaining time, etc.)
- Predict stop sequences based on assigned calls

NOT Responsible For:
- Learning travel times (delegated to future OperationalDataLearner)
- Tracking elevator movements (uses current state only)
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import simpy


@dataclass
class StopPrediction:
    """Prediction of a future stop"""
    floor: int
    direction: str  # "UP", "DOWN", or "NO_DIRECTION"
    stop_reason: str  # "hall_call", "car_call"
    estimated_time_from_now: float  # seconds from current time
    cumulative_time: float  # cumulative time from start


@dataclass
class ElevatorState:
    """Current state estimation of an elevator"""
    safe_to_assign: bool  # Safe to assign new calls
    remaining_time_at_current: float  # Remaining time at current floor (seconds)
    current_floor: int
    advanced_position: int # The floor the elevator can stop at if it brakes immediately
    direction: str
    is_moving: bool
    assigned_calls_count: int  # Number of assigned calls


class TravelTimeProvider(ABC):
    """
    Interface for providing travel time data.
    
    Implementations:
    - PhysicsBasedProvider: Uses PhysicsEngine (Phase 1)
    - LearnedDataProvider: Uses learned data (Phase 3, future)
    """
    
    @abstractmethod
    def get_travel_time(self, elevator_name: str, from_floor: int, to_floor: int) -> float:
        """Get travel time between two floors (seconds)"""
        pass
    
    @abstractmethod
    def get_position_transition_time(self, elevator_name: str, start_floor: int, target_advanced_pos: int) -> float:
        """
        Get time until the elevator's leading position reaches target_advanced_pos.
        
        This represents the time from departure at start_floor until the elevator
        is committed to reaching (or passing) target_advanced_pos.
        This is crucial for determining if an elevator can still stop at a floor
        or if it's too late (committed to next floor).
        
        Args:
            elevator_name: Name of elevator
            start_floor: Floor where movement starts
            target_advanced_pos: The target leading position (floor)
            
        Returns:
            Time in seconds
        """
        pass
    
    @abstractmethod
    def get_stop_time(self, floor: int, direction: str) -> float:
        """Get estimated stop duration at a floor (seconds)"""
        pass


class PhysicsBasedProvider(TravelTimeProvider):
    """
    Provides travel time data from PhysicsEngine.
    
    This is the initial implementation for Phase 1.
    Travel times are static and based on physics calculations.
    """
    
    def __init__(self, physics_engine, num_floors: int, default_stop_time: float = 5.0):
        """
        Initialize with PhysicsEngine data.
        
        Args:
            physics_engine: PhysicsEngine instance
            num_floors: Total number of floors
            default_stop_time: Default stop duration (seconds)
        """
        self.physics_engine = physics_engine
        self.num_floors = num_floors
        self.default_stop_time = default_stop_time
        
        # Build travel time table from PhysicsEngine
        self.travel_time_table: Dict[int, Dict[int, float]] = {}
        self._initialize_travel_times()
    
    def _initialize_travel_times(self) -> None:
        """
        Initialize travel time table from PhysicsEngine.
        
        Uses PhysicsEngine.flight_time_table[(from_floor, to_floor)]
        which contains pre-computed realistic travel times including
        acceleration, cruise, and deceleration phases.
        """
        if self.physics_engine is None:
            # No PhysicsEngine, use conservative defaults
            for from_fl in range(1, self.num_floors + 1):
                self.travel_time_table[from_fl] = {}
                for to_fl in range(1, self.num_floors + 1):
                    if from_fl == to_fl:
                        self.travel_time_table[from_fl][to_fl] = 0.0
                    else:
                        # 3 seconds per floor (conservative estimate)
                        self.travel_time_table[from_fl][to_fl] = abs(to_fl - from_fl) * 3.0
        else:
            # Get from PhysicsEngine's pre-computed tables
            for from_fl in range(1, self.num_floors + 1):
                self.travel_time_table[from_fl] = {}
                for to_fl in range(1, self.num_floors + 1):
                    if from_fl == to_fl:
                        self.travel_time_table[from_fl][to_fl] = 0.0
                    else:
                        # Get from flight_time_table
                        key = (from_fl, to_fl)
                        if key in self.physics_engine.flight_time_table:
                            self.travel_time_table[from_fl][to_fl] = \
                                self.physics_engine.flight_time_table[key]
                        else:
                            # Fallback to conservative estimate if not found
                            self.travel_time_table[from_fl][to_fl] = abs(to_fl - from_fl) * 3.0
                            print(f"[PhysicsBasedProvider] Warning: No flight time data for "
                                  f"{from_fl}→{to_fl}, using estimate")
    
    def get_travel_time(self, elevator_name: str, from_floor: int, to_floor: int) -> float:
        """Get travel time between two floors"""
        if from_floor not in self.travel_time_table:
            return abs(to_floor - from_floor) * 3.0
        return self.travel_time_table[from_floor].get(to_floor, abs(to_floor - from_floor) * 3.0)
    
    def get_position_transition_time(self, elevator_name: str, start_floor: int, target_advanced_pos: int) -> float:
        """
        Get time to reach a specific advanced position.
        
        Phase 1 Implementation:
        Currently approximates using travel time.
        TODO: Retrieve precise transition times from PhysicsEngine's acceleration profile.
        """
        # For now, use the travel time as a conservative estimate
        # In reality, the leading position advances faster than the physical position
        return self.get_travel_time(elevator_name, start_floor, target_advanced_pos)
    
    def get_stop_time(self, floor: int, direction: str) -> float:
        """Get estimated stop duration"""
        # TODO: Adjust based on floor (main floor takes longer)
        # TODO: Adjust based on predicted passenger count
        return self.default_stop_time


class ArrivalTimePredictor:
    """
    Arrival Time Predictor
    
    Calculates when each elevator will arrive at each floor/direction.
    
    This is a pure calculation engine. It does not learn or track state over time.
    Each prediction is calculated fresh based on current elevator state.
    
    Travel time data is provided by TravelTimeProvider (dependency injection).
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        num_floors: int,
        elevator_names: List[str],
        travel_time_provider: TravelTimeProvider,
        safety_margin: float = 1.5
    ):
        """
        Initialize the arrival time predictor.
        
        Args:
            env: SimPy environment
            num_floors: Total number of floors
            elevator_names: List of elevator names
            travel_time_provider: Provider for travel time data
            safety_margin: Safety time margin (seconds) to avoid risky assignments
        """
        self.env = env
        self.num_floors = num_floors
        self.elevator_names = elevator_names
        self.travel_time_provider = travel_time_provider
        self.safety_margin = safety_margin
        
        # Elevator references (populated by register_elevator)
        self.elevators: Dict[str, Any] = {}
    
    def register_elevator(self, elevator) -> None:
        """
        Register an elevator instance for state access.
        
        Args:
            elevator: Elevator instance
        """
        self.elevators[elevator.name] = elevator
    
    def predict_arrival_time(
        self,
        elevator_name: str,
        target_floor: int,
        target_direction: str
    ) -> float:
        """
        Predict when an elevator will arrive at target floor/direction.
        
        This is the main API for allocation strategies.
        Calculates arrival time based on current state and assigned calls.
        
        Args:
            elevator_name: Name of elevator
            target_floor: Target floor
            target_direction: Target direction ("UP" or "DOWN")
        
        Returns:
            Predicted arrival time in seconds from now.
            Returns float('inf') if unreachable or unsafe to assign.
        """
        if elevator_name not in self.elevators:
            return float('inf')
        
        elev = self.elevators[elevator_name]
        
        # Check safety
        state = self.estimate_elevator_state(elevator_name)
        if not state.safe_to_assign:
            # Too risky to assign (door closing, etc.)
            return float('inf')
        
        # Check if already at target
        if elev.current_floor == target_floor and elev.direction == target_direction:
            return state.remaining_time_at_current
        
        # Predict stop sequence
        stops = self._predict_stop_sequence(elevator_name)
        
        # Find target in stop sequence
        for stop in stops:
            if stop.floor == target_floor and stop.direction == target_direction:
                return stop.estimated_time_from_now
        
        # Target not in predicted stops
        # TODO: Calculate if we added this call to the elevator
        # For now, return inf (will be implemented in next phase)
        return float('inf')
    
    def estimate_elevator_state(self, elevator_name: str) -> ElevatorState:
        """
        Estimate current state of an elevator.
        
        Determines if it's safe to assign new calls based on:
        - Door state
        - Current direction
        - Time remaining at current floor
        
        Args:
            elevator_name: Name of elevator
        
        Returns:
            ElevatorState with current status
        """
        if elevator_name not in self.elevators:
            return ElevatorState(
                safe_to_assign=False,
                remaining_time_at_current=float('inf'),
                current_floor=1,
                advanced_position=1,
                direction="NO_DIRECTION",
                is_moving=False,
                assigned_calls_count=0
            )
        
        elev = self.elevators[elevator_name]
        
        # Check if moving
        is_moving = (elev.direction != "NO_DIRECTION")
        
        # Estimate remaining time at current floor
        remaining_time = 0.0
        if not is_moving:
            # Stopped at floor
            # TODO: Check door state for more accurate estimate
            # For now, conservative estimate
            remaining_time = self.travel_time_provider.get_stop_time(
                elev.current_floor, elev.direction
            )
        
        # Count assigned calls
        assigned_calls_count = (
            len(elev.hall_calls_up) + len(elev.hall_calls_down) +
            sum(1 for _ in elev.car_calls if _)
        )
        
        # Safe to assign if:
        # 1. Not currently moving (or just started)
        # 2. Has sufficient time margin at current floor
        # TODO: Add door state check (if door.closing_process exists, not safe)
        safe_to_assign = not is_moving and remaining_time > self.safety_margin
        
        # TODO: Calculate actual advanced position based on speed and braking distance
        # For now, assume advanced position is same as current (safe default)
        advanced_position = elev.current_floor
        
        return ElevatorState(
            safe_to_assign=safe_to_assign,
            remaining_time_at_current=remaining_time,
            current_floor=elev.current_floor,
            advanced_position=advanced_position,
            direction=elev.direction,
            is_moving=is_moving,
            assigned_calls_count=assigned_calls_count
        )
    
    def _predict_stop_sequence(self, elevator_name: str) -> List[StopPrediction]:
        """
        Predict the sequence of stops for an elevator.
        
        This simulates the elevator's selective-collective operation:
        1. Start from current position
        2. Continue in current direction collecting calls
        3. Reverse at top/bottom or when no more calls in that direction
        4. Repeat until all assigned calls are served
        
        Args:
            elevator_name: Name of elevator
        
        Returns:
            List of predicted stops in chronological order
        """
        if elevator_name not in self.elevators:
            return []
        
        elev = self.elevators[elevator_name]
        
        # Copy current call state (we'll simulate consuming these)
        car_calls = set(elev.car_calls)
        hall_calls_up = set(elev.hall_calls_up | elev.forced_calls_up)
        hall_calls_down = set(elev.hall_calls_down | elev.forced_calls_down)
        
        # Start from current position and direction
        current_floor = elev.current_floor
        current_direction = elev.direction if elev.direction != "NO_DIRECTION" else self._determine_initial_direction(
            current_floor, car_calls, hall_calls_up, hall_calls_down
        )
        
        predictions = []
        cumulative_time = 0.0
        max_iterations = self.num_floors * 4  # Safety limit to prevent infinite loops
        iterations = 0
        
        # Simulate selective-collective operation
        while (car_calls or hall_calls_up or hall_calls_down) and iterations < max_iterations:
            iterations += 1
            
            # Find next stop in current direction
            next_floor = self._find_next_stop(
                current_floor, current_direction,
                car_calls, hall_calls_up, hall_calls_down
            )
            
            if next_floor is None:
                # No more stops in this direction, try reversing
                current_direction = self._reverse_direction(current_direction)
                next_floor = self._find_next_stop(
                    current_floor, current_direction,
                    car_calls, hall_calls_up, hall_calls_down
                )
                
                if next_floor is None:
                    # No more stops at all
                    break
            
            # Calculate travel time to next floor
            travel_time = self._get_travel_time(elevator_name, current_floor, next_floor)
            cumulative_time += travel_time
            
            # Determine stop reason and direction
            stop_reason, stop_direction = self._determine_stop_reason(
                next_floor, current_direction,
                car_calls, hall_calls_up, hall_calls_down
            )
            
            # Record this stop
            predictions.append(StopPrediction(
                floor=next_floor,
                direction=stop_direction,
                stop_reason=stop_reason,
                estimated_time_from_now=cumulative_time,
                cumulative_time=cumulative_time
            ))
            
            # Add stop time
            stop_time = self._get_stop_time(next_floor, stop_direction)
            cumulative_time += stop_time
            
            # Consume calls at this floor
            self._consume_calls_at_floor(
                next_floor, stop_direction,
                car_calls, hall_calls_up, hall_calls_down
            )
            
            # Move to next floor
            current_floor = next_floor
        
        return predictions
    
    def _determine_initial_direction(
        self,
        current_floor: int,
        car_calls: set,
        hall_calls_up: set,
        hall_calls_down: set
    ) -> str:
        """
        Determine initial direction when elevator has no direction.
        
        Priority:
        1. Direction with calls above current floor (UP)
        2. Direction with calls below current floor (DOWN)
        3. UP (default)
        """
        has_calls_above = any(
            f > current_floor for f in (car_calls | hall_calls_up | hall_calls_down)
        )
        has_calls_below = any(
            f < current_floor for f in (car_calls | hall_calls_up | hall_calls_down)
        )
        
        if has_calls_above:
            return "UP"
        elif has_calls_below:
            return "DOWN"
        else:
            return "UP"  # Default
    
    def _find_next_stop(
        self,
        current_floor: int,
        direction: str,
        car_calls: set,
        hall_calls_up: set,
        hall_calls_down: set
    ) -> Optional[int]:
        """
        Find the next stop floor in the given direction.
        
        Selective-collective logic:
        - If going UP: serve all calls (car + hall UP) in UP direction
        - If going DOWN: serve all calls (car + hall DOWN) in DOWN direction
        """
        if direction == "UP":
            # Collect all UP-direction calls above current floor
            candidates = set()
            candidates.update(f for f in car_calls if f > current_floor)
            candidates.update(f for f in hall_calls_up if f > current_floor)
            
            if candidates:
                return min(candidates)  # Closest floor above
        
        elif direction == "DOWN":
            # Collect all DOWN-direction calls below current floor
            candidates = set()
            candidates.update(f for f in car_calls if f < current_floor)
            candidates.update(f for f in hall_calls_down if f < current_floor)
            
            if candidates:
                return max(candidates)  # Closest floor below
        
        return None
    
    def _reverse_direction(self, direction: str) -> str:
        """Reverse the direction."""
        if direction == "UP":
            return "DOWN"
        elif direction == "DOWN":
            return "UP"
        else:
            return "UP"  # Default
    
    def _determine_stop_reason(
        self,
        floor: int,
        direction: str,
        car_calls: set,
        hall_calls_up: set,
        hall_calls_down: set
    ) -> Tuple[str, str]:
        """
        Determine why elevator is stopping and the service direction.
        
        Returns:
            (stop_reason, stop_direction)
        """
        is_car_call = floor in car_calls
        is_hall_call_up = floor in hall_calls_up
        is_hall_call_down = floor in hall_calls_down
        
        # Determine stop reason
        if is_hall_call_up or is_hall_call_down:
            stop_reason = "hall_call"
        elif is_car_call:
            stop_reason = "car_call"
        else:
            stop_reason = "unknown"
        
        # Determine service direction
        # At top floor, always serve DOWN
        if floor == self.num_floors:
            stop_direction = "DOWN"
        # At bottom floor, always serve UP
        elif floor == 1:
            stop_direction = "UP"
        # Otherwise, serve in current direction
        else:
            stop_direction = direction
        
        return stop_reason, stop_direction
    
    def _consume_calls_at_floor(
        self,
        floor: int,
        direction: str,
        car_calls: set,
        hall_calls_up: set,
        hall_calls_down: set
    ) -> None:
        """
        Consume (remove) calls that would be served at this stop.
        
        - Car calls: always consumed
        - Hall calls: consumed based on direction
        """
        # Always consume car call
        car_calls.discard(floor)
        
        # Consume hall calls based on service direction
        if direction == "UP":
            hall_calls_up.discard(floor)
        elif direction == "DOWN":
            hall_calls_down.discard(floor)
        
        # At top/bottom floors, consume both directions
        if floor == self.num_floors:
            hall_calls_up.discard(floor)
            hall_calls_down.discard(floor)
        elif floor == 1:
            hall_calls_up.discard(floor)
            hall_calls_down.discard(floor)
    
    def _get_travel_time(self, elevator_name: str, from_floor: int, to_floor: int) -> float:
        """
        Get travel time between two floors for an elevator.
        
        Args:
            elevator_name: Name of elevator
            from_floor: Origin floor
            to_floor: Destination floor
        
        Returns:
            Travel time in seconds
        """
        return self.travel_time_provider.get_travel_time(elevator_name, from_floor, to_floor)
    
    def _get_stop_time(self, floor: int, direction: str) -> float:
        """
        Get estimated stop duration at a floor.
        
        Args:
            floor: Floor number
            direction: Direction at stop
        
        Returns:
            Stop duration in seconds
        """
        return self.travel_time_provider.get_stop_time(floor, direction)


# TODO: Future implementation (Phase 3)
# class OperationalDataLearner:
#     """
#     Learns operational data from actual elevator movements.
#     
#     This will be implemented in a separate file (operational_data_learner.py)
#     when learning functionality is needed.
#     
#     Responsibilities:
#     - Monitor elevator movements via message broker
#     - Learn inter-floor travel times
#     - Learn advanced position transition times
#     - Learn stop durations
#     - Provide learned data via LearnedDataProvider
#     """
#     pass
