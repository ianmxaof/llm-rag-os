"""
Base Agent Class
----------------
Abstract base class for all agents in the shared council.
Supports both "resonance" (Powercore) and "mythos" (Entropy.env) modes.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..logic_glob import LogicGlob
from ..event_bus import get_event_bus, EVENT_RESONANCE

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents in the shared council.
    Provides LLM calls, Logic Glob integration, resonance logging, and Mem0 integration.
    """
    
    def __init__(
        self,
        mode: str = "resonance",
        model_path: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        """
        Initialize base agent.
        
        Args:
            mode: Agent mode - "resonance" (Powercore) or "mythos" (Entropy.env)
            model_path: Optional path to GGUF model or Ollama model name
            task_id: Optional task ID for Logic Glob (auto-generated if None)
        """
        self.mode = mode
        self.model_path = model_path
        self.task_id = task_id or str(uuid.uuid4())
        self.glob = LogicGlob(self.task_id)
        self.event_bus = get_event_bus()
        
        # Mode-specific settings
        if mode == "resonance":
            self.default_temperature = 0.7
            self.default_rag_k = 15
        elif mode == "mythos":
            self.default_temperature = 0.9  # Higher for mythic creativity
            self.default_rag_k = 25
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'resonance' or 'mythos'")
    
    def _llm_call(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        rag_k: Optional[int] = None,
        max_tokens: int = 2000,
        use_rag: bool = True
    ) -> str:
        """
        Make LLM call using Powercore's model system.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (defaults to mode-specific default)
            rag_k: Number of RAG chunks (defaults to mode-specific default)
            max_tokens: Maximum tokens to generate
            use_rag: Whether to use RAG context (default: True)
            
        Returns:
            Generated text response
        """
        temperature = temperature or self.default_temperature
        rag_k = rag_k or self.default_rag_k
        
        try:
            # Import Powercore's LLM call function
            from src.rag_utils import call_local_model, answer_question
            import streamlit as st
            
            # Get model from session state or use default
            model = self.model_path or st.session_state.get("selected_model", None)
            if not model:
                # Try to get from config
                from src import config
                model = config.OLLAMA_CHAT_MODEL
            
            if use_rag and rag_k > 0:
                # Use RAG-enabled call
                result = answer_question(
                    question=prompt,
                    k=rag_k,
                    raw_mode=False,
                    model=model
                )
                return result.get("response", "")
            else:
                # Direct model call without RAG
                messages = [{"role": "user", "content": prompt}]
                return call_local_model(messages, model=model)
                
        except ImportError:
            logger.error("Failed to import Powercore LLM functions")
            return ""
        except Exception as e:
            logger.error(f"Error in LLM call: {e}")
            return ""
    
    def log_resonance(
        self,
        event_id: str,
        event_type: str,
        score: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log resonance event to Mem0 and event bus.
        
        Args:
            event_id: Unique event ID
            event_type: Type of resonance event
            score: Resonance score (0.0-1.0)
            metadata: Optional metadata
        """
        try:
            # Log to Mem0 if available
            from src.app.utils.mem0_memory import get_mem0_memory
            mem0 = get_mem0_memory()
            
            if mem0.memory:
                resonance_text = f"{event_type} event: {event_id}"
                mem0.add_resonance_event(
                    response=resonance_text,
                    combo_score=score * 100.0,  # Convert to combo score scale
                    chain_name=f"{self.__class__.__name__}_{self.mode}"
                )
            
            # Publish to event bus
            self.event_bus.publish_sync(
                EVENT_RESONANCE,
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "score": score,
                    "agent": self.__class__.__name__,
                    "mode": self.mode,
                    "metadata": metadata or {}
                }
            )
            
        except ImportError:
            logger.debug("Mem0 not available for resonance logging")
        except Exception as e:
            logger.error(f"Error logging resonance: {e}")
    
    def execute(
        self,
        input_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute agent with automatic checkpointing.
        
        Args:
            input_data: Input data for agent
            metadata: Optional metadata for checkpoint
            
        Returns:
            Output data from agent
        """
        # Snapshot before execution
        self.glob.snapshot(
            agent_name=self.__class__.__name__,
            input_data=input_data,
            output_data={},
            metadata={"status": "start", **(metadata or {})}
        )
        
        try:
            # Execute agent-specific logic
            output = self._run(input_data)
            
            # Snapshot after execution
            self.glob.snapshot(
                agent_name=self.__class__.__name__,
                input_data=input_data,
                output_data=output,
                metadata={"status": "complete", **(metadata or {})}
            )
            
            return output
            
        except Exception as e:
            logger.error(f"Error in agent execution: {e}")
            # Snapshot error
            self.glob.snapshot(
                agent_name=self.__class__.__name__,
                input_data=input_data,
                output_data={"error": str(e)},
                metadata={"status": "error", **(metadata or {})}
            )
            raise
    
    @abstractmethod
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent-specific execution logic.
        Must be implemented by subclasses.
        
        Args:
            input_data: Input data
            
        Returns:
            Output data
        """
        pass
    
    def get_checkpoint_history(self) -> List[Dict[str, Any]]:
        """Get checkpoint history for this agent's task."""
        return self.glob.checkpoints
    
    def rollback(self, timestamp: str) -> bool:
        """
        Rollback to a specific checkpoint.
        
        Args:
            timestamp: ISO timestamp of checkpoint to rollback to
            
        Returns:
            True if rollback successful
        """
        return self.glob.rollback_to(timestamp)

