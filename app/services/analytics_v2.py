"""Analytics service using stored procedures."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import math

from sqlalchemy.ext.asyncio import AsyncSession
from scipy import stats as scipy_stats

from app.core.stored_procedures import stored_procedure_dao
from app.core.cache import cache_manager

logger = logging.getLogger(__name__)


class AnalyticsServiceV2:
    """Service for analytics using stored procedures."""
    
    def __init__(self):
        self.cache_ttl = 60  # 1 minute cache for results
        self.confidence_level = 0.95
    
    async def get_experiment_results(
        self,
        db: AsyncSession,
        experiment_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        granularity: str = "day",
        metrics: Optional[List[str]] = None,
        include_ci: bool = True,
        min_sample: int = 100
    ) -> Dict[str, Any]:
        """
        Get experiment results using stored procedures.
        
        Args:
            db: Database session
            experiment_id: Experiment ID
            start_date: Start date for analysis
            end_date: End date for analysis
            event_types: Event types to analyze
            granularity: Time granularity (realtime, hour, day)
            metrics: Metrics to calculate
            include_ci: Include confidence intervals
            min_sample: Minimum sample size for reporting
        """
        # Check cache first
        cache_key = self._get_cache_key(
            experiment_id, start_date, end_date, 
            event_types, granularity
        )
        
        cached = await cache_manager.get(cache_key)
        if cached:
            logger.debug(f"Analytics cache hit for experiment {experiment_id}")
            return cached
        
        try:
            # Get experiment details
            experiment = await stored_procedure_dao.get_experiment_with_variants(
                db, experiment_id
            )
            
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")
            
            # Get metrics from stored procedure
            variant_metrics = await stored_procedure_dao.get_experiment_metrics(
                db=db,
                experiment_id=experiment_id,
                start_date=start_date,
                end_date=end_date,
                event_types=event_types
            )
            
            # Process results based on granularity
            if granularity == "day":
                daily_metrics = await stored_procedure_dao.get_daily_metrics(
                    db=db,
                    experiment_id=experiment_id,
                    days=7 if not start_date else (datetime.now() - start_date).days
                )
            else:
                daily_metrics = []
            
            # Format results
            results = {
                "experiment_id": experiment_id,
                "experiment_key": experiment["key"],
                "experiment_name": experiment["name"],
                "status": experiment["status"],
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "granularity": granularity,
                "variants": [],
                "summary": {},
                "time_series": daily_metrics if granularity == "day" else []
            }
            
            # Process each variant
            control_metrics = None
            
            for variant in variant_metrics:
                # Skip if below minimum sample size
                if variant["unique_users"] < min_sample:
                    continue
                
                variant_data = {
                    "variant_key": variant["variant_key"],
                    "variant_name": variant["variant_name"],
                    "is_control": variant["is_control"],
                    "metrics": {
                        "unique_users": variant["unique_users"],
                        "total_events": variant["total_events"],
                        "conversion_rate": {
                            "value": variant["conversion_rate"],
                            "conversions": variant["conversion_count"]
                        }
                    }
                }
                
                # Add confidence intervals if requested
                if include_ci and variant["unique_users"] > 0:
                    ci_lower, ci_upper = self._calculate_confidence_interval(
                        variant["conversion_count"],
                        variant["unique_users"]
                    )
                    variant_data["metrics"]["conversion_rate"]["ci_lower"] = ci_lower
                    variant_data["metrics"]["conversion_rate"]["ci_upper"] = ci_upper
                
                # Store control for comparison
                if variant["is_control"]:
                    control_metrics = variant
                
                # Add average value if present
                if variant["avg_value"] is not None:
                    variant_data["metrics"]["avg_value"] = variant["avg_value"]
                
                results["variants"].append(variant_data)
            
            # Calculate lift vs control
            if control_metrics:
                for variant in results["variants"]:
                    if not variant["is_control"]:
                        # Find the original metrics
                        variant_metrics_data = next(
                            (v for v in variant_metrics if v["variant_key"] == variant["variant_key"]),
                            None
                        )
                        
                        if variant_metrics_data:
                            lift = self._calculate_lift(
                                variant_metrics_data["conversion_rate"],
                                control_metrics["conversion_rate"]
                            )
                            variant["metrics"]["conversion_rate"]["lift_vs_control"] = lift
                            
                            # Calculate p-value if we have enough data
                            if include_ci:
                                p_value = self._calculate_p_value(
                                    variant_metrics_data,
                                    control_metrics
                                )
                                variant["metrics"]["conversion_rate"]["p_value"] = p_value
                                variant["metrics"]["conversion_rate"]["is_significant"] = p_value < 0.05
            
            # Add summary statistics
            results["summary"] = await self._calculate_summary(
                experiment_id, variant_metrics, results["variants"]
            )
            
            # Cache results
            await cache_manager.set(cache_key, results, self.cache_ttl)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting experiment results: {e}")
            raise
    
    async def get_funnel_analysis(
        self,
        db: AsyncSession,
        experiment_id: int,
        funnel_steps: List[str]
    ) -> Dict[str, Any]:
        """
        Get funnel analysis using stored procedure.
        
        Args:
            db: Database session
            experiment_id: Experiment ID
            funnel_steps: Ordered list of event types in funnel
        """
        try:
            # Get funnel metrics from stored procedure
            funnel_metrics = await stored_procedure_dao.get_funnel_metrics(
                db=db,
                experiment_id=experiment_id,
                funnel_steps=funnel_steps
            )
            
            # Group by variant
            variants_data = {}
            for metric in funnel_metrics:
                variant_key = metric["variant_key"]
                if variant_key not in variants_data:
                    variants_data[variant_key] = {
                        "variant_key": variant_key,
                        "steps": []
                    }
                
                variants_data[variant_key]["steps"].append({
                    "step": metric["step"],
                    "step_order": metric["step_order"],
                    "users_reached": metric["users_reached"],
                    "conversion_rate": metric["conversion_rate"]
                })
            
            # Calculate overall funnel metrics
            total_users_start = sum(
                v["steps"][0]["users_reached"] 
                for v in variants_data.values() 
                if v["steps"]
            )
            
            total_users_end = sum(
                v["steps"][-1]["users_reached"] 
                for v in variants_data.values() 
                if v["steps"]
            )
            
            overall_conversion = (
                (total_users_end / total_users_start * 100) 
                if total_users_start > 0 
                else 0
            )
            
            return {
                "experiment_id": experiment_id,
                "funnel_steps": funnel_steps,
                "variants": list(variants_data.values()),
                "summary": {
                    "total_users_entered": total_users_start,
                    "total_users_completed": total_users_end,
                    "overall_conversion_rate": round(overall_conversion, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting funnel analysis: {e}")
            raise
    
    async def get_experiment_statistics(
        self,
        db: AsyncSession,
        experiment_id: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive experiment statistics.
        
        Args:
            db: Database session
            experiment_id: Experiment ID
        """
        try:
            # Get stats from stored procedure
            stats = await stored_procedure_dao.get_experiment_stats(
                db=db,
                experiment_id=experiment_id
            )
            
            if not stats:
                return {
                    "experiment_id": experiment_id,
                    "error": "No statistics available"
                }
            
            # Get metrics for statistical power calculation
            metrics = await stored_procedure_dao.get_experiment_metrics(
                db=db,
                experiment_id=experiment_id
            )
            
            # Calculate statistical power if we have control and treatment
            control = next((m for m in metrics if m["is_control"]), None)
            treatment = next((m for m in metrics if not m["is_control"]), None)
            
            if control and treatment:
                power = self._calculate_statistical_power(
                    control["unique_users"],
                    treatment["unique_users"],
                    control["conversion_rate"] / 100,
                    treatment["conversion_rate"] / 100
                )
                stats["statistical_power"] = power
            
            # Add enrollment rate
            if stats["total_users"] > 0:
                stats["enrollment_rate"] = round(
                    stats["enrolled_users"] / stats["total_users"] * 100, 2
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting experiment statistics: {e}")
            raise
    
    def _calculate_confidence_interval(
        self,
        successes: int,
        trials: int,
        confidence_level: float = 0.95
    ) -> tuple:
        """Calculate Wilson score confidence interval."""
        if trials == 0:
            return (0, 0)
        
        p_hat = successes / trials
        z = scipy_stats.norm.ppf((1 + confidence_level) / 2)
        
        denominator = 1 + z**2 / trials
        center = (p_hat + z**2 / (2 * trials)) / denominator
        
        margin = z * math.sqrt(
            (p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials
        ) / denominator
        
        return (
            max(0, (center - margin) * 100),
            min(100, (center + margin) * 100)
        )
    
    def _calculate_lift(self, treatment_rate: float, control_rate: float) -> float:
        """Calculate percentage lift."""
        if control_rate == 0:
            return 0
        return round((treatment_rate - control_rate) / control_rate * 100, 2)
    
    def _calculate_p_value(
        self,
        treatment_metrics: Dict,
        control_metrics: Dict
    ) -> float:
        """Calculate p-value using chi-squared test."""
        # Extract values
        x1 = control_metrics.get("conversion_count", 0)
        n1 = control_metrics.get("unique_users", 0)
        x2 = treatment_metrics.get("conversion_count", 0)
        n2 = treatment_metrics.get("unique_users", 0)
        
        if n1 == 0 or n2 == 0:
            return 1.0
        
        # Pooled probability
        p_pool = (x1 + x2) / (n1 + n2)
        
        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
        
        if se == 0:
            return 1.0
        
        # Z-score
        z = ((x2/n2) - (x1/n1)) / se
        
        # Two-tailed p-value
        p_value = 2 * (1 - scipy_stats.norm.cdf(abs(z)))
        
        return round(p_value, 4)
    
    def _calculate_statistical_power(
        self,
        n1: int,
        n2: int,
        p1: float,
        p2: float,
        alpha: float = 0.05
    ) -> float:
        """Calculate statistical power of the test."""
        if n1 == 0 or n2 == 0 or p1 == p2:
            return 0
        
        # Effect size (Cohen's h)
        h = 2 * (math.asin(math.sqrt(p2)) - math.asin(math.sqrt(p1)))
        
        # Pooled sample size
        n = 2 * n1 * n2 / (n1 + n2)
        
        # Calculate power
        z_alpha = scipy_stats.norm.ppf(1 - alpha/2)
        z_beta = abs(h) * math.sqrt(n/2) - z_alpha
        power = scipy_stats.norm.cdf(z_beta)
        
        return round(power * 100, 2)
    
    async def _calculate_summary(
        self,
        experiment_id: int,
        metrics: List[Dict],
        variants: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate summary statistics."""
        if not variants:
            return {}
        
        # Find best performing variant
        best_variant = max(
            variants,
            key=lambda v: v.get("metrics", {}).get("conversion_rate", {}).get("value", 0)
        )
        
        # Count significant improvements
        significant_improvements = sum(
            1 for v in variants
            if v.get("metrics", {}).get("conversion_rate", {}).get("is_significant", False)
        )
        
        return {
            "total_variants": len(variants),
            "best_variant": best_variant["variant_key"],
            "best_conversion_rate": best_variant["metrics"]["conversion_rate"]["value"],
            "significant_improvements": significant_improvements,
            "recommendation": self._get_recommendation(variants)
        }
    
    def _get_recommendation(self, variants: List[Dict]) -> str:
        """Generate recommendation based on results."""
        significant_winners = [
            v for v in variants
            if not v["is_control"] 
            and v.get("metrics", {}).get("conversion_rate", {}).get("is_significant", False)
            and v.get("metrics", {}).get("conversion_rate", {}).get("lift_vs_control", 0) > 0
        ]
        
        if significant_winners:
            best = max(
                significant_winners,
                key=lambda v: v["metrics"]["conversion_rate"]["value"]
            )
            return f"Deploy {best['variant_key']} - significant improvement detected"
        
        return "Continue experiment - no significant difference detected yet"
    
    def _get_cache_key(
        self,
        experiment_id: int,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        event_types: Optional[List[str]],
        granularity: str
    ) -> str:
        """Generate cache key for results."""
        parts = [
            f"analytics:v1:exp:{experiment_id}",
            f"start:{start_date.isoformat() if start_date else 'none'}",
            f"end:{end_date.isoformat() if end_date else 'none'}",
            f"types:{','.join(event_types) if event_types else 'all'}",
            f"gran:{granularity}"
        ]
        return ":".join(parts)


# Global service instance
analytics_service_v2 = AnalyticsServiceV2()
