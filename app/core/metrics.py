"""Metrics collection for monitoring."""

import time
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Prometheus metrics collector."""
    
    def __init__(self):
        if not settings.prometheus_enabled:
            self.enabled = False
            return
        
        self.enabled = True
        
        # Request metrics
        self.request_count = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"]
        )
        
        self.request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
        
        # Business metrics
        self.assignment_count = Counter(
            "assignments_total",
            "Total assignments created",
            ["experiment_id", "variant_id"]
        )
        
        self.event_count = Counter(
            "events_total",
            "Total events recorded",
            ["experiment_id", "event_type"]
        )
        
        self.cache_hits = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"]
        )
        
        self.cache_misses = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"]
        )
        
        # System metrics
        self.active_experiments = Gauge(
            "active_experiments",
            "Number of active experiments"
        )
        
        self.db_pool_size = Gauge(
            "database_pool_size",
            "Database connection pool size"
        )
        
        self.redis_connections = Gauge(
            "redis_connections",
            "Active Redis connections"
        )
    
    def record_request_duration(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float
    ):
        """Record HTTP request metrics."""
        if not self.enabled:
            return
        
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration_ms / 1000)  # Convert to seconds
    
    def record_assignment(self, experiment_id: int, variant_id: int):
        """Record assignment creation."""
        if not self.enabled:
            return
        
        self.assignment_count.labels(
            experiment_id=str(experiment_id),
            variant_id=str(variant_id)
        ).inc()
    
    def record_event(self, experiment_id: int, event_type: str):
        """Record event creation."""
        if not self.enabled:
            return
        
        self.event_count.labels(
            experiment_id=str(experiment_id),
            event_type=event_type
        ).inc()
    
    def record_cache_hit(self, cache_type: str = "assignment"):
        """Record cache hit."""
        if not self.enabled:
            return
        
        self.cache_hits.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str = "assignment"):
        """Record cache miss."""
        if not self.enabled:
            return
        
        self.cache_misses.labels(cache_type=cache_type).inc()
    
    def set_active_experiments(self, count: int):
        """Set active experiments count."""
        if not self.enabled:
            return
        
        self.active_experiments.set(count)
    
    def set_db_pool_size(self, size: int):
        """Set database pool size."""
        if not self.enabled:
            return
        
        self.db_pool_size.set(size)
    
    def set_redis_connections(self, count: int):
        """Set Redis connections count."""
        if not self.enabled:
            return
        
        self.redis_connections.set(count)
    
    def get_metrics(self) -> bytes:
        """Get Prometheus metrics."""
        if not self.enabled:
            return b""
        
        return generate_latest()


# Global metrics instance
metrics: Optional[MetricsCollector] = None

if settings.prometheus_enabled:
    metrics = MetricsCollector()
    logger.info("Prometheus metrics enabled")