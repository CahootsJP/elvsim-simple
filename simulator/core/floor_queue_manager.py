"""
Floor Queue Manager for unified queue handling across Traditional, DCS, and Hybrid systems.

Supports:
- Traditional UP-DOWN: queue[floor][direction]
- Full DCS: queue[floor][car]
- Hybrid DCS: Mixed structure based on floor type
"""

import simpy
from typing import Optional, List
from ..interfaces.call_system import ICallSystem


class FloorQueueManager:
    """
    Unified queue management for different call systems.
    
    Traditional floors: queue[floor][direction] (UP/DOWN)
    DCS floors: queue[floor][elevator_name] (Elevator_1, Elevator_2, ...)
    """
    
    def __init__(self, env: simpy.Environment, num_floors: int, num_elevators: int, call_system: ICallSystem):
        """
        Initialize floor queue manager.
        
        Args:
            env: SimPy environment
            num_floors: Number of floors (1-indexed)
            num_elevators: Number of elevators
            call_system: Call system interface to determine floor types
        """
        self.env = env
        self.num_floors = num_floors
        self.num_elevators = num_elevators
        self.call_system = call_system
        
        # Generate elevator names
        self.elevator_names = [f"Elevator_{i}" for i in range(1, num_elevators + 1)]
        
        # Initialize queues based on floor type
        self._queues = {}
        for floor in range(1, num_floors + 1):
            self._queues[floor] = {}
            
            if call_system.is_dcs_floor(floor):
                # DCS floor: queue per elevator
                for elev_name in self.elevator_names:
                    self._queues[floor][elev_name] = simpy.Store(env)
            else:
                # Traditional floor: queue per direction
                self._queues[floor]["UP"] = simpy.Store(env)
                self._queues[floor]["DOWN"] = simpy.Store(env)
    
    def get_queue(self, floor: int, elevator_name: Optional[str] = None, direction: Optional[str] = None) -> simpy.Store:
        """
        Get appropriate queue based on floor type.
        
        Args:
            floor: Floor number (1-indexed)
            elevator_name: Elevator name (required for DCS floors)
            direction: Direction "UP" or "DOWN" (required for Traditional floors)
        
        Returns:
            SimPy Store queue
        
        Raises:
            ValueError: If required parameter is missing for floor type
        """
        if floor < 1 or floor > self.num_floors:
            raise ValueError(f"Floor {floor} is out of range (1-{self.num_floors})")
        
        if self.call_system.is_dcs_floor(floor):
            # DCS floor: elevator_name is required
            if elevator_name is None:
                raise ValueError(f"DCS floor {floor} requires elevator_name parameter")
            if elevator_name not in self._queues[floor]:
                raise ValueError(f"Elevator {elevator_name} not found in queues for floor {floor}")
            return self._queues[floor][elevator_name]
        else:
            # Traditional floor: direction is required
            if direction is None:
                raise ValueError(f"Traditional floor {floor} requires direction parameter (UP or DOWN)")
            if direction not in ["UP", "DOWN"]:
                raise ValueError(f"Direction must be 'UP' or 'DOWN', got '{direction}'")
            if direction not in self._queues[floor]:
                raise ValueError(f"Direction {direction} not found in queues for floor {floor}")
            return self._queues[floor][direction]
    
    def move_passenger(self, passenger, floor: int, from_elevator: str, to_elevator: str):
        """
        Move passenger between elevator queues (for DCS reassignment after being left behind).
        
        Args:
            passenger: Passenger object to move
            floor: Floor number
            from_elevator: Source elevator name
            to_elevator: Destination elevator name
        
        Raises:
            ValueError: If floor is not DCS floor or elevators are invalid
        """
        if not self.call_system.is_dcs_floor(floor):
            raise ValueError(f"Cannot move passenger: Floor {floor} is not a DCS floor")
        
        if from_elevator not in self._queues[floor]:
            raise ValueError(f"Source elevator {from_elevator} not found in queues for floor {floor}")
        if to_elevator not in self._queues[floor]:
            raise ValueError(f"Destination elevator {to_elevator} not found in queues for floor {floor}")
        
        from_queue = self._queues[floor][from_elevator]
        to_queue = self._queues[floor][to_elevator]
        
        # Remove passenger from source queue
        if passenger not in from_queue.items:
            raise ValueError(f"Passenger {passenger.name} not found in source queue {from_elevator} at floor {floor}")
        
        from_queue.items.remove(passenger)
        
        # Add passenger to destination queue
        # Note: We use put() which is a generator, so this should be called with yield
        # But for simplicity, we'll add directly to items and let the workflow handle it
        to_queue.items.append(passenger)
        
        print(f"{self.env.now:.2f} [QueueManager] Moved {passenger.name} from {from_elevator} to {to_elevator} queue at floor {floor}")
    
    def get_all_waiting_passengers(self, floor: int) -> List:
        """
        Get all waiting passengers at a floor (for statistics/metrics).
        
        Args:
            floor: Floor number
        
        Returns:
            List of all waiting passengers
        """
        if floor < 1 or floor > self.num_floors:
            return []
        
        all_passengers = []
        
        if self.call_system.is_dcs_floor(floor):
            # DCS floor: collect from all elevator queues
            for elev_name in self.elevator_names:
                if elev_name in self._queues[floor]:
                    all_passengers.extend(self._queues[floor][elev_name].items)
        else:
            # Traditional floor: collect from UP and DOWN queues
            if "UP" in self._queues[floor]:
                all_passengers.extend(self._queues[floor]["UP"].items)
            if "DOWN" in self._queues[floor]:
                all_passengers.extend(self._queues[floor]["DOWN"].items)
        
        return all_passengers
    
    def get_boarding_queues_for_elevator(self, floor: int, elevator_name: str) -> List[simpy.Store]:
        """
        Get boarding queues for a specific elevator at a specific floor.
        
        For DCS floors: Returns the queue for the specified elevator
        For Traditional floors: Returns UP and/or DOWN queues based on elevator's direction
        
        Args:
            floor: Floor number
            elevator_name: Elevator name
        
        Returns:
            List of SimPy Store queues
        """
        if self.call_system.is_dcs_floor(floor):
            # DCS floor: return only this elevator's queue
            return [self.get_queue(floor, elevator_name=elevator_name)]
        else:
            # Traditional floor: return direction queues (caller should filter by direction)
            queues = []
            if "UP" in self._queues[floor]:
                queues.append(self._queues[floor]["UP"])
            if "DOWN" in self._queues[floor]:
                queues.append(self._queues[floor]["DOWN"])
            return queues

