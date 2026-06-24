"""
Services package for risk assessment application.
Contains business logic separated from views.
"""

# Core services
from .report_config import ReportConfig
from .report_data_service import ReportDataService
from .report_generator_factory import ReportGeneratorFactory
from .report_validators import validate_report_config, ReportConfigValidator
from .report_service import ReportService

# Performance optimization services
from .report_data_service_optimized import OptimizedReportDataService
from .advanced_cache_service import (
    AdvancedCacheService, 
    CacheStrategy, 
    LRUCacheStrategy, 
    TTLCacheStrategy, 
    CompressionCacheStrategy,
    get_cache_service
)
from .async_report_service import (
    AsyncReportService,
    ReportStatus,
    ReportJob,
    ProgressTracker,
    NotificationService,
    get_async_report_service
)
from .pagination_service import (
    PaginationService,
    PaginationConfig,
    PaginationResult,
    LazyLoader,
    QuerySetLazyLoader,
    ListLazyLoader,
    CallableLazyLoader,
    ReportPaginationService,
    InfiniteScrollPagination,
    get_pagination_service
)
from .serialization_service import (
    SerializationService,
    SerializationFormat,
    CompressionMethod,
    SerializationConfig,
    OptimizedJSONEncoder,
    ReportSerializationService,
    get_serialization_service,
    get_report_serialization_service
)
from .performance_monitoring import (
    PerformanceMonitoringService,
    PerformanceMetric,
    QueryMetric,
    FunctionMetric,
    PerformanceCollector,
    SystemMonitor,
    DatabaseMonitor,
    PerformanceAnalyzer,
    performance_monitor,
    get_performance_monitor_service,
    start_monitoring,
    stop_monitoring,
    add_metric,
    monitor_query,
    monitor_operation
)

__all__ = [
    # Core services
    'ReportConfig',
    'ReportDataService',
    'ReportGeneratorFactory',
    'validate_report_config',
    'ReportConfigValidator',
    'ReportService',
    
    # Optimized services
    'OptimizedReportDataService',
    
    # Cache services
    'AdvancedCacheService',
    'CacheStrategy',
    'LRUCacheStrategy',
    'TTLCacheStrategy',
    'CompressionCacheStrategy',
    'get_cache_service',
    
    # Async services
    'AsyncReportService',
    'ReportStatus',
    'ReportJob',
    'ProgressTracker',
    'NotificationService',
    'get_async_report_service',
    
    # Pagination services
    'PaginationService',
    'PaginationConfig',
    'PaginationResult',
    'LazyLoader',
    'QuerySetLazyLoader',
    'ListLazyLoader',
    'CallableLazyLoader',
    'ReportPaginationService',
    'InfiniteScrollPagination',
    'get_pagination_service',
    
    # Serialization services
    'SerializationService',
    'SerializationFormat',
    'CompressionMethod',
    'SerializationConfig',
    'OptimizedJSONEncoder',
    'ReportSerializationService',
    'get_serialization_service',
    'get_report_serialization_service',
    
    # Performance monitoring
    'PerformanceMonitoringService',
    'PerformanceMetric',
    'QueryMetric',
    'FunctionMetric',
    'PerformanceCollector',
    'SystemMonitor',
    'DatabaseMonitor',
    'PerformanceAnalyzer',
    'performance_monitor',
    'get_performance_monitor_service',
    'start_monitoring',
    'stop_monitoring',
    'add_metric',
    'monitor_query',
    'monitor_operation',
] 