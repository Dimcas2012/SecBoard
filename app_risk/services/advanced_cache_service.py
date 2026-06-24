# SecBoard/app_risk/services/advanced_cache_service.py

import logging
import hashlib
import json
import pickle
import gzip
import time
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from django.core.cache import cache
from django.core.cache.backends.base import BaseCache
from django.utils import timezone
from django.conf import settings
import redis
from threading import Lock
import threading

logger = logging.getLogger(__name__)


class CacheStrategy:
    """Base class for cache strategies"""
    
    def __init__(self, name: str, timeout: int = 300):
        self.name = name
        self.timeout = timeout
        self.hit_count = 0
        self.miss_count = 0
        self.last_accessed = timezone.now()
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hit_count + self.miss_count
        return (self.hit_count / total * 100) if total > 0 else 0
    
    def record_hit(self):
        """Record cache hit"""
        self.hit_count += 1
        self.last_accessed = timezone.now()
    
    def record_miss(self):
        """Record cache miss"""
        self.miss_count += 1
        self.last_accessed = timezone.now()


class LRUCacheStrategy(CacheStrategy):
    """Least Recently Used cache strategy"""
    
    def __init__(self, name: str, timeout: int = 300, max_size: int = 100):
        super().__init__(name, timeout)
        self.max_size = max_size
        self.cache_data = {}
        self.access_order = []
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from LRU cache"""
        with self.lock:
            if key in self.cache_data:
                # Move to end (most recently used)
                self.access_order.remove(key)
                self.access_order.append(key)
                self.record_hit()
                return self.cache_data[key]['value']
            
            self.record_miss()
            return None
    
    def set(self, key: str, value: Any):
        """Set value in LRU cache"""
        with self.lock:
            if key in self.cache_data:
                # Update existing key
                self.access_order.remove(key)
            elif len(self.cache_data) >= self.max_size:
                # Remove least recently used
                oldest_key = self.access_order.pop(0)
                del self.cache_data[oldest_key]
            
            self.cache_data[key] = {
                'value': value,
                'timestamp': timezone.now()
            }
            self.access_order.append(key)
    
    def delete(self, key: str):
        """Delete key from cache"""
        with self.lock:
            if key in self.cache_data:
                del self.cache_data[key]
                self.access_order.remove(key)
    
    def clear(self):
        """Clear all cache data"""
        with self.lock:
            self.cache_data.clear()
            self.access_order.clear()


class TTLCacheStrategy(CacheStrategy):
    """Time-To-Live cache strategy"""
    
    def __init__(self, name: str, timeout: int = 300):
        super().__init__(name, timeout)
        self.cache_data = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from TTL cache"""
        with self.lock:
            if key in self.cache_data:
                entry = self.cache_data[key]
                if timezone.now() - entry['timestamp'] < timedelta(seconds=self.timeout):
                    self.record_hit()
                    return entry['value']
                else:
                    # Expired, remove it
                    del self.cache_data[key]
            
            self.record_miss()
            return None
    
    def set(self, key: str, value: Any):
        """Set value in TTL cache"""
        with self.lock:
            self.cache_data[key] = {
                'value': value,
                'timestamp': timezone.now()
            }
    
    def delete(self, key: str):
        """Delete key from cache"""
        with self.lock:
            if key in self.cache_data:
                del self.cache_data[key]
    
    def clear(self):
        """Clear all cache data"""
        with self.lock:
            self.cache_data.clear()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        with self.lock:
            current_time = timezone.now()
            expired_keys = []
            
            for key, entry in self.cache_data.items():
                if current_time - entry['timestamp'] >= timedelta(seconds=self.timeout):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache_data[key]


class CompressionCacheStrategy(CacheStrategy):
    """Cache strategy with compression"""
    
    def __init__(self, name: str, timeout: int = 300, compression_level: int = 6):
        super().__init__(name, timeout)
        self.compression_level = compression_level
        self.cache_data = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from compressed cache"""
        with self.lock:
            if key in self.cache_data:
                compressed_data = self.cache_data[key]['value']
                try:
                    # Decompress and unpickle
                    decompressed = gzip.decompress(compressed_data)
                    value = pickle.loads(decompressed)
                    self.record_hit()
                    return value
                except Exception as e:
                    logger.error(f"Error decompressing cache data: {e}")
                    del self.cache_data[key]
            
            self.record_miss()
            return None
    
    def set(self, key: str, value: Any):
        """Set value in compressed cache"""
        with self.lock:
            try:
                # Pickle and compress
                pickled_data = pickle.dumps(value)
                compressed_data = gzip.compress(pickled_data, compresslevel=self.compression_level)
                
                self.cache_data[key] = {
                    'value': compressed_data,
                    'timestamp': timezone.now(),
                    'original_size': len(pickled_data),
                    'compressed_size': len(compressed_data)
                }
            except Exception as e:
                logger.error(f"Error compressing cache data: {e}")
    
    def get_compression_ratio(self) -> float:
        """Get average compression ratio"""
        total_original = 0
        total_compressed = 0
        
        for entry in self.cache_data.values():
            total_original += entry.get('original_size', 0)
            total_compressed += entry.get('compressed_size', 0)
        
        return (total_compressed / total_original) if total_original > 0 else 1.0


class AdvancedCacheService:
    """Advanced caching service with multiple strategies and optimization"""
    
    def __init__(self):
        self.strategies = {}
        self.redis_client = None
        self.default_strategy = 'lru'
        self.cache_stats = {
            'total_hits': 0,
            'total_misses': 0,
            'total_sets': 0,
            'total_deletes': 0
        }
        self.lock = Lock()
        
        # Initialize strategies
        self._initialize_strategies()
        
        # Initialize Redis if available
        self._initialize_redis()
        
        # Start background cleanup
        self._start_cleanup_thread()
    
    def _initialize_strategies(self):
        """Initialize different cache strategies"""
        self.strategies = {
            'lru': LRUCacheStrategy('LRU', timeout=300, max_size=100),
            'ttl': TTLCacheStrategy('TTL', timeout=300),
            'compressed': CompressionCacheStrategy('Compressed', timeout=600),
            'quick': TTLCacheStrategy('Quick', timeout=60),
            'persistent': TTLCacheStrategy('Persistent', timeout=3600)
        }
    
    def _initialize_redis(self):
        """Initialize Redis connection if available"""
        try:
            redis_config = getattr(settings, 'REDIS_CONFIG', {})
            if redis_config:
                self.redis_client = redis.Redis(**redis_config)
                self.redis_client.ping()  # Test connection
                logger.info("Redis cache backend initialized successfully")
        except Exception as e:
            logger.warning(f"Redis not available, using local cache: {e}")
            self.redis_client = None
    
    def _start_cleanup_thread(self):
        """Start background thread for cache cleanup"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # Run every 5 minutes
                    self._cleanup_expired_entries()
                except Exception as e:
                    logger.error(f"Error in cache cleanup thread: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_expired_entries(self):
        """Clean up expired entries from all strategies"""
        for strategy in self.strategies.values():
            if hasattr(strategy, 'cleanup_expired'):
                strategy.cleanup_expired()
    
    def get(self, key: str, strategy: str = None) -> Optional[Any]:
        """Get value from cache using specified strategy"""
        strategy = strategy or self.default_strategy
        
        if strategy not in self.strategies:
            logger.warning(f"Unknown cache strategy: {strategy}")
            return None
        
        # Try local strategy first
        value = self.strategies[strategy].get(key)
        if value is not None:
            self.cache_stats['total_hits'] += 1
            return value
        
        # Try Redis if available
        if self.redis_client:
            try:
                redis_value = self.redis_client.get(key)
                if redis_value:
                    # Deserialize and store in local cache
                    value = pickle.loads(redis_value)
                    self.strategies[strategy].set(key, value)
                    self.cache_stats['total_hits'] += 1
                    return value
            except Exception as e:
                logger.error(f"Error getting from Redis: {e}")
        
        # Try Django cache as fallback
        try:
            django_value = cache.get(key)
            if django_value is not None:
                self.strategies[strategy].set(key, django_value)
                self.cache_stats['total_hits'] += 1
                return django_value
        except Exception as e:
            logger.error(f"Error getting from Django cache: {e}")
        
        self.cache_stats['total_misses'] += 1
        return None
    
    def set(self, key: str, value: Any, strategy: str = None, timeout: int = None):
        """Set value in cache using specified strategy"""
        strategy = strategy or self.default_strategy
        
        if strategy not in self.strategies:
            logger.warning(f"Unknown cache strategy: {strategy}")
            return
        
        # Set in local strategy
        self.strategies[strategy].set(key, value)
        
        # Set in Redis if available
        if self.redis_client:
            try:
                serialized_value = pickle.dumps(value)
                cache_timeout = timeout or self.strategies[strategy].timeout
                self.redis_client.setex(key, cache_timeout, serialized_value)
            except Exception as e:
                logger.error(f"Error setting in Redis: {e}")
        
        # Set in Django cache as fallback
        try:
            cache_timeout = timeout or self.strategies[strategy].timeout
            cache.set(key, value, timeout=cache_timeout)
        except Exception as e:
            logger.error(f"Error setting in Django cache: {e}")
        
        self.cache_stats['total_sets'] += 1
    
    def delete(self, key: str, strategy: str = None):
        """Delete key from cache"""
        strategy = strategy or self.default_strategy
        
        # Delete from local strategy
        if strategy in self.strategies:
            self.strategies[strategy].delete(key)
        
        # Delete from Redis
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Error deleting from Redis: {e}")
        
        # Delete from Django cache
        try:
            cache.delete(key)
        except Exception as e:
            logger.error(f"Error deleting from Django cache: {e}")
        
        self.cache_stats['total_deletes'] += 1
    
    def get_or_set(self, key: str, default_func: Callable, strategy: str = None, timeout: int = None) -> Any:
        """Get value from cache or set it using default function"""
        value = self.get(key, strategy)
        if value is not None:
            return value
        
        # Generate value using default function
        try:
            value = default_func()
            self.set(key, value, strategy, timeout)
            return value
        except Exception as e:
            logger.error(f"Error in get_or_set default function: {e}")
            return None
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        # Invalidate from Redis
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"Error invalidating Redis pattern: {e}")
        
        # Invalidate from Django cache (if supported)
        try:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)
        except Exception as e:
            logger.error(f"Error invalidating Django cache pattern: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = {
            'global_stats': self.cache_stats.copy(),
            'strategy_stats': {}
        }
        
        for name, strategy in self.strategies.items():
            stats['strategy_stats'][name] = {
                'hit_count': strategy.hit_count,
                'miss_count': strategy.miss_count,
                'hit_rate': strategy.get_hit_rate(),
                'last_accessed': strategy.last_accessed.isoformat()
            }
            
            # Add compression stats if available
            if hasattr(strategy, 'get_compression_ratio'):
                stats['strategy_stats'][name]['compression_ratio'] = strategy.get_compression_ratio()
        
        # Add Redis stats if available
        if self.redis_client:
            try:
                redis_info = self.redis_client.info()
                stats['redis_stats'] = {
                    'used_memory': redis_info.get('used_memory_human'),
                    'connected_clients': redis_info.get('connected_clients'),
                    'total_commands_processed': redis_info.get('total_commands_processed')
                }
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
        
        return stats
    
    def warm_up_cache(self, warm_up_data: Dict[str, Any]):
        """Warm up cache with predefined data"""
        for key, config in warm_up_data.items():
            value = config.get('value')
            strategy = config.get('strategy', self.default_strategy)
            timeout = config.get('timeout')
            
            if value is not None:
                self.set(key, value, strategy, timeout)
                logger.info(f"Warmed up cache key: {key}")
    
    def clear_all_caches(self):
        """Clear all cache strategies"""
        # Clear local strategies
        for strategy in self.strategies.values():
            strategy.clear()
        
        # Clear Redis
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Error clearing Redis: {e}")
        
        # Clear Django cache
        try:
            cache.clear()
        except Exception as e:
            logger.error(f"Error clearing Django cache: {e}")
        
        # Reset stats
        self.cache_stats = {
            'total_hits': 0,
            'total_misses': 0,
            'total_sets': 0,
            'total_deletes': 0
        }
    
    def get_cache_size(self) -> Dict[str, int]:
        """Get cache size for each strategy"""
        sizes = {}
        
        for name, strategy in self.strategies.items():
            if hasattr(strategy, 'cache_data'):
                sizes[name] = len(strategy.cache_data)
        
        return sizes
    
    def export_cache_data(self, strategy: str = None) -> Dict[str, Any]:
        """Export cache data for backup/analysis"""
        if strategy:
            if strategy in self.strategies and hasattr(self.strategies[strategy], 'cache_data'):
                return {strategy: self.strategies[strategy].cache_data}
        else:
            export_data = {}
            for name, strat in self.strategies.items():
                if hasattr(strat, 'cache_data'):
                    export_data[name] = strat.cache_data
            return export_data
        
        return {}


# Global cache service instance
cache_service = AdvancedCacheService()


def get_cache_service() -> AdvancedCacheService:
    """Get global cache service instance"""
    return cache_service