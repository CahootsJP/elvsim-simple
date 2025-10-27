"""
RealtimeEnvironment.py

A custom SimPy environment that synchronizes simulation time with real time.
Allows controlling simulation speed for debugging and visualization purposes.
"""

import simpy
import time


class RealtimeEnvironment(simpy.Environment):
    """
    Custom SimPy environment with real-time synchronization.
    
    Extends simpy.Environment to add real-time speed control.
    All timeout() calls are automatically synchronized with real time
    based on the speed_factor.
    
    Args:
        speed_factor (float): Speed multiplier for simulation
            - 1.0 = real-time (1 sim second = 1 real second)
            - 0.5 = half speed (1 sim second = 2 real seconds)
            - 2.0 = double speed (1 sim second = 0.5 real seconds)
            - 0.0 = no delay (fastest possible, default SimPy behavior)
    
    Example:
        >>> env = RealtimeEnvironment(speed_factor=0.5)  # Half speed
        >>> # All processes will run at half speed automatically
    """
    
    def __init__(self, speed_factor=1.0, initial_time=0):
        """
        Initialize RealtimeEnvironment.
        
        Args:
            speed_factor (float): Speed multiplier (default: 1.0 for real-time)
            initial_time (float): Initial simulation time (default: 0)
        """
        super().__init__(initial_time=initial_time)
        self.speed_factor = speed_factor
        self.real_start_time = time.time()
        self.sim_start_time = self.now
        
    def step(self):
        """
        Execute one simulation step and synchronize with real time.
        
        Overrides simpy.Environment.step() to add real-time synchronization.
        After each simulation step, calculates the required real-time delay
        and sleeps if necessary to maintain the desired speed_factor.
        """
        # Execute the simulation step
        result = super().step()
        
        # Apply real-time synchronization if speed_factor > 0
        if self.speed_factor > 0:
            # Calculate elapsed simulation time
            sim_elapsed = self.now - self.sim_start_time
            
            # Calculate target real time for this simulation time
            target_real_time = self.real_start_time + (sim_elapsed / self.speed_factor)
            
            # Get current real time
            current_real_time = time.time()
            
            # Calculate sleep time needed to synchronize
            sleep_time = target_real_time - current_real_time
            
            # Sleep if we're ahead of schedule
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        return result
    
    def set_speed(self, speed_factor):
        """
        Dynamically change simulation speed during runtime.
        
        This allows changing the speed without restarting the simulation.
        Useful for debugging (slow down) or testing (speed up).
        
        Args:
            speed_factor (float): New speed multiplier
                - 1.0 = real-time
                - 0.5 = half speed
                - 2.0 = double speed
                - 0.0 = no delay (fastest)
        
        Example:
            >>> env.set_speed(0.1)  # Slow down to 10% for debugging
            >>> env.set_speed(10.0)  # Speed up 10x for testing
        """
        # Reset timing references when changing speed
        self.speed_factor = speed_factor
        self.real_start_time = time.time()
        self.sim_start_time = self.now
    
    def get_speed(self):
        """
        Get current simulation speed factor.
        
        Returns:
            float: Current speed_factor value
        """
        return self.speed_factor

