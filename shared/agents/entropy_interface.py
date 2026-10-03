"""
Entropy.env Interface
---------------------
Wrapper functions for Entropy.env-specific agent calls with mode="mythos".
Integrates with nodeverse, Primarch events, and myth fragment ingestion.
"""

import logging
from typing import Dict, Any, Optional, List

from .council.resonance_to_myth import ResonanceToMythAgent
from .council.myth_to_rag import MythToRagAgent
from .council.quantum_collision import QuantumCollisionWatcher
from .event_bus import get_event_bus, EVENT_MYTH_FRAGMENT, EVENT_PRIMARCH_AWAKENED

logger = logging.getLogger(__name__)


class EntropyInterface:
    """
    Interface for Entropy.env to interact with shared agent council.
    All agents run in mode="mythos" for Entropy.env-specific behavior.
    """
    
    def __init__(self):
        """Initialize Entropy.env interface with all agents."""
        self.resonance_to_myth = ResonanceToMythAgent(mode="mythos")
        self.myth_to_rag = MythToRagAgent(mode="mythos")
        self.quantum_collision = QuantumCollisionWatcher(mode="mythos")
        self.event_bus = get_event_bus()
    
    def ingest_myth_fragment(self, myth_fragment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest myth fragment into Entropy.env nodeverse.
        
        Args:
            myth_fragment: Myth fragment dictionary
            
        Returns:
            Ingestion result
        """
        # TODO: Implement Entropy.env nodeverse ingestion
        # For now, just publish event
        self.event_bus.publish_sync(
            EVENT_MYTH_FRAGMENT,
            myth_fragment
        )
        
        logger.info(f"Ingested myth fragment {myth_fragment.get('id')} into Entropy.env")
        
        return {
            "success": True,
            "myth_id": myth_fragment.get("id"),
            "rarity": myth_fragment.get("rarity", "common")
        }
    
    def spawn_primarch_from_resonance(
        self,
        resonance_event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Spawn Primarch suggestion from resonance event.
        
        Args:
            resonance_event: Resonance event dictionary
            
        Returns:
            Primarch suggestion or None
        """
        # Extract nodes from resonance event
        # This is a placeholder - in production, you'd query the nodeverse
        logger.debug(f"Spawning Primarch from resonance event {resonance_event.get('id')}")
        
        # For now, return None (will be implemented when nodeverse is integrated)
        return None
    
    def primarch_council_suggest(
        self,
        resonance_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get Primarch council suggestion based on resonance context.
        
        Args:
            resonance_context: Resonance context dictionary
            
        Returns:
            Primarch suggestion
        """
        # TODO: Implement Primarch council logic
        # For now, return placeholder
        return {
            "success": False,
            "error": "Primarch council not yet implemented"
        }
    
    def detect_node_collisions(
        self,
        nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect node collisions in Entropy.env nodeverse.
        
        Args:
            nodes: List of nodes from nodeverse
            
        Returns:
            Collision detection results
        """
        return self.quantum_collision.execute({"nodes": nodes})
    
    def subscribe_to_events(self):
        """Subscribe to relevant events from event bus."""
        # Subscribe to resonance events (spawn Primarchs)
        from .event_bus import EVENT_RESONANCE
        self.event_bus.subscribe(
            EVENT_RESONANCE,
            lambda data, event_id: self._handle_resonance_event(data, event_id)
        )
    
    def _handle_resonance_event(self, data: Dict[str, Any], event_id: str):
        """Handle resonance event (spawn Primarch)."""
        try:
            primarch = self.spawn_primarch_from_resonance(data)
            if primarch:
                logger.info(f"Spawned Primarch {primarch.get('id')} from resonance event")
        except Exception as e:
            logger.error(f"Error handling resonance event: {e}")


# Global Entropy.env interface instance
_entropy_interface_instance: Optional[EntropyInterface] = None


def get_entropy_interface() -> EntropyInterface:
    """Get or create the global Entropy.env interface instance."""
    global _entropy_interface_instance
    if _entropy_interface_instance is None:
        _entropy_interface_instance = EntropyInterface()
        _entropy_interface_instance.subscribe_to_events()
    return _entropy_interface_instance

