# SecBoard/app_risk/services/performance_monitoring.py

import logging
import time
import psutil
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import connection
from django.core.cache import cache
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import functools
import traceback
from collections import defaultdict, deque
import json

from .advanced_cache_service import get_cache_service

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    category: str = "general"
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category,
            'tags': self.tags
        }


@dataclass
class QueryMetric:
    """Database query performance metric"""
    sql: str
    execution_time: float
    timestamp: datetime
    params: List[Any] = None
    row_count: Optional[int] = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'sql': self.sql[:500],  # Truncate long queries
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
            'params': str(self.params)[:200],  # Truncate long params
            'row_count': self.row_count
        }


@dataclass
class FunctionMetric:
    """Function execution performance metric"""
    function_name: str
    execution_time: float
    timestamp: datetime
    args_count: int
    kwargs_count: int
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'function_name': self.function_name,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat(),
            'args_count': self.args_count,
            'kwargs_count': self.kwargs_count,
            'success': self.success,
            'error_message': self.error_message
        }


class PerformanceCollector:
    """Collects performance metrics"""
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.metrics = deque(maxlen=max_metrics)
        self.query_metrics = deque(maxlen=max_metrics)
        self.function_metrics = deque(maxlen=max_metrics)
        self.lock = threading.Lock()
    
    def add_metric(self, metric: PerformanceMetric):
        """Add a performance metric"""
        with self.lock:
            self.metrics.append(metric)
    
    def add_query_metric(self, metric: QueryMetric):
        """Add a query metric"""
        with self.lock:
            self.query_metrics.append(metric)
    
    def add_function_metric(self, metric: FunctionMetric):
        """Add a function metric"""
        with self.lock:
            self.function_metrics.append(metric)
    
    def get_metrics(self, category: str = None, 
                   since: datetime = None) -> List[PerformanceMetric]:
        """Get performance metrics"""
        with self.lock:
            filtered_metrics = []
            
            for metric in self.metrics:
                if category and metric.category != category:
                    continue
                if since and metric.timestamp < since:
                    continue
                filtered_metrics.append(metric)
            
            return filtered_metrics
    
    def get_query_metrics(self, since: datetime = None) -> List[QueryMetric]:
        """Get query metrics"""
        with self.lock:
            if since:
                return [m for m in self.query_metrics if m.timestamp >= since]
            return list(self.query_metrics)
    
    def get_function_metrics(self, function_name: str = None,
                           since: datetime = None) -> List[FunctionMetric]:
        """Get function metrics"""
        with self.lock:
            filtered_metrics = []
            
            for metric in self.function_metrics:
                if function_name and metric.function_name != function_name:
                    continue
                if since and metric.timestamp < since:
                    continue
                filtered_metrics.append(metric)
            
            return filtered_metrics
    
    def clear_metrics(self):
        """Clear all metrics"""
        with self.lock:
            self.metrics.clear()
            self.query_metrics.clear()
            self.function_metrics.clear()


class SystemMonitor:
    """Monitors system resources"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_interval = 30  # seconds
    
    def start_monitoring(self):
        """Start system monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(self.monitor_interval)
    
    def _collect_system_metrics(self):
        """Collect system metrics"""
        timestamp = timezone.now()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.collector.add_metric(PerformanceMetric(
            name="cpu_usage",
            value=cpu_percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.collector.add_metric(PerformanceMetric(
            name="memory_usage",
            value=memory.percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))
        
        self.collector.add_metric(PerformanceMetric(
            name="memory_available",
            value=memory.available / 1024 / 1024,  # MB
            unit="MB",
            timestamp=timestamp,
            category="system"
        ))
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        self.collector.add_metric(PerformanceMetric(
            name="disk_usage",
            value=disk.percent,
            unit="percent",
            timestamp=timestamp,
            category="system"
        ))
        
        # Network metrics
        network = psutil.net_io_counters()
        self.collector.add_metric(PerformanceMetric(
            name="network_bytes_sent",
            value=network.bytes_sent,
            unit="bytes",
            timestamp=timestamp,
            category="network"
        ))
        
        self.collector.add_metric(PerformanceMetric(
            name="network_bytes_recv",
            value=network.bytes_recv,
            unit="bytes",
            timestamp=timestamp,
            category="network"
        ))


class DatabaseMonitor:
    """Monitors database performance"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
        self.enabled = True
    
    def enable(self):
        """Enable database monitoring"""
        self.enabled = True
    
    def disable(self):
        """Disable database monitoring"""
        self.enabled = False
    
    @contextmanager
    def monitor_query(self, sql: str, params: List[Any] = None):
        """Context manager for monitoring database queries"""
        if not self.enabled:
            yield
            return
        
        start_time = time.time()
        row_count = None
        
        try:
            yield
            # Try to get row count from cursor
            if hasattr(connection, 'cursor'):
                cursor = connection.cursor()
                if hasattr(cursor, 'rowcount'):
                    row_count = cursor.rowcount
        finally:
            execution_time = time.time() - start_time
            
            metric = QueryMetric(
                sql=sql,
                execution_time=execution_time,
                timestamp=timezone.now(),
                params=params or [],
                row_count=row_count
            )
            
            self.collector.add_query_metric(metric)


def performance_monitor(category: str = "function"):
    """Decorator for monitoring function performance"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error_message = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                execution_time = time.time() - start_time
                
                # Get collector from global monitor
                if hasattr(performance_monitor_service, 'collector'):
                    metric = FunctionMetric(
                        function_name=f"{func.__module__}.{func.__name__}",
                        execution_time=execution_time,
                        timestamp=timezone.now(),
                        args_count=len(args),
                        kwargs_count=len(kwargs),
                        success=success,
                        error_message=error_message
                    )
                    
                    performance_monitor_service.collector.add_function_metric(metric)
        
        return wrapper
    return decorator


class PerformanceAnalyzer:
    """Analyzes performance metrics"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
    
    def analyze_queries(self, time_window: timedelta = None) -> Dict[str, Any]:
        """Analyze database query performance"""
        since = timezone.now() - (time_window or timedelta(hours=1))
        query_metrics = self.collector.get_query_metrics(since=since)
        
        if not query_metrics:
            return {'total_queries': 0}
        
        # Group by query pattern
        query_groups = defaultdict(list)
        for metric in query_metrics:
            # Normalize SQL for grouping
            normalized_sql = self._normalize_sql(metric.sql)
            query_groups[normalized_sql].append(metric)
        
        # Analyze each group
        slow_queries = []
        total_time = 0
        
        for sql_pattern, metrics in query_groups.items():
            execution_times = [m.execution_time for m in metrics]
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            total_time += sum(execution_times)
            
            if avg_time > 1.0:  # Slow query threshold
                slow_queries.append({
                    'sql_pattern': sql_pattern,
                    'count': len(metrics),
                    'avg_time': avg_time,
                    'max_time': max_time,
                    'total_time': sum(execution_times)
                })
        
        # Sort slow queries by total time
        slow_queries.sort(key=lambda x: x['total_time'], reverse=True)
        
        return {
            'total_queries': len(query_metrics),
            'total_time': total_time,
            'avg_time': total_time / len(query_metrics),
            'slow_queries': slow_queries[:10],  # Top 10 slow queries
            'unique_queries': len(query_groups)
        }
    
    def analyze_functions(self, time_window: timedelta = None) -> Dict[str, Any]:
        """Analyze function performance"""
        since = timezone.now() - (time_window or timedelta(hours=1))
        function_metrics = self.collector.get_function_metrics(since=since)
        
        if not function_metrics:
            return {'total_calls': 0}
        
        # Group by function name
        function_groups = defaultdict(list)
        for metric in function_metrics:
            function_groups[metric.function_name].append(metric)
        
        # Analyze each function
        slow_functions = []
        error_functions = []
        total_time = 0
        
        for function_name, metrics in function_groups.items():
            execution_times = [m.execution_time for m in metrics]
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            total_time += sum(execution_times)
            
            error_count = sum(1 for m in metrics if not m.success)
            error_rate = error_count / len(metrics) * 100
            
            function_stats = {
                'function_name': function_name,
                'call_count': len(metrics),
                'avg_time': avg_time,
                'max_time': max_time,
                'total_time': sum(execution_times),
                'error_count': error_count,
                'error_rate': error_rate
            }
            
            if avg_time > 0.5:  # Slow function threshold
                slow_functions.append(function_stats)
            
            if error_rate > 5:  # Error rate threshold
                error_functions.append(function_stats)
        
        # Sort by total time
        slow_functions.sort(key=lambda x: x['total_time'], reverse=True)
        error_functions.sort(key=lambda x: x['error_rate'], reverse=True)
        
        return {
            'total_calls': len(function_metrics),
            'total_time': total_time,
            'avg_time': total_time / len(function_metrics),
            'slow_functions': slow_functions[:10],
            'error_functions': error_functions[:10],
            'unique_functions': len(function_groups)
        }
    
    def analyze_system_resources(self, time_window: timedelta = None) -> Dict[str, Any]:
        """Analyze system resource usage"""
        since = timezone.now() - (time_window or timedelta(hours=1))
        system_metrics = self.collector.get_metrics(category="system", since=since)
        
        if not system_metrics:
            return {}
        
        # Group by metric name
        metric_groups = defaultdict(list)
        for metric in system_metrics:
            metric_groups[metric.name].append(metric.value)
        
        analysis = {}
        for metric_name, values in metric_groups.items():
            analysis[metric_name] = {
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'count': len(values)
            }
        
        return analysis
    
    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for grouping similar queries"""
        # Remove specific values and normalize whitespace
        import re
        
        # Replace numbers with placeholder
        sql = re.sub(r'\b\d+\b', '?', sql)
        
        # Replace quoted strings with placeholder
        sql = re.sub(r"'[^']*'", "'?'", sql)
        sql = re.sub(r'"[^"]*"', '"?"', sql)
        
        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql.strip())
        
        return sql


class PerformanceMonitoringService:
    """Main performance monitoring service"""
    
    def __init__(self):
        self.collector = PerformanceCollector()
        self.system_monitor = SystemMonitor(self.collector)
        self.database_monitor = DatabaseMonitor(self.collector)
        self.analyzer = PerformanceAnalyzer(self.collector)
        self.cache_service = get_cache_service()
        self.enabled = True
    
    def start(self):
        """Start performance monitoring"""
        if not self.enabled:
            return
        
        self.system_monitor.start_monitoring()
        self.database_monitor.enable()
        logger.info("Performance monitoring service started")
    
    def stop(self):
        """Stop performance monitoring"""
        self.system_monitor.stop_monitoring()
        self.database_monitor.disable()
        logger.info("Performance monitoring service stopped")
    
    def enable(self):
        """Enable performance monitoring"""
        self.enabled = True
    
    def disable(self):
        """Disable performance monitoring"""
        self.enabled = False
    
    def add_custom_metric(self, name: str, value: float, unit: str, 
                         category: str = "custom", tags: Dict[str, str] = None):
        """Add a custom performance metric"""
        if not self.enabled:
            return
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=timezone.now(),
            category=category,
            tags=tags or {}
        )
        
        self.collector.add_metric(metric)
    
    def get_performance_report(self, time_window: timedelta = None) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        time_window = time_window or timedelta(hours=1)
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'time_window_hours': time_window.total_seconds() / 3600,
            'query_analysis': self.analyzer.analyze_queries(time_window),
            'function_analysis': self.analyzer.analyze_functions(time_window),
            'system_analysis': self.analyzer.analyze_system_resources(time_window)
        }
        
        # Cache the report
        cache_key = f"performance_report_{int(time.time() // 300)}"  # 5-minute cache
        self.cache_service.set(cache_key, report, timeout=300)
        
        return report
    
    def get_real_time_stats(self) -> Dict[str, Any]:
        """Get real-time performance statistics"""
        return {
            'timestamp': timezone.now().isoformat(),
            'system': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent
            },
            'metrics_count': {
                'performance_metrics': len(self.collector.metrics),
                'query_metrics': len(self.collector.query_metrics),
                'function_metrics': len(self.collector.function_metrics)
            }
        }
    
    def export_metrics(self, format: str = 'json', 
                      time_window: timedelta = None) -> str:
        """Export metrics in specified format"""
        since = timezone.now() - (time_window or timedelta(hours=1))
        
        data = {
            'performance_metrics': [m.to_dict() for m in self.collector.get_metrics(since=since)],
            'query_metrics': [m.to_dict() for m in self.collector.get_query_metrics(since=since)],
            'function_metrics': [m.to_dict() for m in self.collector.get_function_metrics(since=since)]
        }
        
        if format.lower() == 'json':
            return json.dumps(data, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_metrics(self):
        """Clear all collected metrics"""
        self.collector.clear_metrics()
        logger.info("Performance metrics cleared")
    
    @contextmanager
    def monitor_operation(self, operation_name: str, category: str = "operation"):
        """Context manager for monitoring operations"""
        start_time = time.time()
        
        try:
            yield
        finally:
            execution_time = time.time() - start_time
            
            self.add_custom_metric(
                name=f"{operation_name}_duration",
                value=execution_time,
                unit="seconds",
                category=category
            )


# Global performance monitoring service instance
performance_monitor_service = PerformanceMonitoringService()


def get_performance_monitor_service() -> PerformanceMonitoringService:
    """Get global performance monitoring service instance"""
    return performance_monitor_service


# Convenience functions
def start_monitoring():
    """Start performance monitoring"""
    performance_monitor_service.start()


def stop_monitoring():
    """Stop performance monitoring"""
    performance_monitor_service.stop()


def add_metric(name: str, value: float, unit: str, category: str = "custom"):
    """Add a custom metric"""
    performance_monitor_service.add_custom_metric(name, value, unit, category)


def monitor_query(sql: str, params: List[Any] = None):
    """Monitor database query"""
    return performance_monitor_service.database_monitor.monitor_query(sql, params)


def monitor_operation(operation_name: str, category: str = "operation"):
    """Monitor operation"""
    return performance_monitor_service.monitor_operation(operation_name, category)