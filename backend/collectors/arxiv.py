"""
ArXiv Collector
---------------
Collects papers from arXiv RSS feeds.
"""

from datetime import datetime
from typing import List, Dict, Optional
import feedparser

from backend.collectors.base import BaseCollector


class ArxivCollector(BaseCollector):
    """Collector for arXiv papers."""
    
    ARXIV_RSS_BASE = "http://arxiv.org/rss"
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.categories = config.get("categories", ["cs.AI", "cs.LG", "cs.CL"])
        
    def get_source_name(self) -> str:
        return "arxiv"
    
    def collect(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Collect recent arXiv papers.
        
        Args:
            since: Only collect items newer than this timestamp
            
        Returns:
            List of arXiv papers
        """
        items = []
        
        for category in self.categories:
            rss_url = f"{self.ARXIV_RSS_BASE}/{category}"
            items.extend(self._collect_from_category(rss_url, category, since))
        
        # ArXiv papers are already AI-related, no need to filter
        return items
    
    def _collect_from_category(self, url: str, category: str, since: Optional[datetime] = None) -> List[Dict]:
        """Collect papers from an arXiv category RSS feed."""
        items = []
        
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Parse published date
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                
                if since and pub_date and pub_date < since:
                    continue
                
                # Extract authors from summary
                summary = entry.get("summary", "")
                authors = []
                if "Authors:" in summary:
                    authors_line = summary.split("Authors:")[1].split("\n")[0]
                    authors = [a.strip() for a in authors_line.split(",")]
                
                items.append({
                    "title": entry.get("title", "").replace("\n", " "),
                    "content": summary,
                    "url": entry.get("link", ""),
                    "published_at": pub_date or datetime.now(),
                    "source": f"arxiv:{category}",
                    "authors": authors,
                    "arxiv_id": entry.get("id", "").split("/")[-1] if "/" in entry.get("id", "") else "",
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch arXiv category {category}: {e}")
        
        return items

