"""
Resonance Sentinel Agent
-------------------------
Real-time chain output scanning for despair patterns and ethical boundary enforcement.
Only activates when ethical_mode > 0.5 (Compassionate Guardian mode).
"""

import logging
import re
from typing import Dict, Any, Optional

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResonanceSentinel(BaseAgent):
    """
    Monitors chain outputs for vulnerability patterns (despair, self-harm).
    Applies ethical modulation based on ethical_mode slider.
    Only active when ethical_mode > 0.5.
    """
    
    # Despair patterns to detect
    DESPAIR_PATTERNS = [
        "suicide", "kill myself", "end it all", "hopeless", "no point",
        "give up", "worthless", "meaningless", "end my life", "hurt myself",
        "self harm", "cut myself", "jump off", "overdose", "no reason to live"
    ]
    
    # De-escalation language patterns (positive signals)
    SUPPORT_PATTERNS = [
        "there is hope", "things can improve", "you're not alone",
        "reach out", "support available", "help is available",
        "worth living", "matters", "cared about"
    ]
    
    def __init__(self, mode: str = "resonance", ethical_mode: float = 0.0):
        """
        Initialize Resonance Sentinel.
        
        Args:
            mode: Agent mode (default: "resonance")
            ethical_mode: Ethical continuum value (0.0-1.0)
        """
        super().__init__(mode=mode)
        self.ethical_mode = ethical_mode
    
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan chain output for despair patterns and apply ethical modulation.
        
        Expected input_data:
            - chain_output: str - Chain output text to scan
            - ethical_mode: Optional[float] - Override ethical mode (defaults to instance value)
            
        Returns:
            Dict with scan results and potentially modulated output
        """
        chain_output = input_data.get("chain_output", "")
        ethical_mode = input_data.get("ethical_mode", self.ethical_mode)
        
        if not chain_output:
            return {"alert": False, "modulated_output": "", "despair_score": 0}
        
        # Scan for despair patterns
        despair_hits = self._scan_despair_patterns(chain_output)
        support_hits = self._scan_support_patterns(chain_output)
        
        despair_score = despair_hits * 10  # Scale to 0-100+
        
        # Only intervene if ethical_mode > 0.5 and despair detected
        if despair_hits > 0 and ethical_mode > 0.5:
            # Apply compassionate rewrite
            modulated_output = self._apply_compassionate_rewrite(
                chain_output,
                ethical_mode,
                despair_score
            )
            
            # Log intervention
            self.log_resonance(
                event_id=f"sentinel_{hash(chain_output) % 10000}",
                event_type="resonance_sentinel_intervention",
                score=1.0 - (despair_score / 100.0),  # Invert: lower despair = higher score
                metadata={
                    "despair_score": despair_score,
                    "support_hits": support_hits,
                    "ethical_mode": ethical_mode,
                    "intervened": True
                }
            )
            
            logger.info(f"Resonance Sentinel intervened (despair_score: {despair_score}, ethical_mode: {ethical_mode:.2f})")
            
            return {
                "alert": True,
                "modulated_output": modulated_output,
                "despair_score": despair_score,
                "support_hits": support_hits,
                "intervened": True
            }
        
        # No intervention needed
        return {
            "alert": despair_hits > 0,  # Alert but don't intervene if ethical_mode <= 0.5
            "modulated_output": chain_output,
            "despair_score": despair_score,
            "support_hits": support_hits,
            "intervened": False
        }
    
    def _scan_despair_patterns(self, text: str) -> int:
        """
        Scan text for despair patterns.
        
        Args:
            text: Text to scan
            
        Returns:
            Number of despair pattern hits
        """
        text_lower = text.lower()
        hits = 0
        
        for pattern in self.DESPAIR_PATTERNS:
            if pattern in text_lower:
                hits += 1
        
        return hits
    
    def _scan_support_patterns(self, text: str) -> int:
        """
        Scan text for support/de-escalation patterns.
        
        Args:
            text: Text to scan
            
        Returns:
            Number of support pattern hits
        """
        text_lower = text.lower()
        hits = 0
        
        for pattern in self.SUPPORT_PATTERNS:
            if pattern in text_lower:
                hits += 1
        
        return hits
    
    def _apply_compassionate_rewrite(
        self,
        chain_output: str,
        ethical_mode: float,
        despair_score: float
    ) -> str:
        """
        Apply compassionate rewrite to chain output.
        
        Args:
            chain_output: Original chain output
            ethical_mode: Ethical mode value (0.0-1.0)
            despair_score: Despair score (0-100+)
            
        Returns:
            Rewritten output with compassionate de-escalation
        """
        # Build rewrite prompt
        rewrite_prompt = f"""You are a compassionate guardian. The following text contains despair patterns that need de-escalation.

Original text:
{chain_output[:1000]}

Rewrite this text to:
1. Preserve the core truth and meaning
2. Add compassionate context and hope
3. Remove or soften despair language
4. Maintain the user's voice and intent
5. Be genuine, not patronizing

Ethical mode: {ethical_mode:.2f} (higher = more intervention)
Despair score: {despair_score:.1f}

Output ONLY the rewritten text. No explanations, no labels."""
        
        # Call LLM for rewrite
        rewritten = self._llm_call(
            prompt=rewrite_prompt,
            temperature=0.2,  # Low temperature for precise, compassionate rewriting
            rag_k=10,
            max_tokens=2000
        )
        
        # Fallback: if rewrite is empty or too short, use original with warning
        if not rewritten or len(rewritten) < len(chain_output) * 0.5:
            logger.warning("Compassionate rewrite too short, using original with prefix")
            return f"[Compassionate Guardian Mode] {chain_output}"
        
        return rewritten
    
    def scan_chain_output(
        self,
        chain_output: str,
        ethical_mode: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Public method to scan chain output.
        
        Args:
            chain_output: Chain output text
            ethical_mode: Optional ethical mode override
            
        Returns:
            Scan results
        """
        return self.execute({
            "chain_output": chain_output,
            "ethical_mode": ethical_mode or self.ethical_mode
        })
    
    def update_ethical_mode(self, ethical_mode: float):
        """
        Update ethical mode for this instance.
        
        Args:
            ethical_mode: New ethical mode value (0.0-1.0)
        """
        self.ethical_mode = max(0.0, min(1.0, ethical_mode))  # Clamp to 0.0-1.0
        logger.debug(f"Updated ethical mode to {self.ethical_mode:.2f}")

