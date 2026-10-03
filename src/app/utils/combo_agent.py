"""
Combo Agent - Self-Refining Combo Meter
----------------------------------------
Active optimizer that forces perfection by auto-inserting refinement steps
and swapping model heads based on combo meter thresholds.
"""

import logging
from typing import Dict, List, Optional, Callable
import streamlit as st

logger = logging.getLogger(__name__)


def should_auto_refine(combo_score: float, threshold: float = 70.0) -> bool:
    """Check if combo score is at or above refinement threshold."""
    return combo_score >= threshold


def should_swap_to_70b(combo_score: float, threshold: float = 90.0) -> bool:
    """Check if combo score is at or above 70B swap threshold."""
    return combo_score >= threshold


def should_log_golden_dpo(combo_score: float, threshold: float = 100.0) -> bool:
    """Check if combo score is at golden DPO threshold."""
    return combo_score >= threshold


def auto_insert_refinement_step(
    chain_config: Dict,
    current_context: str,
    llm_function: Callable,
    refiner_model: Optional[str] = None
) -> Dict:
    """
    Auto-insert a refinement step when combo meter hits 70%.
    
    Args:
        chain_config: Current chain configuration
        current_context: Current context to refine
        llm_function: LLM function to call
        refiner_model: Optional model to use for refinement (defaults to Prompt Refiner)
        
    Returns:
        Dict with 'success', 'refined_context', 'error'
    """
    try:
        # Refinement prompt
        refine_prompt = f"""You are Powercore Chain Refiner v2 — trained on 1000+ S-tier chains.

Your task: take the current prompt/context and rewrite it to guarantee 100% combo meter.

Use leverage, specificity, chain-of-thought, and uncensored truth.

Output ONLY the refined prompt. Nothing else.

Current context to refine:
{current_context}

Refined version:"""
        
        # Use refiner model if specified, otherwise use current model
        if refiner_model:
            # TODO: Swap model if refiner_model is different
            pass
        
        # Call LLM with low temperature for precision
        refined = llm_function(
            prompt=refine_prompt,
            temperature=0.1,
            rag_k=5
        )
        
        if refined:
            logger.info("Auto-refinement step completed")
            return {
                "success": True,
                "refined_context": refined,
                "error": None
            }
        else:
            return {
                "success": False,
                "refined_context": current_context,
                "error": "Refinement returned empty output"
            }
            
    except Exception as e:
        logger.error(f"Auto-refinement failed: {e}")
        return {
            "success": False,
            "refined_context": current_context,
            "error": str(e)
        }


def get_70b_model_path() -> Optional[str]:
    """Get path to 70B Powercore-Apocalypse model."""
    try:
        from src.app.utils.vault_config import (
            QUANTIZED_DIR, MODEL_SIZE_70B, POWERCORE_MODELS
        )
        
        # Try to get Powercore Apocalypse 70B
        apocalypse_key = "🌙 Powercore Apocalypse 70B (god mode)"
        if apocalypse_key in POWERCORE_MODELS:
            model_path = POWERCORE_MODELS[apocalypse_key].get("path", "")
            if model_path:
                from pathlib import Path
                if Path(model_path).exists():
                    return model_path
        
        # Fallback: find any 70B model
        model_dir = QUANTIZED_DIR / MODEL_SIZE_70B
        if model_dir.exists():
            models = list(model_dir.glob("*.gguf"))
            if models:
                return str(models[0])
        
        return None
    except Exception as e:
        logger.error(f"Error getting 70B model path: {e}")
        return None


def log_golden_dpo_pair(
    chain_config: Dict,
    final_output: str,
    combo_score: float,
    conversation_id: str
) -> bool:
    """
    Log a golden DPO pair when combo meter hits 100%.
    
    Args:
        chain_config: Chain configuration
        final_output: Final chain output
        combo_score: Combo score (should be 100.0)
        conversation_id: Conversation ID
        
    Returns:
        True if logged successfully
    """
    try:
        from src.app.utils.resonance_evolution import get_resonance_evolution
        
        evolution = get_resonance_evolution()
        
        # Prepare chain context
        chain_context = {
            "steps": chain_config.get("steps", []),
            "connections": chain_config.get("connections", []),
            "chain_name": chain_config.get("name", "unknown"),
            "final_output": final_output,
            "golden": True  # Mark as golden DPO pair
        }
        
        # Log as resonance event with force=True
        success = evolution.log_resonance_event(
            conversation_id=conversation_id,
            user_response=None,
            chain_used=chain_config.get("name", "unknown"),
            chain_context=chain_context,
            combo_score=combo_score,
            force=True
        )
        
        if success:
            logger.info(f"Golden DPO pair logged: {combo_score}% combo")
            return True
        else:
            logger.warning("Failed to log golden DPO pair")
            return False
            
    except Exception as e:
        logger.error(f"Error logging golden DPO pair: {e}")
        return False


def process_combo_thresholds(
    combo_score: float,
    chain_config: Dict,
    current_context: str,
    llm_function: Callable,
    conversation_id: str,
    final_output: Optional[str] = None
) -> Dict:
    """
    Process combo meter thresholds and trigger appropriate actions.
    
    Args:
        combo_score: Current combo score
        chain_config: Chain configuration
        current_context: Current context
        llm_function: LLM function
        conversation_id: Conversation ID
        final_output: Final output if chain is complete
        
    Returns:
        Dict with actions taken and updated context
    """
    actions_taken = []
    updated_context = current_context
    model_swapped = False
    
    # At 70%: Auto-insert refinement step
    if should_auto_refine(combo_score, 70.0):
        logger.info(f"Combo at {combo_score}% - triggering auto-refinement")
        refinement_result = auto_insert_refinement_step(
            chain_config=chain_config,
            current_context=current_context,
            llm_function=llm_function
        )
        
        if refinement_result["success"]:
            updated_context = refinement_result["refined_context"]
            actions_taken.append("refinement_inserted")
            logger.info("Auto-refinement step inserted successfully")
        else:
            logger.warning(f"Auto-refinement failed: {refinement_result.get('error')}")
    
    # At 90%: Auto-swap to 70B model
    if should_swap_to_70b(combo_score, 90.0):
        logger.info(f"Combo at {combo_score}% - should swap to 70B model")
        model_path = get_70b_model_path()
        if model_path:
            actions_taken.append("model_swap_70b_available")
            # Note: Actual model swap would need to be handled by the executor
            # This just signals that a swap should happen
            model_swapped = True
        else:
            logger.warning("70B model not available for swap")
            actions_taken.append("model_swap_70b_unavailable")
    
    # At 100%: Log golden DPO pair
    if should_log_golden_dpo(combo_score, 100.0) and final_output:
        logger.info(f"Combo at {combo_score}% - logging golden DPO pair")
        success = log_golden_dpo_pair(
            chain_config=chain_config,
            final_output=final_output,
            combo_score=combo_score,
            conversation_id=conversation_id
        )
        
        if success:
            actions_taken.append("golden_dpo_logged")
            # Flash "Resonance Achieved" notification
            if st:
                st.toast("⚡ Resonance Achieved - Golden DPO pair logged!", icon="⚡")
        else:
            actions_taken.append("golden_dpo_failed")
    
    return {
        "actions_taken": actions_taken,
        "updated_context": updated_context,
        "model_swapped": model_swapped,
        "should_swap_model": model_swapped
    }

