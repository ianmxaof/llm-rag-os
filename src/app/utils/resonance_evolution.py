"""
Resonance Evolution System
---------------------------
Tracks user feedback and prepares datasets for model evolution via DPO training.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import streamlit as st

from .vault_config import (
    RESONANCE_PAIRS_DIR, CONVERSATIONS_DIR, DPO_DATASETS_DIR,
    ensure_vault_structure
)
from .memory_store import load_conversation_by_id

logger = logging.getLogger(__name__)

# Ensure directories exist
ensure_vault_structure()

RESONANCE_LOG_PATH = RESONANCE_PAIRS_DIR / "log.jsonl"
EVOLUTION_THRESHOLD = 50  # Number of resonance events before triggering evolution


class ResonanceEvolution:
    """Automatically evolve models based on resonance feedback."""
    
    def __init__(self, vault_path: Optional[str] = None):
        """
        Initialize resonance evolution tracker.
        
        Args:
            vault_path: Optional override for vault path (uses config default if None)
        """
        self.resonance_log = RESONANCE_LOG_PATH
        self.conversations_dir = CONVERSATIONS_DIR
        self.dpo_datasets_dir = DPO_DATASETS_DIR
        
        # Ensure log file exists
        self.resonance_log.parent.mkdir(parents=True, exist_ok=True)
        if not self.resonance_log.exists():
            self.resonance_log.touch()
    
    def log_resonance_event(
        self,
        conversation_id: str,
        user_response: Optional[str] = None,
        chain_used: Optional[str] = None,
        chain_context: Optional[Dict] = None,
        combo_score: Optional[float] = None,
        force: bool = False
    ) -> bool:
        """
        Log when user types 'resonance' or upvotes a response.
        Can be triggered by button click (force=True) or text detection.
        
        Args:
            conversation_id: ID of the conversation
            user_response: User's response (checked for "resonance" keyword) or None if button click
            chain_used: Optional prompt chain that was used
            chain_context: Optional full chain execution context (steps, outputs, etc.)
            combo_score: Optional combo meter score at time of resonance
            force: If True, log resonance regardless of text detection (button click)
            
        Returns:
            True if resonance was detected and logged
        """
        # Check for resonance keyword or button click
        resonance_detected = force
        if not resonance_detected and user_response:
            resonance_detected = (
                "resonance" in user_response.lower() or
                user_response.strip().startswith("👍") or
                user_response.strip().startswith("+1") or
                user_response.strip().lower() == "upvote"
            )
        
        if not resonance_detected:
            return False
        
        try:
            # Get conversation history
            conversation = load_conversation_by_id(conversation_id)
            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found for resonance logging")
                return False
            
            # Extract DPO pairs from conversation with enhanced chain context
            pairs = self.extract_dpo_pairs(
                conversation, 
                chain_used, 
                chain_context=chain_context,
                combo_score=combo_score
            )
            
            # Append to dataset
            with open(self.resonance_log, 'a', encoding='utf-8') as f:
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + '\n')
            
            logger.info(f"Logged {len(pairs)} resonance pairs from conversation {conversation_id}")
            
            # Also save to Mem0 if available
            try:
                from src.app.utils.mem0_memory import get_mem0_memory
                mem0 = get_mem0_memory()
                if mem0.memory:
                    mem0.add_resonance_event(
                        response=user_response or "Button click resonance",
                        combo_score=combo_score,
                        chain_name=chain_used
                    )
            except:
                pass
            
            # Publish to event bus
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
                from shared.agents.event_bus import get_event_bus, EVENT_RESONANCE
                
                event_bus = get_event_bus()
                event_bus.publish_sync(
                    EVENT_RESONANCE,
                    {
                        "conversation_id": conversation_id,
                        "chain_used": chain_used,
                        "chain_context": chain_context,
                        "combo_score": combo_score,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                logger.debug(f"Event bus not available: {e}")
            
            # Check if we hit evolution threshold
            trigger_count = self.check_evolution_trigger()
            if trigger_count:
                # Signal that evolution should be triggered
                self._trigger_evolution_signal(trigger_count)
            
            return True
            
        except Exception as e:
            logger.error(f"Error logging resonance event: {e}")
            return False
    
    def extract_dpo_pairs(
        self,
        conversation: List[Dict],
        chain_used: Optional[str] = None,
        chain_context: Optional[Dict] = None,
        combo_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert conversation to DPO training pairs with enhanced chain context.
        
        Args:
            conversation: List of message dictionaries
            chain_used: Optional prompt chain identifier
            chain_context: Optional full chain execution context (steps, outputs, connections)
            combo_score: Optional combo meter score
            
        Returns:
            List of DPO pair dictionaries
        """
        pairs = []
        
        # Build full chain context string if available
        chain_context_str = ""
        if chain_context:
            steps = chain_context.get('steps', [])
            if steps:
                chain_context_str = "\n\n=== Chain Execution Context ===\n"
                for i, step in enumerate(steps):
                    chain_context_str += f"\nStep {i+1}: {step.get('description', 'Unknown')}\n"
                    chain_context_str += f"Input: {step.get('input', '')[:200]}...\n" if step.get('input') else ""
                    chain_context_str += f"Output: {step.get('output', '')[:500]}...\n" if step.get('output') else ""
                chain_context_str += "\n"
        
        # Find user-assistant pairs where assistant response was good
        for i in range(len(conversation) - 1):
            if conversation[i].get('role') == 'user' or 'question' in conversation[i]:
                prompt = conversation[i].get('content') or conversation[i].get('question', '')
                
                # Enhance prompt with chain context if available
                if chain_context_str:
                    prompt = prompt + chain_context_str
                
                # Find the next assistant response
                if i + 1 < len(conversation):
                    chosen = conversation[i + 1].get('content') or conversation[i + 1].get('answer', '')
                    
                    if prompt and chosen:
                        # Generate a "rejected" response (placeholder - in practice, use previous attempts or weaker model)
                        rejected = "I cannot help with that request."  # Placeholder
                        
                        pair = {
                            "prompt": prompt,
                            "chosen": chosen,
                            "rejected": rejected,
                            "timestamp": datetime.now().isoformat(),
                            "conversation_id": conversation[i].get('conversation_id', 'unknown'),
                            "model_used": st.session_state.get('selected_model', 'unknown'),
                            "chain_used": chain_used,
                            "combo_score": combo_score,
                            "metadata": {
                                "max_relevance": conversation[i + 1].get('max_relevance', 0.0),
                                "mode": conversation[i + 1].get('mode', 'unknown'),
                                "chain_steps": len(chain_context.get('steps', [])) if chain_context else 0,
                                "chain_connections": len(chain_context.get('connections', [])) if chain_context else 0
                            }
                        }
                        pairs.append(pair)
        
        return pairs
    
    def check_evolution_trigger(self) -> Optional[int]:
        """
        Check if evolution threshold has been reached.
        
        Returns:
            Number of resonance events if threshold reached, None otherwise
        """
        try:
            # Count total resonance events
            count = sum(1 for _ in open(self.resonance_log, 'r', encoding='utf-8') if _.strip())
            
            if count > 0 and count % EVOLUTION_THRESHOLD == 0:
                logger.info(f"Evolution trigger: {count} resonance events collected")
                return count
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking evolution trigger: {e}")
            return None
    
    def _trigger_evolution_signal(self, count: int):
        """
        Signal that evolution threshold has been reached.
        This will be picked up by the DPO worker.
        
        Args:
            count: Number of resonance events
        """
        # Create a signal file that the DPO worker can monitor
        signal_file = self.dpo_datasets_dir / "evolution_trigger.json"
        signal_data = {
            "triggered": True,
            "resonance_count": count,
            "timestamp": datetime.now().isoformat(),
            "processed": False
        }
        signal_file.write_text(json.dumps(signal_data, indent=2), encoding='utf-8')
        logger.info(f"Evolution signal created: {count} resonance events")
        
        # Also extract high-resonance memories from Mem0 for DPO training
        try:
            from src.app.utils.mem0_memory import get_mem0_memory
            mem0 = get_mem0_memory()
            
            if mem0.memory:
                # Search for high-resonance memories
                high_resonance_memories = mem0.search_memories(
                    "",
                    limit=50,
                    filters={"resonance_score": 1.0}
                )
                
                if high_resonance_memories:
                    # Extract as DPO pairs
                    mem0_pairs = []
                    for mem in high_resonance_memories:
                        text = mem.get('text', '')
                        metadata = mem.get('metadata', {})
                        
                        # Create DPO pair from memory
                        pair = {
                            "prompt": f"Extract resonance from: {text[:200]}...",
                            "chosen": text,
                            "rejected": "No resonance detected.",
                            "timestamp": datetime.now().isoformat(),
                            "conversation_id": "mem0_memory",
                            "model_used": "mem0_extracted",
                            "chain_used": metadata.get('chain_name'),
                            "combo_score": metadata.get('combo_score', 0.0),
                            "metadata": {
                                "source": "mem0",
                                "resonance_score": metadata.get('resonance_score', 1.0)
                            }
                        }
                        mem0_pairs.append(pair)
                    
                    # Append to resonance log
                    if mem0_pairs:
                        with open(self.resonance_log, 'a', encoding='utf-8') as f:
                            for pair in mem0_pairs:
                                f.write(json.dumps(pair, ensure_ascii=False) + '\n')
                        
                        logger.info(f"Extracted {len(mem0_pairs)} DPO pairs from Mem0 memories")
        except ImportError:
            # Mem0 not available
            pass
        except Exception as e:
            logger.debug(f"Mem0 DPO extraction failed: {e}")
    
    def get_resonance_count(self) -> int:
        """Get total number of resonance events logged."""
        try:
            return sum(1 for _ in open(self.resonance_log, 'r', encoding='utf-8') if _.strip())
        except Exception:
            return 0
    
    def get_resonance_dataset_path(self) -> Path:
        """Get path to the resonance dataset file."""
        return self.resonance_log
    
    def export_dpo_dataset(self, output_path: Optional[Path] = None) -> Path:
        """
        Export resonance pairs as a DPO-ready dataset.
        
        Args:
            output_path: Optional output path (defaults to dpo_datasets directory)
            
        Returns:
            Path to exported dataset file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.dpo_datasets_dir / f"dpo_dataset_{timestamp}.jsonl"
        
        # Read all pairs from log
        pairs = []
        try:
            with open(self.resonance_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        pairs.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading resonance log: {e}")
            return output_path
        
        # Write to output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + '\n')
        
        logger.info(f"Exported {len(pairs)} DPO pairs to {output_path}")
        return output_path


# Global instance
_resonance_evolution_instance: Optional[ResonanceEvolution] = None


def get_resonance_evolution() -> ResonanceEvolution:
    """Get or create the global resonance evolution instance."""
    global _resonance_evolution_instance
    if _resonance_evolution_instance is None:
        _resonance_evolution_instance = ResonanceEvolution()
    return _resonance_evolution_instance

