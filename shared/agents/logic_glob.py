"""
Logic Glob Checkpoint System
----------------------------
Git-like checkpoint system for agent actions with hash-chained snapshots,
caching for efficiency, and rollback capability.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Ensure checkpoints directory exists
CHECKPOINTS_DIR = Path("checkpoints")
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


class LogicGlob:
    """
    Checkpoint system for agent actions with hash-chained snapshots.
    Provides efficiency through caching and security through hash verification.
    """
    
    def __init__(self, task_id: str):
        """
        Initialize Logic Glob for a task.
        
        Args:
            task_id: Unique identifier for this task/chain
        """
        self.task_id = task_id
        self.checkpoints: List[Dict[str, Any]] = []
        self.cache: Dict[str, Any] = {}  # input_hash -> output
        self.checkpoint_file = CHECKPOINTS_DIR / f"{task_id}.jsonl"
        
        # Load existing checkpoints if file exists
        self._load_checkpoints()
    
    def _load_checkpoints(self):
        """Load existing checkpoints from file."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            checkpoint = json.loads(line)
                            self.checkpoints.append(checkpoint)
                            # Rebuild cache
                            if "input_hash" in checkpoint and "output_data" in checkpoint:
                                self.cache[checkpoint["input_hash"]] = checkpoint["output_data"]
            except Exception as e:
                logger.warning(f"Error loading checkpoints: {e}")
    
    def snapshot(
        self,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a checkpoint snapshot.
        
        Args:
            agent_name: Name of the agent performing the action
            input_data: Input data for this step
            output_data: Output data from this step
            metadata: Optional metadata (rarity, combo_score, chain_id, etc.)
            
        Returns:
            Checkpoint dictionary
        """
        # Calculate hashes
        input_hash = self._hash_data(input_data)
        output_hash = self._hash_data(output_data)
        
        # Check cache for efficiency
        if input_hash in self.cache:
            logger.debug(f"Cache hit for {agent_name} with input_hash {input_hash[:8]}...")
            cached_output = self.cache[input_hash]
            # Still create checkpoint for provenance
            output_data = cached_output
            output_hash = self._hash_data(output_data)
        
        # Build checkpoint
        checkpoint = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_id": self.task_id,
            "agent": agent_name,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "metadata": metadata or {},
        }
        
        # Hash chain: link to previous checkpoint
        if len(self.checkpoints) > 0:
            prev_checkpoint = self.checkpoints[-1]
            prev_hash = self._hash_data(prev_checkpoint)
            checkpoint["prev_hash"] = prev_hash
        else:
            checkpoint["prev_hash"] = None
        
        # Store checkpoint
        self.checkpoints.append(checkpoint)
        
        # Cache output
        self.cache[input_hash] = output_data
        
        # Atomic write to JSONL file
        try:
            with open(self.checkpoint_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(checkpoint, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Error writing checkpoint: {e}")
        
        return checkpoint
    
    def _hash_data(self, data: Any) -> str:
        """Calculate hash of data."""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()
    
    def verify_chain(self) -> bool:
        """
        Verify hash chain integrity (detect tampering).
        
        Returns:
            True if chain is valid, False if tampering detected
        """
        for i in range(1, len(self.checkpoints)):
            current = self.checkpoints[i]
            previous = self.checkpoints[i - 1]
            
            # Calculate expected prev_hash
            expected_prev_hash = self._hash_data(previous)
            
            if current.get("prev_hash") != expected_prev_hash:
                logger.error(f"Hash chain broken at checkpoint {i}")
                return False
        
        return True
    
    def rollback_to(self, timestamp: str) -> bool:
        """
        Rollback to a specific checkpoint timestamp.
        
        Args:
            timestamp: ISO timestamp of checkpoint to rollback to
            
        Returns:
            True if rollback successful
        """
        # Find checkpoint index
        target_idx = None
        for i, checkpoint in enumerate(self.checkpoints):
            if checkpoint["timestamp"] == timestamp:
                target_idx = i
                break
        
        if target_idx is None:
            logger.error(f"Checkpoint with timestamp {timestamp} not found")
            return False
        
        # Truncate checkpoints
        self.checkpoints = self.checkpoints[:target_idx + 1]
        
        # Rebuild cache up to rollback point
        self.cache = {}
        for checkpoint in self.checkpoints:
            if "input_hash" in checkpoint and "output_data" in checkpoint:
                self.cache[checkpoint["input_hash"]] = checkpoint["output_data"]
        
        # Rewrite checkpoint file
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                for checkpoint in self.checkpoints:
                    f.write(json.dumps(checkpoint, ensure_ascii=False) + '\n')
            logger.info(f"Rolled back to checkpoint at {timestamp}")
            return True
        except Exception as e:
            logger.error(f"Error rewriting checkpoint file: {e}")
            return False
    
    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get the latest checkpoint."""
        return self.checkpoints[-1] if self.checkpoints else None
    
    def get_checkpoint_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get checkpoint by index."""
        if 0 <= index < len(self.checkpoints):
            return self.checkpoints[index]
        return None

