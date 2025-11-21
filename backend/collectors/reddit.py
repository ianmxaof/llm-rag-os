"""
Reddit Collector
----------------
Collects posts from Reddit via RSS.
"""

from datetime import datetime
from typing import List, Dict, Optional
import feedparser

from backend.collectors.base import BaseCollector


class RedditCollector(BaseCollector):
    """Collector for Reddit subreddits via RSS."""
    
    REDDIT_RSS_BASE = "https://www.reddit.com/r"
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.subreddits = config.get("subreddits", [
            "MachineLearning",
            "LocalLLaMA",
            "singularity",
        ])
        
    def get_source_name(self) -> str:
        return "reddit"
    
    def collect(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Collect recent Reddit posts.
        
        Args:
            since: Only collect items newer than this timestamp
            
        Returns:
            List of Reddit posts
        """
        items = []
        
        for subreddit in self.subreddits:
            rss_url = f"{self.REDDIT_RSS_BASE}/{subreddit}/.rss"
            items.extend(self._collect_from_subreddit(rss_url, subreddit, since))
        
        # Filter AI-related
        items = self.filter_ai_related(items)
        
        return items
    
    def _collect_from_subreddit(self, url: str, subreddit: str, since: Optional[datetime] = None) -> List[Dict]:
        """Collect posts from a Reddit subreddit RSS feed."""
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
                
                items.append({
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", "") or entry.get("description", ""),
                    "url": entry.get("link", ""),
                    "published_at": pub_date or datetime.now(),
                    "source": f"reddit:r/{subreddit}",
                    "author": entry.get("author", ""),
                    "score": entry.get("reddit_score", 0),
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch Reddit r/{subreddit}: {e}")
        
        return items

