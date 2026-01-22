"""
Simple file-based cache for GitHub issue analysis results.

This module provides caching functionality to avoid re-analyzing
the same issues and improve performance.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AnalysisCache:
    """Simple file-based cache for analysis results.
    
    Cache entries are stored as JSON files with TTL support.
    """
    
    def __init__(self, cache_dir: str = ".cache", ttl_seconds: int = 86400):
        """Initialize cache.
        
        Args:
            cache_dir: Directory to store cache files
            ttl_seconds: Time-to-live for cache entries (default: 24 hours)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_seconds
        logger.info(f"Initialized cache at {self.cache_dir} with TTL {ttl_seconds}s")
    
    def _get_cache_key(self, owner: str, repo: str, issue_number: int) -> str:
        """Generate cache key for an issue.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            Cache key (hash)
        """
        key_str = f"{owner}/{repo}#{issue_number}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get file path for cache entry.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, owner: str, repo: str, issue_number: int) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis result.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            
        Returns:
            Cached result if found and not expired, None otherwise
        """
        cache_key = self._get_cache_key(owner, repo, issue_number)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            logger.debug(f"Cache miss: {owner}/{repo}#{issue_number}")
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            
            # Check if expired
            cached_time = cached_data.get('cached_at', 0)
            age = time.time() - cached_time
            
            if age > self.ttl_seconds:
                logger.info(f"Cache expired: {owner}/{repo}#{issue_number} (age: {age:.0f}s)")
                cache_path.unlink()  # Delete expired cache
                return None
            
            logger.info(f"Cache hit: {owner}/{repo}#{issue_number} (age: {age:.0f}s)")
            return cached_data.get('result')
            
        except Exception as e:
            logger.error(f"Error reading cache: {str(e)}")
            return None
    
    def set(self, owner: str, repo: str, issue_number: int, result: Dict[str, Any]) -> None:
        """Store analysis result in cache.
        
        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            result: Analysis result to cache
        """
        cache_key = self._get_cache_key(owner, repo, issue_number)
        cache_path = self._get_cache_path(cache_key)
        
        cached_data = {
            'cached_at': time.time(),
            'owner': owner,
            'repo': repo,
            'issue_number': issue_number,
            'result': result
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cached_data, f, indent=2)
            logger.info(f"Cached result: {owner}/{repo}#{issue_number}")
        except Exception as e:
            logger.error(f"Error writing cache: {str(e)}")
    
    def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.error(f"Error deleting cache file {cache_file}: {str(e)}")
        
        logger.info(f"Cleared {count} cache entries")
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_entries = len(list(self.cache_dir.glob("*.json")))
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
        
        return {
            'total_entries': total_entries,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'cache_dir': str(self.cache_dir)
        }
