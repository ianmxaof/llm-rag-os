"""
Data Source Collectors
----------------------
Collectors for various data sources (RSS, GitHub, arXiv, Reddit, etc.)
"""

from backend.collectors.base import BaseCollector
from backend.collectors.rss import RSSCollector
from backend.collectors.github import GitHubCollector
from backend.collectors.arxiv import ArxivCollector
from backend.collectors.reddit import RedditCollector

__all__ = [
    "BaseCollector",
    "RSSCollector",
    "GitHubCollector",
    "ArxivCollector",
    "RedditCollector",
]

