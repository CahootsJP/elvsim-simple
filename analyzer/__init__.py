"""
Elevator System Analyzer

This package provides statistical analysis and reporting tools
for elevator system performance data.

Components:
- Statistics: Base class for sensor-based data collection
- SimulationStatistics: Simulation-only metrics with "God's view"
- RealtimePerformanceMonitor: Real hardware compatible performance monitoring
"""

__version__ = "0.1.0"

from .statistics import Statistics
from .simulation_statistics import SimulationStatistics
from .realtime_monitor import RealtimePerformanceMonitor

__all__ = ['Statistics', 'SimulationStatistics', 'RealtimePerformanceMonitor']

