"""
Shared Agents Module
--------------------
Agent council infrastructure for Powercore-Entropy fusion.
"""

from .powercore_interface import PowercoreInterface, get_powercore_interface
from .entropy_interface import EntropyInterface, get_entropy_interface
from .event_bus import EventBus, get_event_bus
from .logic_glob import LogicGlob

__all__ = [
    "PowercoreInterface",
    "get_powercore_interface",
    "EntropyInterface",
    "get_entropy_interface",
    "EventBus",
    "get_event_bus",
    "LogicGlob"
]

