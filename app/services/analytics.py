"""Analytics service with dual-source strategy."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from scipy import stats

from app.models.models import Event, Assignment, Variant, Experiment
from app.core.cache import cache_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for experiment analytics with dual-source strategy."""
    
    def __init__(self):
        self.cache_ttl = 60  # 1 minute for results cache
        self.use_clickhouse_threshold = timedelta(hours=1)  # Use CH for data older than 1 hour
    
    async def get_experiment_results(
        self,
        db: AsyncSession,
        experiment_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        granularity: str = "day",  # realtime, hour, day
        metrics: Optional[List[str]] = None,
        include_ci: bool = True,
        min_sample: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get experiment results with flexible parameters.
        
        Uses PostgreSQL for recent data, prepared for ClickHouse for historical.
        """
        # Default time range
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        # Default metrics
        if not metrics:
            metrics = ["conversion_rate", "unique_users", "event_count"]
        
        # Check cache
        cache_key = self._get_cache_key(
            experiment_id, start_date, end_date, event_types, granularity
        )
        cached = await cache_manager.get(cache_key)
        if cached:
            logger.debug(f"Results cache hit for experiment {experiment_id}")
            return cached
        
        # Determine data source
        use_clickhouse = self._should_use_clickhouse(start_date, end_date)
        
        if use_clickhouse:
            # In production, query ClickHouse
            results = await self._get_clickhouse_results(
                experiment_id, start_date, end_date, event_types,
                granularity, metrics, include_ci, min_sample, filters
            )
        else:
            # Query PostgreSQL for recent data
            results = await self._get_postgres_results(
                db, experiment_id, start_date, end_date, event_types,
                granularity, metrics, include_ci, min_sample, filters
            )
        
        # Cache results
        await cache_manager.set(cache_key, results, self.cache_ttl)
        
        return results
    
    async def _get_postgres_results(
        self,
        db: AsyncSession,
        experiment_id: int,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]],
        granularity: str,
        metrics: List[str],
        include_ci: bool,
        min_sample: int,
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get results from PostgreSQL."""
        
        # Fetch experiment and variants
        result = await db.execute(
            select(Experiment, Variant)
            .join(Variant)
            .where(Experiment.id == experiment_id)
        )
        experiment_variants = result.all()
        
        if not experiment_variants:
            return {"error": "Experiment not found"}
        
        experiment = experiment_variants[0][0]
        variants = [v for _, v in experiment_variants]
        
        # Build time truncation based on granularity
        if granularity == "day":
            time_trunc = func.date_trunc("day", Event.timestamp)
        elif granularity == "hour":
            time_trunc = func.date_trunc("hour", Event.timestamp)
        else:  # realtime
            time_trunc = Event.timestamp
        
        # Base query for events
        base_query = select(
            Event.variant_id,
            time_trunc.label("time_bucket"),
            Event.event_type,
            func.count(Event.id).label("event_count"),
            func.count(func.distinct(Event.user_id)).label("unique_users")
        ).where(
            and_(
                Event.experiment_id == experiment_id,
                Event.timestamp >= start_date,
                Event.timestamp <= end_date,
                Event.timestamp >= Event.assignment_at  # Only post-assignment events
            )
        )
        
        # Apply event type filter
        if event_types:
            base_query = base_query.where(Event.event_type.in_(event_types))
        
        # Apply property filters if provided
        if filters:
            for key, value in filters.items():
                base_query = base_query.where(
                    Event.properties[key].astext == str(value)
                )
        
        # Group by variant and time
        query = base_query.group_by(
            Event.variant_id,
            "time_bucket",
            Event.event_type
        ).having(
            func.count(func.distinct(Event.user_id)) >= min_sample
        )
        
        # Execute query
        result = await db.execute(query)
        rows = result.all()
        
        # Process results
        variant_metrics = {}
        control_variant = None
        
        for variant in variants:
            variant_data = {
                "id": variant.id,
                "key": variant.key,
                "name": variant.name,
                "is_control": variant.is_control,
                "metrics": {},
                "time_series": []
            }
            
            if variant.is_control:
                control_variant = variant
            
            # Calculate metrics for this variant
            variant_rows = [r for r in rows if r.variant_id == variant.id]
            
            for metric in metrics:
                if metric == "conversion_rate":
                    conversions = sum(r.event_count for r in variant_rows if r.event_type == "conversion")
                    users = sum(r.unique_users for r in variant_rows)
                    rate = conversions / users if users > 0 else 0
                    
                    metric_data = {
                        "value": rate,
                        "conversions": conversions,
                        "users": users
                    }
                    
                    # Add confidence interval if requested
                    if include_ci and users >= min_sample:
                        ci_lower, ci_upper = self._calculate_confidence_interval(
                            conversions, users
                        )
                        metric_data["ci_lower"] = ci_lower
                        metric_data["ci_upper"] = ci_upper
                    
                    variant_data["metrics"][metric] = metric_data
                    
                elif metric == "unique_users":
                    users = sum(r.unique_users for r in variant_rows)
                    variant_data["metrics"][metric] = {"value": users}
                    
                elif metric == "event_count":
                    count = sum(r.event_count for r in variant_rows)
                    variant_data["metrics"][metric] = {"value": count}
            
            # Build time series
            for row in variant_rows:
                variant_data["time_series"].append({
                    "time": row.time_bucket.isoformat() if hasattr(row.time_bucket, 'isoformat') else str(row.time_bucket),
                    "event_type": row.event_type,
                    "event_count": row.event_count,
                    "unique_users": row.unique_users
                })
            
            variant_metrics[variant.id] = variant_data
        
        # Calculate lift vs control
        if control_variant and include_ci:
            control_data = variant_metrics.get(control_variant.id, {})
            control_rate = control_data.get("metrics", {}).get("conversion_rate", {}).get("value", 0)
            
            for variant_id, variant_data in variant_metrics.items():
                if variant_id != control_variant.id:
                    variant_rate = variant_data.get("metrics", {}).get("conversion_rate", {}).get("value", 0)
                    if control_rate > 0:
                        lift = ((variant_rate - control_rate) / control_rate) * 100
                        variant_data["metrics"]["conversion_rate"]["lift_vs_control"] = round(lift, 2)
                        
                        # Statistical significance
                        if include_ci:
                            p_value = self._calculate_p_value(
                                variant_data["metrics"]["conversion_rate"],
                                control_data["metrics"]["conversion_rate"]
                            )
                            variant_data["metrics"]["conversion_rate"]["p_value"] = p_value
                            variant_data["metrics"]["conversion_rate"]["is_significant"] = p_value < 0.05
        
        return {
            "experiment_id": experiment_id,
            "experiment_key": experiment.key,
            "experiment_name": experiment.name,
            "status": experiment.status.value,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "granularity": granularity
            },
            "variants": list(variant_metrics.values()),
            "summary": self._calculate_summary(variant_metrics, control_variant)
        }
    
    async def _get_clickhouse_results(
        self,
        experiment_id: int,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]],
        granularity: str,
        metrics: List[str],
        include_ci: bool,
        min_sample: int,
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get results from ClickHouse (placeholder for actual implementation).
        
        In production, this would query ClickHouse for historical data.
        """
        # This is where you would implement ClickHouse queries
        # For now, return a placeholder
        logger.info(f"Would query ClickHouse for experiment {experiment_id}")
        
        # Example ClickHouse query:
        # from clickhouse_driver import Client
        # client = Client(host=settings.clickhouse_host)
        # 
        # query = """
        # SELECT
        #     variant_id,
        #     toStartOfDay(timestamp) as day,
        #     event_type,
        #     count() as event_count,
        #     uniqExact(user_id) as unique_users
        # FROM experiments.events
        # WHERE experiment_id = %(experiment_id)s
        #     AND timestamp BETWEEN %(start_date)s AND %(end_date)s
        #     AND timestamp >= assignment_at
        # GROUP BY variant_id, day, event_type
        # HAVING unique_users >= %(min_sample)s
        # """
        
        return {
            "source": "clickhouse",
            "message": "ClickHouse integration pending",
            "experiment_id": experiment_id
        }
    
    def _should_use_clickhouse(self, start_date: datetime, end_date: datetime) -> bool:
        """Determine if we should use ClickHouse based on time range."""
        now = datetime.now(timezone.utc)
        
        # Use ClickHouse if querying data older than threshold
        if now - start_date > self.use_clickhouse_threshold:
            return True
        
        # Use ClickHouse for large time ranges
        if end_date - start_date > timedelta(days=30):
            return True
        
        return False
    
    def _calculate_confidence_interval(
        self,
        successes: int,
        trials: int,
        confidence: float = 0.95
    ) -> tuple:
        """Calculate Wilson score confidence interval for proportions."""
        if trials == 0:
            return (0, 0)
        
        p = successes / trials
        z = stats.norm.ppf((1 + confidence) / 2)
        
        denominator = 1 + z**2 / trials
        center = (p + z**2 / (2 * trials)) / denominator
        margin = z * np.sqrt((p * (1 - p) / trials + z**2 / (4 * trials**2))) / denominator
        
        return (
            max(0, center - margin),
            min(1, center + margin)
        )
    
    def _calculate_p_value(
        self,
        treatment_metrics: Dict,
        control_metrics: Dict
    ) -> float:
        """Calculate p-value using two-proportion z-test."""
        n1 = control_metrics.get("users", 0)
        n2 = treatment_metrics.get("users", 0)
        
        if n1 == 0 or n2 == 0:
            return 1.0
        
        x1 = control_metrics.get("conversions", 0)
        x2 = treatment_metrics.get("conversions", 0)
        
        p1 = x1 / n1
        p2 = x2 / n2
        p_pooled = (x1 + x2) / (n1 + n2)
        
        se = np.sqrt(p_pooled * (1 - p_pooled) * (1/n1 + 1/n2))
        
        if se == 0:
            return 1.0
        
        z = (p2 - p1) / se
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        
        return p_value
    
    def _calculate_summary(
        self,
        variant_metrics: Dict,
        control_variant: Optional[Variant]
    ) -> Dict[str, Any]:
        """Calculate experiment summary statistics."""
        total_users = sum(
            v.get("metrics", {}).get("unique_users", {}).get("value", 0)
            for v in variant_metrics.values()
        )
        
        # Find winning variant
        best_variant = None
        best_rate = 0
        
        for variant_data in variant_metrics.values():
            rate = variant_data.get("metrics", {}).get("conversion_rate", {}).get("value", 0)
            if rate > best_rate:
                best_rate = rate
                best_variant = variant_data["key"]
        
        # Calculate statistical power
        power = self._calculate_statistical_power(variant_metrics)
        
        return {
            "total_users": total_users,
            "winning_variant": best_variant,
            "best_conversion_rate": round(best_rate, 4),
            "statistical_power": round(power, 2),
            "minimum_detectable_effect": 0.01,  # Would calculate based on sample size
            "recommendation": self._get_recommendation(variant_metrics, power)
        }
    
    def _calculate_statistical_power(self, variant_metrics: Dict) -> float:
        """Calculate statistical power of the experiment."""
        # Simplified power calculation
        # In production, use proper power analysis
        total_users = sum(
            v.get("metrics", {}).get("unique_users", {}).get("value", 0)
            for v in variant_metrics.values()
        )
        
        if total_users < 1000:
            return 0.2
        elif total_users < 5000:
            return 0.5
        elif total_users < 10000:
            return 0.8
        else:
            return 0.95
    
    def _get_recommendation(self, variant_metrics: Dict, power: float) -> str:
        """Get recommendation based on results."""
        if power < 0.8:
            return "Continue experiment - insufficient statistical power"
        
        # Check for significant winner
        significant_winners = [
            v for v in variant_metrics.values()
            if v.get("metrics", {}).get("conversion_rate", {}).get("is_significant", False)
        ]
        
        if significant_winners:
            best = max(significant_winners, 
                      key=lambda v: v.get("metrics", {}).get("conversion_rate", {}).get("value", 0))
            return f"Deploy variant '{best['key']}' - statistically significant improvement"
        
        return "No significant difference detected - consider stopping experiment"
    
    def _get_cache_key(
        self,
        experiment_id: int,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]],
        granularity: str
    ) -> str:
        """Generate cache key for results."""
        event_types_str = ",".join(sorted(event_types)) if event_types else "all"
        return f"results:{experiment_id}:{start_date.date()}:{end_date.date()}:{event_types_str}:{granularity}"


# Global analytics service instance
analytics_service = AnalyticsService()