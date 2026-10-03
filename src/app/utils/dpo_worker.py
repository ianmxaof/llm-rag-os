"""
Background DPO Worker
---------------------
Monitors resonance log and triggers DPO fine-tuning when threshold is reached.
Runs asynchronously to generate new LoRA model versions.
"""

import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .vault_config import (
    DPO_DATASETS_DIR, RESONANCE_PAIRS_DIR, FUSIONS_FINAL_DIR,
    QUANTIZED_DIR, MODEL_SIZE_13B, ensure_vault_structure
)

logger = logging.getLogger(__name__)

# Ensure directories exist
ensure_vault_structure()

EVOLUTION_THRESHOLD = 50
EVOLUTION_SIGNAL_FILE = DPO_DATASETS_DIR / "evolution_trigger.json"
CHECK_INTERVAL = 60  # Check every 60 seconds


class DPOWorker:
    """Background worker for DPO fine-tuning."""
    
    def __init__(self):
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.last_check = 0.0
    
    def start(self):
        """Start the background worker thread."""
        if self.running:
            logger.warning("DPO worker is already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("DPO worker started")
    
    def stop(self):
        """Stop the background worker thread."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        logger.info("DPO worker stopped")
    
    def _worker_loop(self):
        """Main worker loop that checks for evolution triggers."""
        while self.running:
            try:
                self._check_evolution_trigger()
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error in DPO worker loop: {e}")
                time.sleep(CHECK_INTERVAL)
    
    def _check_evolution_trigger(self):
        """Check if evolution should be triggered."""
        if not EVOLUTION_SIGNAL_FILE.exists():
            return
        
        try:
            signal_data = json.loads(EVOLUTION_SIGNAL_FILE.read_text(encoding='utf-8'))
            
            # Check if already processed
            if signal_data.get('processed', False):
                return
            
            # Check if trigger is set
            if not signal_data.get('triggered', False):
                return
            
            count = signal_data.get('resonance_count', 0)
            logger.info(f"DPO worker detected evolution trigger: {count} resonance events")
            
            # Trigger DPO fine-tuning
            success = self._trigger_dpo_training(count)
            
            if success:
                # Mark as processed
                signal_data['processed'] = True
                signal_data['processed_at'] = datetime.now().isoformat()
                EVOLUTION_SIGNAL_FILE.write_text(
                    json.dumps(signal_data, indent=2), 
                    encoding='utf-8'
                )
                logger.info(f"DPO training triggered successfully for {count} events")
            else:
                logger.error("DPO training failed to trigger")
                
        except Exception as e:
            logger.error(f"Error checking evolution trigger: {e}")
    
    def _trigger_dpo_training(self, resonance_count: int) -> bool:
        """
        Trigger DPO fine-tuning process.
        
        Args:
            resonance_count: Number of resonance events that triggered this
            
        Returns:
            True if training was successfully queued/started
        """
        try:
            # Export DPO dataset
            dataset_path = self._export_dpo_dataset()
            if not dataset_path or not dataset_path.exists():
                logger.error("Failed to export DPO dataset")
                return False
            
            # Determine base model (use current selected model or default)
            base_model = self._get_base_model_for_training()
            if not base_model:
                logger.error("No base model available for DPO training")
                return False
            
            # Generate new version number
            version = self._get_next_version_number()
            
            # Create training job configuration
            training_config = {
                "version": version,
                "base_model": base_model,
                "dataset_path": str(dataset_path),
                "resonance_count": resonance_count,
                "created_at": datetime.now().isoformat(),
                "status": "queued"
            }
            
            # Save training config
            config_path = DPO_DATASETS_DIR / f"training_config_v{version}.json"
            config_path.write_text(
                json.dumps(training_config, indent=2),
                encoding='utf-8'
            )
            
            logger.info(f"DPO training job created: v{version} with {resonance_count} resonance events")
            
            # TODO: Actually trigger DPO training script
            # For now, we just create the config file
            # In production, this would call a DPO training script or queue a job
            
            return True
            
        except Exception as e:
            logger.error(f"Error triggering DPO training: {e}")
            return False
    
    def _export_dpo_dataset(self) -> Optional[Path]:
        """Export resonance pairs as DPO-ready dataset."""
        try:
            resonance_log = RESONANCE_PAIRS_DIR / "log.jsonl"
            if not resonance_log.exists():
                logger.warning("Resonance log does not exist")
                return None
            
            # Read all pairs
            pairs = []
            with open(resonance_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        pairs.append(json.loads(line))
            
            if not pairs:
                logger.warning("No resonance pairs to export")
                return None
            
            # Export to dataset file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = DPO_DATASETS_DIR / f"dpo_dataset_{timestamp}.jsonl"
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + '\n')
            
            logger.info(f"Exported {len(pairs)} DPO pairs to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting DPO dataset: {e}")
            return None
    
    def _get_base_model_for_training(self) -> Optional[str]:
        """Get the base model path for DPO training."""
        # Default to Powercore Ultimate 13B
        default_model = QUANTIZED_DIR / MODEL_SIZE_13B / "Powercore-Ultimate-13B-Q6_K.gguf"
        
        if default_model.exists():
            return str(default_model)
        
        # Fallback: find any 13B model
        model_dir = QUANTIZED_DIR / MODEL_SIZE_13B
        if model_dir.exists():
            models = list(model_dir.glob("*.gguf"))
            if models:
                return str(models[0])
        
        return None
    
    def _get_next_version_number(self) -> int:
        """Get the next version number for DPO model."""
        # Check existing versions in final fusions directory
        version = 1
        
        if FUSIONS_FINAL_DIR.exists():
            # Look for existing DPO versions
            pattern = "Powercore-Ultimate-13B-DPO-v*.gguf"
            existing = list(FUSIONS_FINAL_DIR.glob(pattern))
            
            if existing:
                # Extract version numbers
                versions = []
                for path in existing:
                    try:
                        # Extract version from filename like "Powercore-Ultimate-13B-DPO-v12.gguf"
                        name = path.stem
                        if "-v" in name:
                            v_str = name.split("-v")[-1]
                            versions.append(int(v_str))
                    except:
                        continue
                
                if versions:
                    version = max(versions) + 1
        
        return version
    
    def get_training_status(self) -> Dict[str, Any]:
        """Get current status of DPO training."""
        status = {
            "running": self.running,
            "last_check": self.last_check,
            "pending_training": False
        }
        
        if EVOLUTION_SIGNAL_FILE.exists():
            try:
                signal_data = json.loads(EVOLUTION_SIGNAL_FILE.read_text(encoding='utf-8'))
                status["pending_training"] = signal_data.get('triggered', False) and not signal_data.get('processed', False)
                status["resonance_count"] = signal_data.get('resonance_count', 0)
            except:
                pass
        
        return status


# Global worker instance
_dpo_worker_instance: Optional[DPOWorker] = None


def get_dpo_worker() -> DPOWorker:
    """Get or create the global DPO worker instance."""
    global _dpo_worker_instance
    if _dpo_worker_instance is None:
        _dpo_worker_instance = DPOWorker()
    return _dpo_worker_instance

