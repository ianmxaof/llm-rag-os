"""
Base Collector Interface
------------------------
Abstract base class for all data source collectors.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class BaseCollector(ABC):
    """Base class for all data source collectors."""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize collector with optional configuration.
        
        Args:
            config: Configuration dictionary specific to collector type
        """
        self.config = config or {}
        self.last_run: Optional[datetime] = None
        
    @abstractmethod
    def collect(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Collect new items from the source.
        
        Args:
            since: Only collect items newer than this timestamp
            
        Returns:
            List of items, each with at least:
            - title: str
            - content: str or content_snippet
            - url: str
            - source: str
            - published_at: datetime
            - raw_data: dict (original item data)
        """
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this source."""
        pass
    
    def normalize_item(self, item: Dict) -> Dict:
        """
        Normalize an item to standard format.
        
        Args:
            item: Raw item from source
            
        Returns:
            Normalized item with standard fields
        """
        return {
            "title": item.get("title", ""),
            "content": item.get("content") or item.get("content_snippet", ""),
            "url": item.get("url") or item.get("link", ""),
            "source": self.get_source_name(),
            "published_at": item.get("published_at") or item.get("pubDate"),
            "raw_data": item,
        }
    
    def filter_ai_related(self, items: List[Dict]) -> List[Dict]:
        """
        Filter items to only those related to AI/ML.
        
        Args:
            items: List of items to filter
            
        Returns:
            Filtered list of AI-related items
        """
        ai_keywords = [
            "ai", "llm", "model", "claude", "grok", "gpt", "mistral",
            "anthropic", "openai", "xai", "machine learning", "deep learning",
            "neural", "transformer", "embedding", "rag", "retrieval"
        ]
        
        filtered = []
        for item in items:
            text = (
                (item.get("title", "") or "") +
                " " +
                (item.get("content", "") or item.get("content_snippet", "") or "")
            ).lower()
            
            if any(keyword in text for keyword in ai_keywords):
                filtered.append(item)
        
        return filtered

