"""
Group Control System Configuration

This configuration is used both in simulation and real elevator systems.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class AllocationStrategyConfig:
    """Configuration for call allocation strategy"""
    name: str = "NearestCar"
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.name:
            raise ValueError("allocation_strategy.name cannot be empty")


@dataclass
class RepositioningStrategyConfig:
    """Configuration for elevator repositioning strategy"""
    name: str = "None"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReassignmentPolicyConfig:
    """Configuration for call reassignment policy"""
    enabled: bool = False
    name: str = "EarliestArrival"
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.enabled and not self.name:
            raise ValueError("reassignment_policy.name cannot be empty when enabled")


@dataclass
class GroupControlConfig:
    """
    Group Control System configuration
    
    This configuration is used both in simulation and real elevator systems.
    Contains only control logic settings, not physical specifications.
    """
    allocation_strategy: AllocationStrategyConfig
    repositioning_strategy: Optional[RepositioningStrategyConfig] = None
    reassignment_policy: Optional[ReassignmentPolicyConfig] = None
    
    def __post_init__(self):
        # Set defaults if not provided
        if self.repositioning_strategy is None:
            self.repositioning_strategy = RepositioningStrategyConfig()
        if self.reassignment_policy is None:
            self.reassignment_policy = ReassignmentPolicyConfig()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GroupControlConfig':
        """Create GroupControlConfig from dictionary"""
        gc_data = data.get('group_control', data)
        
        # Parse allocation_strategy
        alloc_data = gc_data.get('allocation_strategy', {})
        allocation_strategy = AllocationStrategyConfig(
            name=alloc_data.get('name', 'NearestCar'),
            parameters=alloc_data.get('parameters', {})
        )
        
        # Parse repositioning_strategy
        repos_data = gc_data.get('repositioning_strategy', {})
        repositioning_strategy = RepositioningStrategyConfig(
            name=repos_data.get('name', 'None'),
            parameters=repos_data.get('parameters', {})
        )
        
        # Parse reassignment_policy
        reassign_data = gc_data.get('reassignment_policy', {})
        reassignment_policy = ReassignmentPolicyConfig(
            enabled=reassign_data.get('enabled', False),
            name=reassign_data.get('name', 'EarliestArrival'),
            parameters=reassign_data.get('parameters', {})
        )
        
        return cls(
            allocation_strategy=allocation_strategy,
            repositioning_strategy=repositioning_strategy,
            reassignment_policy=reassignment_policy
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'group_control': {
                'allocation_strategy': {
                    'name': self.allocation_strategy.name,
                    'parameters': self.allocation_strategy.parameters
                },
                'repositioning_strategy': {
                    'name': self.repositioning_strategy.name,
                    'parameters': self.repositioning_strategy.parameters
                },
                'reassignment_policy': {
                    'enabled': self.reassignment_policy.enabled,
                    'name': self.reassignment_policy.name,
                    'parameters': self.reassignment_policy.parameters
                }
            }
        }
    
    def validate(self):
        """Validate configuration consistency"""
        # Allocation strategy is required
        if not self.allocation_strategy.name:
            raise ValueError("allocation_strategy.name is required")
        
        # If reassignment is enabled, name must be provided
        if self.reassignment_policy.enabled and not self.reassignment_policy.name:
            raise ValueError("reassignment_policy.name is required when enabled")

