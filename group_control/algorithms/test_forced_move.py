from typing import List, Dict
from ..interfaces.repositioning_strategy import IRepositioningStrategy

class TestForcedMoveStrategy(IRepositioningStrategy):
    """
    Test strategy: Send forced_move_command when elevator becomes IDLE
    
    This is a test/demo implementation to verify forced_move_command functionality.
    When an elevator becomes IDLE, it sends a forced_move_command to return the
    elevator to home_floor with main_direction.
    
    Purpose:
        - Verify forced_move_command reception and execution
        - Test that elevator treats forced call as real hall call
        - Demonstrate selective collective response behavior
        - Validate door opening at arrival
    
    Behavior:
        - Detects when elevator transitions to IDLE state
        - Checks if elevator is NOT already at home_floor
        - Sends forced_move_command to (home_floor, main_direction)
        - Tracks sent commands to avoid duplicates
        - Resets tracking when elevator becomes non-IDLE
    """
    
    def __init__(self):
        """Initialize strategy with command tracking"""
        self.sent_commands = set()  # Track which elevators already received command
    
    def evaluate(self, elevator_name: str, status: dict, all_statuses: dict) -> List[dict]:
        """
        Evaluate if forced_move_command should be sent
        
        Args:
            elevator_name: Name of the elevator whose status was updated
            status: Current status of this elevator
            all_statuses: Status of all elevators
        
        Returns:
            List containing one forced_move command if elevator just became IDLE
            at a floor other than home_floor, empty list otherwise
        """
        commands = []
        
        current_state = status.get('state')
        
        # Check if elevator is in IDLE state
        if current_state == 'IDLE':
            # Only send command once per IDLE period
            if elevator_name not in self.sent_commands:
                home_floor = status.get('home_floor', 1)
                current_floor = status.get('current_floor', 1)
                main_direction = status.get('main_direction', 'UP')
                
                # Don't send command if elevator is already at home_floor
                if current_floor != home_floor:
                    # Create forced_move_command
                    commands.append({
                        'type': 'forced_move',
                        'elevator': elevator_name,
                        'floor': home_floor,
                        'direction': main_direction
                    })
                    
                    print(f"[TestForcedMove] Strategy triggered for {elevator_name}: forced_move to {home_floor} {main_direction}")
                
                # Mark this elevator as having received command (even if already at home_floor)
                self.sent_commands.add(elevator_name)
        else:
            # Elevator is no longer IDLE - reset tracking for next IDLE period
            if elevator_name in self.sent_commands:
                self.sent_commands.discard(elevator_name)
        
        return commands
    
    def get_strategy_name(self) -> str:
        """Return strategy name"""
        return "Test Forced Move (IDLE → home_floor+main_direction)"

