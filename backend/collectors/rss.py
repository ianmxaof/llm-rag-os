"""
RSS Collector
-------------
Collects items from RSS feeds (including FreshRSS API).
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
import requests
import feedparser

from backend.collectors.base import BaseCollector


class RSSCollector(BaseCollector):
    """Collector for RSS feeds."""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.freshrss_url = config.get("freshrss_url") or os.getenv("FRESHRSS_URL", "")
        self.freshrss_user = config.get("freshrss_user") or os.getenv("FRESHRSS_USER", "")
        self.freshrss_password = config.get("freshrss_password") or os.getenv("FRESHRSS_PASSWORD", "")
        
    def get_source_name(self) -> str:
        return "rss"
    
    def collect(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Collect items from RSS feeds.
        
        Args:
            since: Only collect items newer than this timestamp
            
        Returns:
            List of RSS items
        """
        items = []
        
        # If FreshRSS is configured, use its API
        if self.freshrss_url and self.freshrss_user:
            items.extend(self._collect_from_freshrss(since))
        
        # Also collect from direct RSS URLs in config
        rss_urls = self.config.get("feeds", [])
        for url in rss_urls:
            items.extend(self._collect_from_rss_url(url, since))
        
        # Filter AI-related
        items = self.filter_ai_related(items)
        
        return items
    
    def _collect_from_freshrss(self, since: Optional[datetime] = None) -> List[Dict]:
        """Collect unread items from FreshRSS API."""
        items = []
        
        if not self.freshrss_url or not self.freshrss_user:
            return items
        
        # FreshRSS API endpoint for unread items
        api_url = f"{self.freshrss_url}/api/greader.php/stream/contents"
        params = {
            "output": "json",
            "xt": "user/-/state/com.google/read",  # Unread only
            "n": "100",  # Limit to 100 items
        }
        
        auth = (self.freshrss_user, self.freshrss_password)
        
        try:
            response = requests.get(api_url, params=params, auth=auth, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    pub_date = datetime.fromtimestamp(int(item.get("published", 0)))
                    if since and pub_date < since:
                        continue
                    
                    items.append({
                        "title": item.get("title", ""),
                        "content": item.get("content", {}).get("content", ""),
                        "url": item.get("alternate", [{}])[0].get("href", ""),
                        "published_at": pub_date,
                        "source": item.get("origin", {}).get("title", "rss"),
                    })
        except Exception as e:
            print(f"[WARN] Failed to fetch from FreshRSS: {e}")
        
        return items
    
    def _collect_from_rss_url(self, url: str, since: Optional[datetime] = None) -> List[Dict]:
        """Collect items from a direct RSS URL."""
        items = []
        
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Parse published date
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6])
                
                if since and pub_date and pub_date < since:
                    continue
                
                items.append({
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", "") or entry.get("description", ""),
                    "url": entry.get("link", ""),
                    "published_at": pub_date or datetime.now(),
                    "source": feed.feed.get("title", url),
                })
        except Exception as e:
            print(f"[WARN] Failed to fetch RSS from {url}: {e}")
        
        return items

