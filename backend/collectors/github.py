"""
GitHub Collector
----------------
Collects activity from GitHub repositories and users.
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
import requests

from backend.collectors.base import BaseCollector


class GitHubCollector(BaseCollector):
    """Collector for GitHub repository and user activity."""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        self.token = config.get("token") or os.getenv("GITHUB_TOKENS", "")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}" if self.token else None,
        }
        # Remove None headers
        self.headers = {k: v for k, v in self.headers.items() if v is not None}
        
    def get_source_name(self) -> str:
        return "github"
    
    def collect(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Collect recent GitHub activity.
        
        Args:
            since: Only collect items newer than this timestamp
            
        Returns:
            List of GitHub activity items
        """
        items = []
        
        # Get repositories/users to monitor from config
        repos = self.config.get("repos", [])
        users = self.config.get("users", [])
        
        # Collect from repositories
        for repo in repos:
            if "/" in repo:
                owner, repo_name = repo.split("/", 1)
                items.extend(self._get_repo_activity(owner, repo_name, since))
            else:
                # Assume it's an organization
                items.extend(self._get_org_activity(repo, since))
        
        # Collect from users
        for user in users:
            items.extend(self._get_user_activity(user, since))
        
        # Filter AI-related
        items = self.filter_ai_related(items)
        
        return items
    
    def _get_repo_activity(self, owner: str, repo: str, since: Optional[datetime] = None) -> List[Dict]:
        """Get recent activity from a repository."""
        items = []
        
        # Get recent commits
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": 10}
        if since:
            params["since"] = since.isoformat()
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                commits = response.json()
                for commit in commits:
                    items.append({
                        "title": f"Commit: {commit['commit']['message'][:100]}",
                        "content": commit['commit']['message'],
                        "url": commit['html_url'],
                        "published_at": datetime.fromisoformat(commit['commit']['author']['date'].replace('Z', '+00:00')),
                        "author": commit['commit']['author']['name'],
                        "sha": commit['sha'],
                    })
        except Exception as e:
            print(f"[WARN] Failed to fetch GitHub repo {owner}/{repo}: {e}")
        
        # Get recent issues/PRs
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {"per_page": 10, "state": "all"}
        if since:
            params["since"] = since.isoformat()
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                for issue in issues:
                    items.append({
                        "title": issue['title'],
                        "content": issue.get('body', ''),
                        "url": issue['html_url'],
                        "published_at": datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')),
                        "author": issue['user']['login'],
                        "type": "pull_request" if 'pull_request' in issue else "issue",
                    })
        except Exception as e:
            print(f"[WARN] Failed to fetch GitHub issues for {owner}/{repo}: {e}")
        
        return items
    
    def _get_org_activity(self, org: str, since: Optional[datetime] = None) -> List[Dict]:
        """Get recent activity from an organization."""
        items = []
        
        # Get organization repositories
        url = f"{self.base_url}/orgs/{org}/repos"
        params = {"per_page": 10, "sort": "updated"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                repos = response.json()
                for repo in repos[:5]:  # Limit to top 5 recently updated
                    owner = repo['owner']['login']
                    repo_name = repo['name']
                    items.extend(self._get_repo_activity(owner, repo_name, since))
        except Exception as e:
            print(f"[WARN] Failed to fetch GitHub org {org}: {e}")
        
        return items
    
    def _get_user_activity(self, user: str, since: Optional[datetime] = None) -> List[Dict]:
        """Get recent activity from a user."""
        items = []
        
        # Get user's public events
        url = f"{self.base_url}/users/{user}/events/public"
        params = {"per_page": 10}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                events = response.json()
                for event in events:
                    if event['type'] in ['PushEvent', 'IssuesEvent', 'PullRequestEvent']:
                        items.append({
                            "title": f"{event['type']} by {user}",
                            "content": str(event.get('payload', {})),
                            "url": f"https://github.com/{user}",
                            "published_at": datetime.fromisoformat(event['created_at'].replace('Z', '+00:00')),
                            "author": user,
                            "type": event['type'],
                        })
        except Exception as e:
            print(f"[WARN] Failed to fetch GitHub user {user}: {e}")
        
        return items

