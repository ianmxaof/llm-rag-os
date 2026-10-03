"""
Resonance → Myth Bridge Agent
------------------------------
Automatically converts Powercore resonance events into Entropy.env myth fragments.
Triggers on resonance button clicks or high combo scores.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent
from ..event_bus import get_event_bus, EVENT_MYTH_FRAGMENT

logger = logging.getLogger(__name__)


class ResonanceToMythAgent(BaseAgent):
    """
    Converts resonance events into myth fragments for Entropy.env.
    Automatically triggered when user clicks "Resonance Achieved" or combo_score >= threshold.
    """
    
    def __init__(self, mode: str = "resonance", combo_threshold: float = 80.0):
        """
        Initialize Resonance → Myth Bridge agent.
        
        Args:
            mode: Agent mode (default: "resonance")
            combo_threshold: Minimum combo score to trigger myth creation (default: 80.0)
        """
        super().__init__(mode=mode)
        self.combo_threshold = combo_threshold
    
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert resonance event to myth fragment.
        
        Expected input_data:
            - resonance_content: str - The resonance text/content
            - combo_score: float - Combo meter score
            - chain_name: Optional[str] - Chain that produced resonance
            - chain_context: Optional[Dict] - Full chain execution context
            
        Returns:
            Dict with myth fragment data
        """
        resonance_content = input_data.get("resonance_content", "")
        combo_score = input_data.get("combo_score", 0.0)
        chain_name = input_data.get("chain_name", "unknown")
        chain_context = input_data.get("chain_context", {})
        
        if not resonance_content:
            logger.warning("No resonance content provided")
            return {"success": False, "error": "No resonance content"}
        
        # Calculate rarity based on combo score
        rarity = self._calculate_rarity(combo_score)
        
        # Extract mythic essence from resonance content
        myth_essence = self._extract_myth_essence(resonance_content, chain_context)
        
        # Create myth fragment
        myth_fragment = {
            "id": str(uuid.uuid4()),
            "type": "myth_fragment",
            "essence": myth_essence,
            "content": resonance_content,
            "resonance_score": combo_score / 100.0,  # Normalize to 0.0-1.0
            "rarity": rarity,
            "timestamp": datetime.utcnow().isoformat(),
            "provenance": f"Powercore chain: {chain_name}",
            "tags": ["resonance", "powercore", "s-tier"],
            "metadata": {
                "chain_name": chain_name,
                "combo_score": combo_score,
                "mode": self.mode
            }
        }
        
        # Log resonance
        self.log_resonance(
            event_id=myth_fragment["id"],
            event_type="resonance_to_myth",
            score=myth_fragment["resonance_score"],
            metadata={"rarity": rarity, "chain_name": chain_name}
        )
        
        # Publish myth fragment event
        event_bus = get_event_bus()
        event_bus.publish_sync(
            EVENT_MYTH_FRAGMENT,
            myth_fragment
        )
        
        logger.info(f"Created myth fragment {myth_fragment['id']} with rarity {rarity}")
        
        return {
            "success": True,
            "myth_fragment": myth_fragment
        }
    
    def _calculate_rarity(self, combo_score: float) -> str:
        """
        Calculate rarity tier based on combo score.
        
        Args:
            combo_score: Combo meter score (0.0-100.0)
            
        Returns:
            Rarity tier: "common", "uncommon", "rare", "epic", "legendary", "mythic"
        """
        if combo_score >= 98.0:
            return "mythic"
        elif combo_score >= 95.0:
            return "legendary"
        elif combo_score >= 90.0:
            return "epic"
        elif combo_score >= 85.0:
            return "rare"
        elif combo_score >= 75.0:
            return "uncommon"
        else:
            return "common"
    
    def _extract_myth_essence(
        self,
        resonance_content: str,
        chain_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Extract mythic essence from resonance content using LLM.
        
        Args:
            resonance_content: The resonance text
            chain_context: Optional chain execution context
            
        Returns:
            Extracted mythic essence (1-2 sentences)
        """
        # Build context for extraction
        context_prompt = f"""Extract the mythic essence from this resonance event.
        
Resonance Content:
{resonance_content[:500]}

Output exactly one sentence that captures the timeless, archetypal truth embedded in this moment.
Make it remixable and open-ended. No quotes, no labels, just the essence.

Mythic Essence:"""
        
        # Add chain context if available
        if chain_context:
            steps = chain_context.get("steps", [])
            if steps:
                context_prompt += "\n\nChain Context:\n"
                for i, step in enumerate(steps[:3]):  # Limit to first 3 steps
                    context_prompt += f"Step {i+1}: {step.get('description', 'Unknown')}\n"
        
        # Call LLM to extract essence
        essence = self._llm_call(
            prompt=context_prompt,
            temperature=0.8,  # Slightly creative for mythic extraction
            rag_k=10,
            max_tokens=200
        )
        
        # Clean up essence (remove quotes, labels, etc.)
        essence = essence.strip()
        if essence.startswith('"') and essence.endswith('"'):
            essence = essence[1:-1]
        if essence.startswith("Mythic Essence:"):
            essence = essence.replace("Mythic Essence:", "").strip()
        
        return essence or resonance_content[:200]  # Fallback to truncated content
    
    def trigger_from_resonance_button(
        self,
        chain_output: str,
        combo_score: float,
        chain_name: str,
        chain_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trigger myth fragment creation from resonance button click.
        
        Args:
            chain_output: Final chain output
            combo_score: Combo meter score
            chain_name: Name of the chain
            chain_context: Optional full chain context
            
        Returns:
            Result dictionary
        """
        return self.execute({
            "resonance_content": chain_output,
            "combo_score": combo_score,
            "chain_name": chain_name,
            "chain_context": chain_context
        })
    
    def trigger_from_combo_threshold(
        self,
        chain_output: str,
        combo_score: float,
        chain_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-trigger if combo score exceeds threshold.
        
        Args:
            chain_output: Final chain output
            combo_score: Combo meter score
            chain_name: Name of the chain
            
        Returns:
            Result dictionary or None if threshold not met
        """
        if combo_score >= self.combo_threshold:
            return self.execute({
                "resonance_content": chain_output,
                "combo_score": combo_score,
                "chain_name": chain_name
            })
        return None

