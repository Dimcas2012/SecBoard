# SecBoard/app_risk/services/pagination_service.py

import logging
import math
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet, Count, Q
from django.utils import timezone
from django.core.cache import cache
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .advanced_cache_service import get_cache_service
from .report_config import ReportConfig

logger = logging.getLogger(__name__)


@dataclass
class PaginationConfig:
    """Configuration for pagination"""
    page_size: int = 50
    max_page_size: int = 1000
    enable_caching: bool = True
    cache_timeout: int = 300
    lazy_loading: bool = True
    prefetch_next_page: bool = True
    
    def validate(self):
        """Validate pagination configuration"""
        if self.page_size <= 0:
            raise ValueError("Page size must be positive")
        if self.page_size > self.max_page_size:
            raise ValueError(f"Page size cannot exceed {self.max_page_size}")


@dataclass
class PaginationResult:
    """Result of pagination operation"""
    items: List[Any]
    page_number: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
    next_page: Optional[int]
    previous_page: Optional[int]
    start_index: int
    end_index: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'items': self.items,
            'pagination': {
                'page_number': self.page_number,
                'page_size': self.page_size,
                'total_items': self.total_items,
                'total_pages': self.total_pages,
                'has_next': self.has_next,
                'has_previous': self.has_previous,
                'next_page': self.next_page,
                'previous_page': self.previous_page,
                'start_index': self.start_index,
                'end_index': self.end_index
            }
        }


class LazyLoader(ABC):
    """Abstract base class for lazy loading"""
    
    @abstractmethod
    def load_page(self, page_number: int, page_size: int) -> List[Any]:
        """Load a specific page of data"""
        pass
    
    @abstractmethod
    def get_total_count(self) -> int:
        """Get total count of items"""
        pass
    
    @abstractmethod
    def get_cache_key(self, page_number: int, page_size: int) -> str:
        """Get cache key for a specific page"""
        pass


class QuerySetLazyLoader(LazyLoader):
    """Lazy loader for Django QuerySets"""
    
    def __init__(self, queryset: QuerySet, cache_prefix: str = "lazy_loader"):
        self.queryset = queryset
        self.cache_prefix = cache_prefix
        self.cache_service = get_cache_service()
        self._total_count = None
    
    def load_page(self, page_number: int, page_size: int) -> List[Any]:
        """Load a specific page from QuerySet"""
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        
        # Use database slicing for efficiency
        page_data = list(self.queryset[start_index:end_index])
        return page_data
    
    def get_total_count(self) -> int:
        """Get total count with caching"""
        if self._total_count is None:
            cache_key = f"{self.cache_prefix}_total_count"
            cached_count = self.cache_service.get(cache_key)
            
            if cached_count is not None:
                self._total_count = cached_count
            else:
                self._total_count = self.queryset.count()
                self.cache_service.set(cache_key, self._total_count, timeout=300)
        
        return self._total_count
    
    def get_cache_key(self, page_number: int, page_size: int) -> str:
        """Get cache key for a specific page"""
        queryset_hash = hash(str(self.queryset.query))
        return f"{self.cache_prefix}_page_{page_number}_{page_size}_{queryset_hash}"


class ListLazyLoader(LazyLoader):
    """Lazy loader for Python lists"""
    
    def __init__(self, data_list: List[Any], cache_prefix: str = "list_loader"):
        self.data_list = data_list
        self.cache_prefix = cache_prefix
        self.cache_service = get_cache_service()
    
    def load_page(self, page_number: int, page_size: int) -> List[Any]:
        """Load a specific page from list"""
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        
        return self.data_list[start_index:end_index]
    
    def get_total_count(self) -> int:
        """Get total count of items"""
        return len(self.data_list)
    
    def get_cache_key(self, page_number: int, page_size: int) -> str:
        """Get cache key for a specific page"""
        data_hash = hash(str(self.data_list))
        return f"{self.cache_prefix}_page_{page_number}_{page_size}_{data_hash}"


class CallableLazyLoader(LazyLoader):
    """Lazy loader using callable functions"""
    
    def __init__(self, load_func: Callable[[int, int], List[Any]], 
                 count_func: Callable[[], int], cache_prefix: str = "callable_loader"):
        self.load_func = load_func
        self.count_func = count_func
        self.cache_prefix = cache_prefix
        self.cache_service = get_cache_service()
        self._total_count = None
    
    def load_page(self, page_number: int, page_size: int) -> List[Any]:
        """Load page using callable function"""
        return self.load_func(page_number, page_size)
    
    def get_total_count(self) -> int:
        """Get total count using callable function"""
        if self._total_count is None:
            self._total_count = self.count_func()
        return self._total_count
    
    def get_cache_key(self, page_number: int, page_size: int) -> str:
        """Get cache key for a specific page"""
        func_hash = hash(str(self.load_func))
        return f"{self.cache_prefix}_page_{page_number}_{page_size}_{func_hash}"


class PaginationService:
    """Service for handling pagination and lazy loading"""
    
    def __init__(self, config: PaginationConfig = None):
        self.config = config or PaginationConfig()
        self.config.validate()
        self.cache_service = get_cache_service()
        self.prefetch_cache = {}
    
    def paginate_queryset(self, queryset: QuerySet, page_number: int, 
                         page_size: int = None, cache_prefix: str = None) -> PaginationResult:
        """Paginate a Django QuerySet"""
        page_size = page_size or self.config.page_size
        cache_prefix = cache_prefix or "queryset_pagination"
        
        # Create lazy loader
        lazy_loader = QuerySetLazyLoader(queryset, cache_prefix)
        
        return self._paginate_with_loader(lazy_loader, page_number, page_size)
    
    def paginate_list(self, data_list: List[Any], page_number: int, 
                     page_size: int = None, cache_prefix: str = None) -> PaginationResult:
        """Paginate a Python list"""
        page_size = page_size or self.config.page_size
        cache_prefix = cache_prefix or "list_pagination"
        
        # Create lazy loader
        lazy_loader = ListLazyLoader(data_list, cache_prefix)
        
        return self._paginate_with_loader(lazy_loader, page_number, page_size)
    
    def paginate_callable(self, load_func: Callable[[int, int], List[Any]], 
                         count_func: Callable[[], int], page_number: int,
                         page_size: int = None, cache_prefix: str = None) -> PaginationResult:
        """Paginate using callable functions"""
        page_size = page_size or self.config.page_size
        cache_prefix = cache_prefix or "callable_pagination"
        
        # Create lazy loader
        lazy_loader = CallableLazyLoader(load_func, count_func, cache_prefix)
        
        return self._paginate_with_loader(lazy_loader, page_number, page_size)
    
    def _paginate_with_loader(self, lazy_loader: LazyLoader, page_number: int, 
                             page_size: int) -> PaginationResult:
        """Paginate using a lazy loader"""
        # Validate page size
        if page_size > self.config.max_page_size:
            page_size = self.config.max_page_size
        
        # Get total count
        total_items = lazy_loader.get_total_count()
        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 1
        
        # Validate page number
        if page_number < 1:
            page_number = 1
        elif page_number > total_pages:
            page_number = total_pages
        
        # Try to get from cache first
        cache_key = lazy_loader.get_cache_key(page_number, page_size)
        cached_items = None
        
        if self.config.enable_caching:
            cached_items = self.cache_service.get(cache_key)
        
        if cached_items is not None:
            items = cached_items
        else:
            # Load page data
            items = lazy_loader.load_page(page_number, page_size)
            
            # Cache the result
            if self.config.enable_caching:
                self.cache_service.set(cache_key, items, timeout=self.config.cache_timeout)
        
        # Calculate pagination info
        start_index = (page_number - 1) * page_size + 1
        end_index = min(start_index + len(items) - 1, total_items)
        
        has_next = page_number < total_pages
        has_previous = page_number > 1
        
        next_page = page_number + 1 if has_next else None
        previous_page = page_number - 1 if has_previous else None
        
        # Prefetch next page if enabled
        if self.config.prefetch_next_page and has_next:
            self._prefetch_page(lazy_loader, next_page, page_size)
        
        return PaginationResult(
            items=items,
            page_number=page_number,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            next_page=next_page,
            previous_page=previous_page,
            start_index=start_index,
            end_index=end_index
        )
    
    def _prefetch_page(self, lazy_loader: LazyLoader, page_number: int, page_size: int):
        """Prefetch a page in background"""
        if not self.config.enable_caching:
            return
        
        cache_key = lazy_loader.get_cache_key(page_number, page_size)
        
        # Check if already cached
        if self.cache_service.get(cache_key) is not None:
            return
        
        # Load and cache in background
        try:
            items = lazy_loader.load_page(page_number, page_size)
            self.cache_service.set(cache_key, items, timeout=self.config.cache_timeout)
        except Exception as e:
            logger.error(f"Error prefetching page {page_number}: {e}")
    
    def get_page_range(self, current_page: int, total_pages: int, 
                      window_size: int = 5) -> List[int]:
        """Get page range for pagination UI"""
        if total_pages <= window_size:
            return list(range(1, total_pages + 1))
        
        # Calculate start and end of window
        half_window = window_size // 2
        start = max(1, current_page - half_window)
        end = min(total_pages, current_page + half_window)
        
        # Adjust if we're at the beginning or end
        if start == 1:
            end = min(total_pages, window_size)
        elif end == total_pages:
            start = max(1, total_pages - window_size + 1)
        
        return list(range(start, end + 1))
    
    def invalidate_cache(self, cache_prefix: str):
        """Invalidate cached pages for a specific prefix"""
        pattern = f"{cache_prefix}_*"
        self.cache_service.invalidate_pattern(pattern)
    
    def get_pagination_stats(self) -> Dict[str, Any]:
        """Get pagination statistics"""
        cache_stats = self.cache_service.get_cache_stats()
        
        return {
            'config': {
                'page_size': self.config.page_size,
                'max_page_size': self.config.max_page_size,
                'enable_caching': self.config.enable_caching,
                'cache_timeout': self.config.cache_timeout,
                'lazy_loading': self.config.lazy_loading,
                'prefetch_next_page': self.config.prefetch_next_page
            },
            'cache_stats': cache_stats,
            'prefetch_cache_size': len(self.prefetch_cache)
        }


class ReportPaginationService:
    """Specialized pagination service for reports"""
    
    def __init__(self, report_config: ReportConfig):
        self.report_config = report_config
        self.pagination_config = PaginationConfig(
            page_size=report_config.page_size or 100,
            enable_caching=True,
            cache_timeout=600,
            lazy_loading=True,
            prefetch_next_page=True
        )
        self.pagination_service = PaginationService(self.pagination_config)
    
    def paginate_assets(self, assets_queryset: QuerySet, page_number: int) -> PaginationResult:
        """Paginate assets for reports"""
        return self.pagination_service.paginate_queryset(
            assets_queryset, 
            page_number, 
            cache_prefix=f"report_assets_{self.report_config.hash}"
        )
    
    def paginate_vulnerabilities(self, vulnerabilities_queryset: QuerySet, 
                                page_number: int) -> PaginationResult:
        """Paginate vulnerabilities for reports"""
        return self.pagination_service.paginate_queryset(
            vulnerabilities_queryset,
            page_number,
            cache_prefix=f"report_vulnerabilities_{self.report_config.hash}"
        )
    
    def paginate_risk_treatments(self, treatments_queryset: QuerySet, 
                                page_number: int) -> PaginationResult:
        """Paginate risk treatments for reports"""
        return self.pagination_service.paginate_queryset(
            treatments_queryset,
            page_number,
            cache_prefix=f"report_treatments_{self.report_config.hash}"
        )
    
    def get_chunked_data(self, data_loader: Callable[[int, int], List[Any]], 
                        total_count: int, chunk_size: int = None) -> List[List[Any]]:
        """Get data in chunks for processing"""
        chunk_size = chunk_size or self.pagination_config.page_size
        chunks = []
        
        total_pages = math.ceil(total_count / chunk_size)
        
        for page_num in range(1, total_pages + 1):
            chunk = data_loader(page_num, chunk_size)
            if chunk:
                chunks.append(chunk)
        
        return chunks
    
    def stream_data(self, data_loader: Callable[[int, int], List[Any]], 
                   total_count: int, chunk_size: int = None):
        """Stream data in chunks (generator)"""
        chunk_size = chunk_size or self.pagination_config.page_size
        total_pages = math.ceil(total_count / chunk_size)
        
        for page_num in range(1, total_pages + 1):
            chunk = data_loader(page_num, chunk_size)
            if chunk:
                yield chunk
    
    def get_lazy_report_data(self, data_service) -> Dict[str, Any]:
        """Get report data with lazy loading"""
        # This method would be implemented to work with your data service
        # to provide lazy-loaded report data
        
        lazy_data = {
            'assets_loader': lambda page, size: self._load_assets_page(data_service, page, size),
            'vulnerabilities_loader': lambda page, size: self._load_vulnerabilities_page(data_service, page, size),
            'treatments_loader': lambda page, size: self._load_treatments_page(data_service, page, size),
            'statistics': data_service.get_quick_statistics(),
            'total_counts': {
                'assets': data_service._get_user_companies_optimized().count(),
                'vulnerabilities': 0,  # Would be calculated
                'treatments': 0  # Would be calculated
            }
        }
        
        return lazy_data
    
    def _load_assets_page(self, data_service, page_number: int, page_size: int) -> List[Any]:
        """Load a page of assets"""
        # This would integrate with your data service
        # For now, return empty list
        return []
    
    def _load_vulnerabilities_page(self, data_service, page_number: int, page_size: int) -> List[Any]:
        """Load a page of vulnerabilities"""
        # This would integrate with your data service
        return []
    
    def _load_treatments_page(self, data_service, page_number: int, page_size: int) -> List[Any]:
        """Load a page of risk treatments"""
        # This would integrate with your data service
        return []


class InfiniteScrollPagination:
    """Pagination service for infinite scroll UI"""
    
    def __init__(self, page_size: int = 20):
        self.page_size = page_size
        self.cache_service = get_cache_service()
    
    def get_next_items(self, loader: LazyLoader, cursor: str = None, 
                      limit: int = None) -> Dict[str, Any]:
        """Get next items for infinite scroll"""
        limit = limit or self.page_size
        
        # Parse cursor to get page number
        if cursor:
            try:
                page_number = int(cursor) + 1
            except (ValueError, TypeError):
                page_number = 1
        else:
            page_number = 1
        
        # Load items
        items = loader.load_page(page_number, limit)
        
        # Check if there are more items
        total_items = loader.get_total_count()
        has_more = (page_number * limit) < total_items
        
        next_cursor = str(page_number) if has_more else None
        
        return {
            'items': items,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'page_number': page_number,
            'total_items': total_items
        }


# Global pagination service instance
pagination_service = PaginationService()


def get_pagination_service() -> PaginationService:
    """Get global pagination service instance"""
    return pagination_service