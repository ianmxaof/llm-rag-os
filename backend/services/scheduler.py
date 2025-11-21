"""
Scheduler Service
-----------------
Cron-like scheduling for intelligence pipeline.
"""

import time
from datetime import datetime, timedelta
from typing import Callable, Optional
import threading


class Scheduler:
    """Simple scheduler for running tasks at intervals."""
    
    def __init__(self, interval_seconds: int = 900):
        """
        Initialize scheduler.
        
        Args:
            interval_seconds: Interval between runs in seconds (default: 15 minutes)
        """
        self.interval = interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_run: Optional[datetime] = None
        
    def start(self, task: Callable):
        """
        Start the scheduler with a task.
        
        Args:
            task: Function to run at intervals
        """
        if self.running:
            return
        
        self.running = True
        
        def run_loop():
            while self.running:
                try:
                    task()
                    self.last_run = datetime.now()
                except Exception as e:
                    print(f"[ERROR] Scheduled task failed: {e}")
                
                # Sleep for interval
                time.sleep(self.interval)
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "interval_seconds": self.interval,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": (self.last_run + timedelta(seconds=self.interval)).isoformat() if self.last_run else None,
        }

