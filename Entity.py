# File: Entity.py
import simpy
from abc import ABC, abstractmethod
import itertools  # Helper for entity ID counter
from typing import Optional  # Add Optional for type hints

class Entity(ABC):
    """
    Abstract base class for entities in SimPy simulation.

    This class defines common attributes and behaviors for entities that operate
    as SimPy processes, providing a foundation for entity lifecycle management
    in the SimPy environment.
    """
    # Entity ID counter shared across all class instances
    _entity_id_counter = itertools.count()

    def __init__(self, env: simpy.Environment, name: str = None):
        """
        Initialize the entity.

        Args:
            env: The SimPy simulation environment this entity belongs to.
            name: Entity name. Optional. If not specified, auto-generated from class name and ID.
        """
        self.env = env
        # Generate unique entity ID
        self.entity_id: int = next(self._entity_id_counter)
        # Set entity name
        self.name: str = name if name is not None else f"{self.__class__.__name__}_{self.entity_id}"

        # Variable to hold the current state of the entity
        # Specific state values are defined and used in concrete classes (e.g., 'idle', 'moving', 'waiting', etc.)
        self.state: str = "initial_state"  # Set default value as initial state (recommended to override in concrete classes)

        # SimPy process object corresponding to this entity
        # Start as a process that executes the run() method within the constructor
        # The run() method is implemented in subclasses
        self._process = self.env.process(self.run())

        # Initialization completion log
        print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}, ID:{self.entity_id}) created.')
        # Initial state transition log (assuming initial state changes from 'initial_state')
        # If initial state is set in concrete class, it might be more appropriate to call
        # set_state in the concrete class's __init__. Here we log as the state immediately after creation.
        # self._log_state_change(self.state)  # Enable if initial state logging is needed


    @abstractmethod
    def run(self):
        """
        Generator method that serves as the main SimPy process body for the entity (abstract method).

        This method is executed by the SimPy environment and defines the main behavior
        of the entity in the simulation. Within this method, use yield to wait for event
        completion and advance simulation time.
        Must be implemented in subclasses. Typically structured as an infinite loop
        that calls processing based on state.

        Example:
            while True:
                if self.state == 'StateA':
                    yield from self._state_A()
                elif self.state == 'StateB':
                    yield from self._state_B()
                else:
                    # Handle undefined state (error logging, etc.)
                    print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}) unknown state: {self.state}')
                    yield self.env.timeout(1)  # Wait to prevent infinite loop
        """
        pass  # No concrete implementation as this is an abstract method

    # --- Common utility methods ---

    def set_state(self, new_state: str):
        """
        Transition the entity's state.

        Args:
            new_state: String representing the target state for transition.
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self._log_state_change(old_state, new_state)

    def get_state(self) -> str:
        """
        Get the current state of the entity.

        Returns:
            String representing the current state.
        """
        return self.state

    def _log_state_change(self, old_state: str, new_state: str):
        """
        Internal helper method to log state transitions.
        Logging verbosity and format can be customized as needed.
        """
        print(f'{self.env.now:.2f}: Entity "{self.name}" ({self.__class__.__name__}, ID:{self.entity_id}) state transition: {old_state} -> {new_state}')

    # Access to SimPy process object
    @property
    def process(self) -> simpy.Process:
        """
        Get the SimPy process object for this entity.
        Can be used for operations like interrupting the process.
        """
        return self._process

    # Add state-specific abstract methods as needed
    # @abstractmethod
    # def _state_some_state(self):
    #     """ Processing for 'some_state' state (implement in subclass)"""
    #     pass

    # The concept equivalent to delays() in ESM.java is often written directly
    # in each state method in SimPy as yield self.env.timeout(time).
    # If a common method for calculating delay times based on state is needed,
    # it can also be added here.
    # Example:
    # def get_delay_for_current_state(self) -> float:
    #    """Return standard delay time corresponding to current state."""
    #    # Implement logic to return delay time based on state in concrete class
    #    return 0.0  # Default value
