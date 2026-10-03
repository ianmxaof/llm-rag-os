"""
Mem0 Memory Module
------------------
Local Mem0 instance for persistent, adaptive memory layer.
Replaces JSONL resonance logging with graph-based memory system.
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import streamlit as st

logger = logging.getLogger(__name__)

# Try to import Mem0
try:
    from mem0 import Memory
    HAS_MEM0 = True
except ImportError:
    HAS_MEM0 = False
    logger.warning("Mem0 not installed. Install with: pip install mem0ai==0.1.22")


class Mem0Memory:
    """Mem0 memory layer for Powercore Mind."""
    
    def __init__(self, user_id: str = "powercore_user"):
        """
        Initialize Mem0 memory instance.
        
        Args:
            user_id: User ID for memory isolation
        """
        self.user_id = user_id
        self.memory: Optional[Any] = None
        
        if not HAS_MEM0:
            logger.error("Mem0 not available - install with: pip install mem0ai==0.1.22")
            return
        
        try:
            # Initialize local Mem0 instance (self-hosted, no cloud)
            # Use nomic-embed-text-v1.5 as embedder (already in vault)
            self.memory = Memory(
                embedding_model="nomic-embed-text-v1.5"
            )
            logger.info("Mem0 memory initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0: {e}")
            self.memory = None
    
    def add_memory(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a memory to Mem0.
        
        Args:
            text: Text content to remember
            metadata: Optional metadata (resonance_score, combo_score, god_chain, etc.)
            
        Returns:
            True if added successfully
        """
        if not self.memory:
            return False
        
        try:
            # Prepare metadata
            mem_metadata = metadata or {}
            
            # Add memory
            self.memory.add(
                text=text,
                user_id=self.user_id,
                metadata=mem_metadata
            )
            
            logger.info(f"Added memory to Mem0: {text[:100]}...")
            
            # Trigger Quantum Collision Watcher on memory updates
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
                from shared.agents.powercore_interface import get_powercore_interface
                
                powercore = get_powercore_interface()
                # Check for collisions asynchronously (don't block memory addition)
                # This could be done in a background thread in production
                powercore.check_quantum_collisions()
            except Exception as e:
                logger.debug(f"Quantum Collision Watcher not available: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding memory to Mem0: {e}")
            return False
    
    def search_memories(
        self,
        query: str,
        limit: int = 20,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Search memories by query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters (e.g., {"resonance_score": 1.0})
            
        Returns:
            List of memory dictionaries
        """
        if not self.memory:
            return []
        
        try:
            # Search memories
            results = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit,
                filters=filters
            )
            
            # Convert to list of dicts
            memories = []
            if results:
                for result in results:
                    memories.append({
                        "text": result.get("memory", ""),
                        "metadata": result.get("metadata", {}),
                        "score": result.get("score", 0.0)
                    })
            
            return memories
            
        except Exception as e:
            logger.error(f"Error searching Mem0 memories: {e}")
            return []
    
    def add_chain_execution(
        self,
        chain_name: str,
        chain_output: str,
        combo_score: Optional[float] = None,
        steps: Optional[List[Dict]] = None
    ) -> bool:
        """
        Add a chain execution to memory.
        
        Args:
            chain_name: Name of the chain
            chain_output: Final output from chain
            combo_score: Optional combo meter score
            steps: Optional chain steps
            
        Returns:
            True if added successfully
        """
        # Build memory text
        memory_text = f"Chain: {chain_name}\n\nOutput: {chain_output}"
        
        if steps:
            memory_text += "\n\nSteps:\n"
            for i, step in enumerate(steps):
                memory_text += f"{i+1}. {step.get('description', 'Unknown')}\n"
        
        metadata = {
            "type": "chain_execution",
            "chain_name": chain_name,
            "combo_score": combo_score or 0.0,
            "god_chain": combo_score and combo_score >= 100.0
        }
        
        return self.add_memory(memory_text, metadata)
    
    def add_resonance_event(
        self,
        response: str,
        combo_score: Optional[float] = None,
        chain_name: Optional[str] = None
    ) -> bool:
        """
        Add a resonance event to memory.
        
        Args:
            response: Response that triggered resonance
            combo_score: Optional combo meter score
            chain_name: Optional chain name
            
        Returns:
            True if added successfully
        """
        metadata = {
            "type": "resonance_event",
            "resonance_score": 1.0,
            "combo_score": combo_score or 0.0,
            "chain_name": chain_name
        }
        
        return self.add_memory(response, metadata)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored memories.
        
        Returns:
            Dictionary with stats
        """
        if not self.memory:
            return {
                "total_memories": 0,
                "resonance_events": 0,
                "god_chains": 0
            }
        
        try:
            # Search for all memories (this is a simplified approach)
            # In production, Mem0 might have a count method
            all_memories = self.search_memories("", limit=10000)
            
            resonance_count = sum(
                1 for m in all_memories
                if m.get("metadata", {}).get("type") == "resonance_event"
            )
            
            god_chain_count = sum(
                1 for m in all_memories
                if m.get("metadata", {}).get("god_chain", False)
            )
            
            return {
                "total_memories": len(all_memories),
                "resonance_events": resonance_count,
                "god_chains": god_chain_count
            }
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {
                "total_memories": 0,
                "resonance_events": 0,
                "god_chains": 0
            }


# Global Mem0 instance
_mem0_instance: Optional[Mem0Memory] = None


def get_mem0_memory() -> Mem0Memory:
    """Get or create the global Mem0 memory instance."""
    global _mem0_instance
    if _mem0_instance is None:
        _mem0_instance = Mem0Memory()
    return _mem0_instance

