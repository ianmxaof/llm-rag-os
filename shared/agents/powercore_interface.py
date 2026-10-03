"""
Powercore Interface
--------------------
Wrapper functions for Powercore-specific agent calls with mode="resonance".
Integrates with combo meter, chain editor, and ethical continuum.
"""

import logging
from typing import Dict, Any, Optional

from .council.resonance_to_myth import ResonanceToMythAgent
from .council.myth_to_rag import MythToRagAgent
from .council.quantum_collision import QuantumCollisionWatcher
from .council.resonance_sentinel import ResonanceSentinel
from .event_bus import get_event_bus, EVENT_RESONANCE, EVENT_MYTH_FRAGMENT

logger = logging.getLogger(__name__)


class PowercoreInterface:
    """
    Interface for Powercore Mind to interact with shared agent council.
    All agents run in mode="resonance" for Powercore-specific behavior.
    """
    
    def __init__(self):
        """Initialize Powercore interface with all agents."""
        self.resonance_to_myth = ResonanceToMythAgent(mode="resonance")
        self.myth_to_rag = MythToRagAgent(mode="resonance")
        self.quantum_collision = QuantumCollisionWatcher(mode="resonance")
        self.resonance_sentinel = ResonanceSentinel(mode="resonance")
        self.event_bus = get_event_bus()
    
    def on_resonance_achieved(
        self,
        chain_output: str,
        combo_score: float,
        chain_name: str,
        chain_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle "Resonance Achieved" button click.
        Creates myth fragment in Entropy.env.
        
        Args:
            chain_output: Final chain output
            combo_score: Combo meter score
            chain_name: Name of the chain
            chain_context: Optional full chain context
            
        Returns:
            Result dictionary
        """
        logger.info(f"Resonance achieved for chain {chain_name} (combo: {combo_score:.1f})")
        
        # Create myth fragment
        result = self.resonance_to_myth.trigger_from_resonance_button(
            chain_output=chain_output,
            combo_score=combo_score,
            chain_name=chain_name,
            chain_context=chain_context
        )
        
        # Auto-inject into RAG if successful
        if result.get("success") and result.get("myth_fragment"):
            myth_fragment = result["myth_fragment"]
            rag_result = self.myth_to_rag.execute({"myth_fragment": myth_fragment})
            if rag_result.get("success"):
                logger.info(f"Myth fragment {myth_fragment['id']} injected into RAG")
        
        return result
    
    def on_high_combo(
        self,
        chain_output: str,
        combo_score: float,
        chain_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-trigger myth creation on high combo scores.
        
        Args:
            chain_output: Final chain output
            combo_score: Combo meter score
            chain_name: Name of the chain
            
        Returns:
            Result dictionary or None if threshold not met
        """
        return self.resonance_to_myth.trigger_from_combo_threshold(
            chain_output=chain_output,
            combo_score=combo_score,
            chain_name=chain_name
        )
    
    def scan_chain_output(
        self,
        chain_output: str,
        ethical_mode: float
    ) -> Dict[str, Any]:
        """
        Scan chain output for despair patterns.
        
        Args:
            chain_output: Chain output to scan
            ethical_mode: Ethical continuum value (0.0-1.0)
            
        Returns:
            Scan results with potentially modulated output
        """
        self.resonance_sentinel.update_ethical_mode(ethical_mode)
        return self.resonance_sentinel.scan_chain_output(
            chain_output=chain_output,
            ethical_mode=ethical_mode
        )
    
    def check_quantum_collisions(self) -> Dict[str, Any]:
        """
        Check Mem0 graph for quantum collisions.
        
        Returns:
            Collision scan results
        """
        return self.quantum_collision.monitor_mem0_graph()
    
    def inject_myth_fragment(self, myth_fragment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject myth fragment into RAG system.
        
        Args:
            myth_fragment: Myth fragment dictionary
            
        Returns:
            Injection result
        """
        return self.myth_to_rag.execute({"myth_fragment": myth_fragment})
    
    def process_primarch_suggestion(
        self,
        primarch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process Primarch suggestion and inject as new chain in Powercore IDE.
        
        Args:
            primarch: Primarch suggestion dictionary
            
        Returns:
            Processing result
        """
        suggestions = primarch.get("suggestions", [])
        if not suggestions:
            return {"success": False, "error": "No suggestions in Primarch"}
        
        # Create chain from first suggestion
        # Note: This would integrate with chain editor to create new chain
        # For now, return the suggestion for manual processing
        logger.info(f"Primarch {primarch['id']} suggests: {suggestions[0]}")
        
        return {
            "success": True,
            "primarch_id": primarch["id"],
            "suggestion": suggestions[0],
            "all_suggestions": suggestions,
            "rarity": primarch.get("rarity", "rare")
        }
    
    def subscribe_to_events(self):
        """Subscribe to relevant events from event bus."""
        # Subscribe to myth fragments (auto-inject into RAG)
        self.event_bus.subscribe(
            EVENT_MYTH_FRAGMENT,
            lambda data, event_id: self._handle_myth_fragment(data, event_id)
        )
        
        # Subscribe to Primarch awakenings (create chains)
        from .event_bus import EVENT_PRIMARCH_AWAKENED
        self.event_bus.subscribe(
            EVENT_PRIMARCH_AWAKENED,
            lambda data, event_id: self._handle_primarch_awakened(data, event_id)
        )
    
    def _handle_myth_fragment(self, data: Dict[str, Any], event_id: str):
        """Handle myth fragment event (auto-inject into RAG)."""
        try:
            result = self.inject_myth_fragment(data)
            if result.get("success"):
                logger.info(f"Auto-injected myth fragment {data.get('id')} into RAG")
        except Exception as e:
            logger.error(f"Error handling myth fragment: {e}")
    
    def _handle_primarch_awakened(self, data: Dict[str, Any], event_id: str):
        """Handle Primarch awakening event (create chain suggestion)."""
        try:
            result = self.process_primarch_suggestion(data)
            if result.get("success"):
                logger.info(f"Processed Primarch {data.get('id')} suggestion")
        except Exception as e:
            logger.error(f"Error handling Primarch: {e}")


# Global Powercore interface instance
_powercore_interface_instance: Optional[PowercoreInterface] = None


def get_powercore_interface() -> PowercoreInterface:
    """Get or create the global Powercore interface instance."""
    global _powercore_interface_instance
    if _powercore_interface_instance is None:
        _powercore_interface_instance = PowercoreInterface()
        _powercore_interface_instance.subscribe_to_events()
    return _powercore_interface_instance

