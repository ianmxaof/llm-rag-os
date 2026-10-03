"""
Quantum Collision Watcher Agent
--------------------------------
Monitors Mem0 graph for low-activity + high-activity node collisions.
Spawns Primarch suggestions when collisions occur (RNG-based probability).
"""

import random
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent
from ..event_bus import get_event_bus, EVENT_QUANTUM_COLLISION, EVENT_PRIMARCH_AWAKENED

logger = logging.getLogger(__name__)


class QuantumCollisionWatcher(BaseAgent):
    """
    Watches for node collisions in Mem0 graph and spawns Primarch suggestions.
    Quantum RNG determines if collision produces a Primarch event.
    """
    
    def __init__(
        self,
        mode: str = "resonance",
        collision_probability_base: float = 0.3
    ):
        """
        Initialize Quantum Collision Watcher.
        
        Args:
            mode: Agent mode (default: "resonance")
            collision_probability_base: Base probability for collision events (default: 0.3)
        """
        super().__init__(mode=mode)
        self.collision_probability_base = collision_probability_base
        self.processed_collisions: set = set()  # Track processed collisions
    
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process node collision and potentially spawn Primarch.
        
        Expected input_data:
            - low_node: Dict - Low-activity node
            - high_node: Dict - High-activity node
            OR
            - nodes: List[Dict] - List of nodes to analyze for collisions
            
        Returns:
            Dict with collision result and potential Primarch suggestion
        """
        # Handle list of nodes (scan for collisions)
        if "nodes" in input_data:
            return self._scan_for_collisions(input_data["nodes"])
        
        # Handle specific collision
        low_node = input_data.get("low_node")
        high_node = input_data.get("high_node")
        
        if not low_node or not high_node:
            return {"success": False, "error": "Both low_node and high_node required"}
        
        # Check if collision already processed
        collision_id = self._get_collision_id(low_node, high_node)
        if collision_id in self.processed_collisions:
            logger.debug(f"Collision {collision_id} already processed")
            return {"success": True, "already_processed": True}
        
        # Calculate collision probability
        prob = self._calculate_collision_probability(low_node, high_node)
        
        # RNG: Does collision produce event?
        if random.random() > prob:
            return {
                "success": True,
                "event": "no_spawn",
                "probability": prob,
                "output": None
            }
        
        # Spawn Primarch suggestion
        primarch = self._spawn_primarch(low_node, high_node, prob)
        
        # Mark collision as processed
        self.processed_collisions.add(collision_id)
        
        # Log resonance
        self.log_resonance(
            event_id=primarch["id"],
            event_type="quantum_collision",
            score=prob,
            metadata={
                "low_node_id": low_node.get("id"),
                "high_node_id": high_node.get("id"),
                "rarity": primarch.get("rarity")
            }
        )
        
        # Publish events
        event_bus = get_event_bus()
        event_bus.publish_sync(
            EVENT_QUANTUM_COLLISION,
            {
                "collision_id": collision_id,
                "low_node": low_node,
                "high_node": high_node,
                "probability": prob
            }
        )
        
        event_bus.publish_sync(
            EVENT_PRIMARCH_AWAKENED,
            primarch
        )
        
        logger.info(f"Spawned Primarch {primarch['id']} from collision (prob: {prob:.2f})")
        
        return {
            "success": True,
            "event": "spawn",
            "probability": prob,
            "primarch": primarch
        }
    
    def _calculate_collision_probability(
        self,
        low_node: Dict[str, Any],
        high_node: Dict[str, Any]
    ) -> float:
        """
        Calculate probability of collision producing Primarch event.
        
        Theory: Low energy assisted by high energy = quantum event probability.
        
        Args:
            low_node: Low-activity node
            high_node: High-activity node
            
        Returns:
            Probability (0.0-1.0)
        """
        low_activity = low_node.get("activity", 0) or 0.1  # Avoid division by zero
        high_activity = high_node.get("activity", 0) or 1.0
        
        # Base probability from activity ratio
        energy_ratio = high_activity / max(low_activity, 0.1)
        prob = min(1.0, (energy_ratio * self.collision_probability_base))
        
        # Boost probability for high-rarity nodes
        low_rarity = low_node.get("rarity", "common")
        high_rarity = high_node.get("rarity", "common")
        
        rarity_boost = {
            "mythic": 0.4,
            "legendary": 0.3,
            "epic": 0.2,
            "rare": 0.1,
            "uncommon": 0.05,
            "common": 0.0
        }
        
        prob += rarity_boost.get(low_rarity, 0.0) * 0.5
        prob += rarity_boost.get(high_rarity, 0.0) * 0.5
        
        return min(1.0, prob)
    
    def _spawn_primarch(
        self,
        low_node: Dict[str, Any],
        high_node: Dict[str, Any],
        probability: float
    ) -> Dict[str, Any]:
        """
        Spawn Primarch suggestion from collision.
        
        Args:
            low_node: Low-activity node
            high_node: High-activity node
            probability: Collision probability
            
        Returns:
            Primarch suggestion dictionary
        """
        # Extract primitives from nodes
        low_primitive = low_node.get("primitive") or low_node.get("content", "")[:200]
        high_primitive = high_node.get("primitive") or high_node.get("content", "")[:200]
        
        # Generate Primarch suggestion using LLM
        primarch_prompt = f"""A quantum collision has occurred between two nodes:

Low-activity node: {low_primitive}
High-activity node: {high_primitive}

Generate 3-5 Primarch suggestions for new ideas, chains, or evolutions that could emerge from this collision.
Make them open-ended, remixable, and mythic in nature.

Output format:
1. [Suggestion 1]
2. [Suggestion 2]
3. [Suggestion 3]
..."""
        
        suggestions_text = self._llm_call(
            prompt=primarch_prompt,
            temperature=0.95,  # High creativity for Primarch suggestions
            rag_k=30,
            max_tokens=500
        )
        
        # Parse suggestions
        suggestions = []
        for line in suggestions_text.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
                # Clean up numbering/bullets
                suggestion = line.lstrip("0123456789.-* ").strip()
                if suggestion:
                    suggestions.append(suggestion)
        
        # If parsing failed, split by periods or newlines
        if not suggestions:
            suggestions = [s.strip() for s in suggestions_text.split(".") if s.strip()][:5]
        
        # Determine rarity based on probability
        if probability >= 0.9:
            rarity = "mythic"
        elif probability >= 0.7:
            rarity = "legendary"
        elif probability >= 0.5:
            rarity = "epic"
        else:
            rarity = "rare"
        
        primarch = {
            "id": str(uuid.uuid4()),
            "type": "primarch_suggestion",
            "suggestions": suggestions[:5],  # Limit to 5
            "probability": probability,
            "rarity": rarity,
            "timestamp": datetime.utcnow().isoformat(),
            "provenance": f"Quantum collision: {low_node.get('id', 'unknown')} + {high_node.get('id', 'unknown')}",
            "source_nodes": [low_node.get("id"), high_node.get("id")],
            "metadata": {
                "low_node_activity": low_node.get("activity", 0),
                "high_node_activity": high_node.get("activity", 0),
                "low_node_rarity": low_node.get("rarity", "common"),
                "high_node_rarity": high_node.get("rarity", "common")
            }
        }
        
        return primarch
    
    def _get_collision_id(
        self,
        low_node: Dict[str, Any],
        high_node: Dict[str, Any]
    ) -> str:
        """Generate unique collision ID."""
        low_id = low_node.get("id", "unknown")
        high_id = high_node.get("id", "unknown")
        return f"{low_id}_{high_id}"
    
    def _scan_for_collisions(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scan list of nodes for potential collisions.
        
        Args:
            nodes: List of node dictionaries
            
        Returns:
            Dict with collision scan results
        """
        if len(nodes) < 2:
            return {"success": False, "error": "Need at least 2 nodes"}
        
        # Sort nodes by activity
        sorted_nodes = sorted(nodes, key=lambda n: n.get("activity", 0))
        
        # Find low-activity and high-activity pairs
        collisions = []
        low_threshold = sorted_nodes[len(sorted_nodes) // 3].get("activity", 0)  # Bottom third
        high_threshold = sorted_nodes[2 * len(sorted_nodes) // 3].get("activity", 0)  # Top third
        
        low_nodes = [n for n in sorted_nodes if n.get("activity", 0) <= low_threshold]
        high_nodes = [n for n in sorted_nodes if n.get("activity", 0) >= high_threshold]
        
        # Check collisions
        for low_node in low_nodes[:5]:  # Limit to first 5 low nodes
            for high_node in high_nodes[:5]:  # Limit to first 5 high nodes
                collision_id = self._get_collision_id(low_node, high_node)
                if collision_id not in self.processed_collisions:
                    result = self._run({
                        "low_node": low_node,
                        "high_node": high_node
                    })
                    if result.get("event") == "spawn":
                        collisions.append(result)
        
        return {
            "success": True,
            "collisions_found": len(collisions),
            "collisions": collisions
        }
    
    def monitor_mem0_graph(self) -> Dict[str, Any]:
        """
        Monitor Mem0 graph for node collisions.
        
        Returns:
            Collision scan results
        """
        try:
            from src.app.utils.mem0_memory import get_mem0_memory
            mem0 = get_mem0_memory()
            
            if not mem0.memory:
                return {"success": False, "error": "Mem0 not available"}
            
            # Search for memories (nodes in graph)
            # Note: This is a simplified approach - in production, you'd query the graph structure
            memories = mem0.search_memories("", limit=50)
            
            # Convert memories to nodes with activity scores
            nodes = []
            for mem in memories:
                metadata = mem.get("metadata", {})
                nodes.append({
                    "id": mem.get("id", str(uuid.uuid4())),
                    "content": mem.get("text", ""),
                    "activity": metadata.get("resonance_score", 0.0) or metadata.get("combo_score", 0.0) / 100.0,
                    "rarity": metadata.get("rarity", "common"),
                    "timestamp": metadata.get("timestamp", datetime.utcnow().isoformat())
                })
            
            if len(nodes) >= 2:
                return self._scan_for_collisions(nodes)
            else:
                return {"success": False, "error": "Not enough nodes in graph"}
                
        except ImportError:
            return {"success": False, "error": "Mem0 not available"}
        except Exception as e:
            logger.error(f"Error monitoring Mem0 graph: {e}")
            return {"success": False, "error": str(e)}

