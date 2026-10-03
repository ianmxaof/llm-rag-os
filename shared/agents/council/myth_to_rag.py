"""
Myth → RAG Injector Agent
--------------------------
Monitors Entropy.env for new myth fragments and injects them into Powercore RAG system.
Converts myth fragments to RAG context and updates combo meter baselines.
"""

import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base_agent import BaseAgent
from ..event_bus import get_event_bus, EVENT_MYTH_FRAGMENT, EVENT_CHAIN_EXECUTION

logger = logging.getLogger(__name__)


class MythToRagAgent(BaseAgent):
    """
    Monitors Entropy.env for new myth fragments and injects them into Powercore RAG.
    Automatically makes myth fragments available as RAG context in future queries.
    """
    
    def __init__(self, mode: str = "resonance"):
        """
        Initialize Myth → RAG Injector agent.
        
        Args:
            mode: Agent mode (default: "resonance")
        """
        super().__init__(mode=mode)
        self.processed_myths: set = set()  # Track processed myth IDs
    
    def _run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject myth fragment into RAG system.
        
        Expected input_data:
            - myth_fragment: Dict - Myth fragment from Entropy.env
            OR
            - myth_id: str - ID of myth fragment to fetch
            
        Returns:
            Dict with injection result
        """
        myth_fragment = input_data.get("myth_fragment")
        
        # If myth_id provided, fetch from Entropy.env (placeholder for now)
        if not myth_fragment and input_data.get("myth_id"):
            myth_fragment = self._fetch_myth_fragment(input_data["myth_id"])
        
        if not myth_fragment:
            return {"success": False, "error": "No myth fragment provided"}
        
        myth_id = myth_fragment.get("id")
        if myth_id in self.processed_myths:
            logger.debug(f"Myth fragment {myth_id} already processed")
            return {"success": True, "already_processed": True}
        
        # Convert myth fragment to RAG document
        rag_document = self._convert_to_rag_document(myth_fragment)
        
        # Inject into RAG system
        injection_result = self._inject_into_rag(rag_document)
        
        if injection_result.get("success"):
            self.processed_myths.add(myth_id)
            logger.info(f"Injected myth fragment {myth_id} into RAG")
        
        return injection_result
    
    def _convert_to_rag_document(self, myth_fragment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert myth fragment to RAG document format.
        
        Args:
            myth_fragment: Myth fragment dictionary
            
        Returns:
            RAG document dictionary
        """
        essence = myth_fragment.get("essence", "")
        content = myth_fragment.get("content", "")
        rarity = myth_fragment.get("rarity", "common")
        provenance = myth_fragment.get("provenance", "")
        
        # Build RAG document text
        rag_text = f"""MYTHIC FRAGMENT ({rarity.upper()})

{essence}

Source: {provenance}
Rarity: {rarity}
Resonance Score: {myth_fragment.get('resonance_score', 0.0):.2f}

Full Content:
{content[:1000]}  # Limit content length
"""
        
        return {
            "text": rag_text,
            "metadata": {
                "type": "myth_fragment",
                "myth_id": myth_fragment.get("id"),
                "rarity": rarity,
                "resonance_score": myth_fragment.get("resonance_score", 0.0),
                "provenance": provenance,
                "timestamp": myth_fragment.get("timestamp", datetime.utcnow().isoformat()),
                "tags": myth_fragment.get("tags", [])
            }
        }
    
    def _inject_into_rag(self, rag_document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject RAG document into Powercore's RAG system.
        
        Args:
            rag_document: RAG document dictionary
            
        Returns:
            Injection result
        """
        try:
            # Inject into ChromaDB via backend API or direct access
            import hashlib
            import chromadb
            from pathlib import Path
            
            text = rag_document["text"]
            metadata = rag_document["metadata"]
            
            # Get ChromaDB path from config
            try:
                from src import config
                chroma_path = getattr(config, 'CHROMA_PATH', './chroma')
            except:
                chroma_path = './chroma'
            
            # Connect to ChromaDB
            chroma_client = chromadb.PersistentClient(path=str(chroma_path))
            
            # Use existing collection or create myth_fragments collection
            try:
                collection = chroma_client.get_or_create_collection(
                    name="myth_fragments",
                    metadata={"description": "Myth fragments from Entropy.env"}
                )
            except:
                # Fallback to main collection
                collection = chroma_client.get_or_create_collection(name="llm_docs")
            
            # Chunk text if needed (simple chunking for now)
            chunk_size = 1000
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            
            # Add chunks to collection
            ids = []
            documents = []
            metadatas = []
            
            for idx, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{metadata.get('myth_id', 'unknown')}-{idx}".encode()).hexdigest()
                ids.append(chunk_id)
                documents.append(chunk)
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk"] = idx
                metadatas.append(chunk_metadata)
            
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            
            # Also update combo meter baseline if high rarity
            if metadata.get("rarity") in ["epic", "legendary", "mythic"]:
                self._update_combo_baseline(metadata.get("resonance_score", 0.0))
            
            # Publish chain execution event
            event_bus = get_event_bus()
            event_bus.publish_sync(
                EVENT_CHAIN_EXECUTION,
                {
                    "type": "myth_injection",
                    "myth_id": metadata.get("myth_id"),
                    "rarity": metadata.get("rarity"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return {
                "success": True,
                "myth_id": metadata.get("myth_id"),
                "rarity": metadata.get("rarity")
            }
            
        except ImportError:
            logger.error("Failed to import RAG utilities")
            return {"success": False, "error": "RAG system not available"}
        except Exception as e:
            logger.error(f"Error injecting into RAG: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_combo_baseline(self, resonance_score: float):
        """
        Update combo meter baseline based on high-rarity myth fragments.
        
        Args:
            resonance_score: Resonance score from myth fragment (0.0-1.0)
        """
        try:
            import streamlit as st
            
            # Update personal best if myth fragment has high resonance
            if resonance_score > 0.9:
                current_best = st.session_state.get("personal_best_combo", 0.0)
                new_baseline = resonance_score * 100.0  # Convert to combo scale
                if new_baseline > current_best:
                    st.session_state.personal_best_combo = new_baseline
                    logger.info(f"Updated combo baseline to {new_baseline:.1f} from myth fragment")
                    
        except Exception as e:
            logger.debug(f"Could not update combo baseline: {e}")
    
    def _fetch_myth_fragment(self, myth_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch myth fragment from Entropy.env (placeholder).
        
        Args:
            myth_id: Myth fragment ID
            
        Returns:
            Myth fragment dictionary or None
        """
        # TODO: Implement Entropy.env API call to fetch myth fragment
        # For now, return None (will be implemented when Entropy.env is integrated)
        logger.debug(f"Fetching myth fragment {myth_id} from Entropy.env (not yet implemented)")
        return None
    
    def monitor_myth_fragments(self) -> List[Dict[str, Any]]:
        """
        Monitor event bus for new myth fragments and auto-inject them.
        
        Returns:
            List of injection results
        """
        event_bus = get_event_bus()
        recent_events = event_bus.get_events_by_type(EVENT_MYTH_FRAGMENT, limit=10)
        
        results = []
        for event in recent_events:
            myth_fragment = event.get("data", {})
            myth_id = myth_fragment.get("id")
            
            if myth_id and myth_id not in self.processed_myths:
                result = self.execute({"myth_fragment": myth_fragment})
                results.append(result)
        
        return results

