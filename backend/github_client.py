"""
GitHub API client for fetching issue data.

This module provides a client for interacting with the GitHub REST API v3,
with comprehensive error handling and rate limit management.
"""

import re
import logging
from typing import Tuple, List, Dict, Any
from urllib.parse import urlparse
import requests
from requests.exceptions import RequestException, Timeout

from .models import GitHubIssueData


logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""
    pass


class GitHubURLError(GitHubClientError):
    """Raised when a GitHub URL is invalid or cannot be parsed."""
    pass


class GitHubNotFoundError(GitHubClientError):
    """Raised when a repository or issue is not found (404)."""
    pass


class GitHubForbiddenError(GitHubClientError):
    """Raised when access is forbidden, e.g., private repository (403)."""
    pass


class GitHubRateLimitError(GitHubClientError):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubClient:
    """Client for interacting with GitHub REST API.
    
    This client handles fetching issue data, parsing URLs, and managing
    API authentication and error handling.
    
    Attributes:
        token: GitHub Personal Access Token for authentication
        base_url: Base URL for GitHub API (default: https://api.github.com)
        timeout: Request timeout in seconds (default: 10)
    """
    
    BASE_URL = "https://api.github.com"
    TIMEOUT = 10  # seconds
    
    def __init__(self, token: str):
        """Initialize GitHub client with authentication token.
        
        Args:
            token: GitHub Personal Access Token
        """
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Issue-Assistant/1.0"
        })
    
    def parse_repo_url(self, url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo name.
        
        Supports various URL formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - github.com/owner/repo
        - owner/repo
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo)
            
        Raises:
            GitHubURLError: If URL cannot be parsed
        """
        url = url.strip()
        
        # Remove .git suffix if present
        url = re.sub(r'\.git$', '', url)
        
        # Pattern to match GitHub URLs
        patterns = [
            r'^https?://github\.com/([\w\-\.]+)/([\w\-\.]+)/?$',
            r'^github\.com/([\w\-\.]+)/([\w\-\.]+)/?$',
            r'^([\w\-\.]+)/([\w\-\.]+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                owner, repo = match.groups()
                logger.info(f"Parsed GitHub URL: owner={owner}, repo={repo}")
                return owner, repo
        
        raise GitHubURLError(
            f"Invalid GitHub URL format: {url}. "
            "Expected format: https://github.com/owner/repo"
        )
    
    def fetch_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssueData:
        """Fetch issue data from GitHub API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number to fetch
            
        Returns:
            GitHubIssueData with issue details
            
        Raises:
            GitHubNotFoundError: If repository or issue not found
            GitHubForbiddenError: If access is forbidden (private repo)
            GitHubRateLimitError: If rate limit exceeded
            GitHubClientError: For other API errors
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        
        try:
            logger.info(f"Fetching issue: {owner}/{repo}#{issue_number}")
            response = self.session.get(url, timeout=self.TIMEOUT)
            
            # Handle different HTTP status codes
            if response.status_code == 404:
                raise GitHubNotFoundError(
                    f"Repository '{owner}/{repo}' or issue #{issue_number} not found. "
                    "Please verify the URL and issue number."
                )
            elif response.status_code == 403:
                # Check if it's rate limit or forbidden
                if 'X-RateLimit-Remaining' in response.headers:
                    remaining = response.headers.get('X-RateLimit-Remaining', '0')
                    if remaining == '0':
                        reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                        raise GitHubRateLimitError(
                            f"GitHub API rate limit exceeded. Resets at: {reset_time}"
                        )
                raise GitHubForbiddenError(
                    f"Access forbidden to '{owner}/{repo}'. "
                    "This may be a private repository. Check your token permissions."
                )
            elif response.status_code == 401:
                raise GitHubClientError(
                    "GitHub authentication failed. Please check your GITHUB_TOKEN."
                )
            
            response.raise_for_status()
            
            # Parse issue data
            data = response.json()
            
            # Fetch comments separately
            comments = self._fetch_comments(owner, repo, issue_number)
            
            issue_data = GitHubIssueData(
                title=data.get('title', ''),
                body=data.get('body') or '',  # Handle None
                comments=comments,
                labels=[label['name'] for label in data.get('labels', [])],
                state=data.get('state', 'open'),
                created_at=data.get('created_at', ''),
                updated_at=data.get('updated_at', '')
            )
            
            logger.info(
                f"Successfully fetched issue: {len(comments)} comments, "
                f"{len(issue_data.labels)} labels"
            )
            
            return issue_data
            
        except Timeout:
            raise GitHubClientError(
                "Request to GitHub API timed out. Please try again."
            )
        except RequestException as e:
            raise GitHubClientError(
                f"Network error while fetching GitHub data: {str(e)}"
            )
    
    def _fetch_comments(self, owner: str, repo: str, issue_number: int) -> List[str]:
        """Fetch all comments for an issue.
        
        Handles pagination to fetch all comments if there are many.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            List of comment body texts
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        comments = []
        page = 1
        per_page = 100  # Max allowed by GitHub API
        
        try:
            while True:
                logger.debug(f"Fetching comments page {page}")
                response = self.session.get(
                    url,
                    params={'page': page, 'per_page': per_page},
                    timeout=self.TIMEOUT
                )
                response.raise_for_status()
                
                page_comments = response.json()
                if not page_comments:
                    break
                
                # Extract comment bodies, excluding empty ones
                for comment in page_comments:
                    body = comment.get('body', '').strip()
                    if body:
                        comments.append(body)
                
                # Check if there are more pages
                if len(page_comments) < per_page:
                    break
                page += 1
                
                # Safety limit to prevent infinite loops
                if page > 10:  # Max 1000 comments
                    logger.warning(
                        f"Stopping comment fetch at page {page} (too many comments)"
                    )
                    break
            
            logger.debug(f"Fetched {len(comments)} comments")
            return comments
            
        except RequestException as e:
            # Don't fail the entire request if comments can't be fetched
            logger.warning(f"Failed to fetch comments: {str(e)}")
            return []
    
    def check_rate_limit(self) -> Dict[str, Any]:
        """Check current GitHub API rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        url = f"{self.BASE_URL}/rate_limit"
        
        try:
            response = self.session.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Failed to check rate limit: {str(e)}")
            return {}
