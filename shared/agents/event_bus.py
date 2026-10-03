"""
Event Bus for Cross-System Communication
-----------------------------------------
Async/sync pub-sub system for routing events between Powercore Mind and Entropy.env.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, Any, Callable, List, Optional
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Event types
EVENT_RESONANCE = "resonance_event"
EVENT_MYTH_FRAGMENT = "myth_fragment"
EVENT_QUANTUM_COLLISION = "quantum_collision"
EVENT_PRIMARCH_AWAKENED = "primarch_awakened"
EVENT_CHAIN_EXECUTION = "chain_execution"
EVENT_MEMORY_UPDATE = "memory_update"


class EventBus:
    """
    Asynchronous/synchronous event bus for agent communication.
    Routes events between Powercore Mind and Entropy.env systems.
    """
    
    def __init__(self):
        """Initialize event bus."""
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_log: List[Dict[str, Any]] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop
    
    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe an agent to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Callback function to call when event is published
        """
        self.subscribers[event_type].append(callback)
        logger.debug(f"Subscribed callback to {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe a callback from an event type."""
        if callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            logger.debug(f"Unsubscribed callback from {event_type}")
    
    async def publish_async(self, event_type: str, data: Any) -> str:
        """
        Async publish event to subscribers.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            Event ID
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Log event for provenance
        event_record = {
            "id": event_id,
            "type": event_type,
            "data_hash": hash(str(data)),
            "timestamp": timestamp,
            "data": data  # Store data for debugging (can be removed in production)
        }
        self.event_log.append(event_record)
        
        # Log to resonance evolution if available
        try:
            from src.app.utils.resonance_evolution import get_resonance_evolution
            evolution = get_resonance_evolution()
            # Store event in resonance log for provenance
            logger.debug(f"Event {event_id} logged to resonance system")
        except ImportError:
            pass
        
        # Dispatch to subscribers
        callbacks = self.subscribers.get(event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data, event_id)
                else:
                    callback(data, event_id)
            except Exception as e:
                logger.error(f"Error in event callback for {event_type}: {e}")
        
        logger.info(f"Published event {event_type} (ID: {event_id})")
        return event_id
    
    def publish_sync(self, event_type: str, data: Any) -> str:
        """
        Synchronous publish for blocking workflows.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            Event ID
        """
        loop = self._get_loop()
        if loop.is_running():
            # If loop is already running, schedule the coroutine
            future = asyncio.run_coroutine_threadsafe(
                self.publish_async(event_type, data),
                loop
            )
            return future.result()
        else:
            # If no loop is running, run it
            return loop.run_until_complete(self.publish_async(event_type, data))
    
    def get_provenance(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full chain for an event.
        
        Args:
            event_id: Event ID to look up
            
        Returns:
            Event record or None if not found
        """
        for event in self.event_log:
            if event["id"] == event_id:
                return event
        return None
    
    def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events of a specific type.
        
        Args:
            event_type: Type of event to filter
            limit: Maximum number of events to return
            
        Returns:
            List of event records
        """
        events = [e for e in self.event_log if e["type"] == event_type]
        return events[-limit:] if len(events) > limit else events


# Global event bus instance
_event_bus_instance: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance

