"""Assignment service using stored procedures."""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import mmh3

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cache import cache_manager
from app.core.stored_procedures import stored_procedure_dao
from app.models.models import Experiment, ExperimentStatus

logger = logging.getLogger(__name__)


class AssignmentServiceV2:
    """Service for managing experiment assignments using stored procedures."""
    
    def __init__(self):
        self.bucket_size = settings.assignment_bucket_size
        self.cache_ttl = settings.assignment_cache_ttl
        self.hash_seed = settings.assignment_hash_seed
    
    async def get_assignment(
        self,
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        force_refresh: bool = False,
        enroll: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get or create assignment for user in experiment using stored procedure.
        
        Args:
            db: Database session
            experiment_id: Experiment ID
            user_id: User ID
            force_refresh: Force cache refresh
            enroll: Mark user as enrolled
        """
        # 1. Check cache first (unless force refresh)
        cache_key = self._get_cache_key(experiment_id, user_id)
        
        if not force_refresh:
            cached = await cache_manager.get(cache_key)
            if cached:
                logger.debug(f"Assignment cache hit: exp={experiment_id}, user={user_id}")
                
                # Handle enrollment if needed and not already enrolled
                if enroll and not cached.get("enrolled_at"):
                    # Need to update enrollment in DB
                    assignment = await stored_procedure_dao.get_or_create_assignment(
                        db, experiment_id, user_id, enroll=True
                    )
                    
                    # Update cache with enrollment
                    cached["enrolled_at"] = assignment["enrolled_at"]
                    cached["enrolled"] = True
                    await cache_manager.set(cache_key, cached, self.cache_ttl)
                
                return cached
        
        # 2. Get experiment to check if active
        experiment = await self._get_experiment(db, experiment_id)
        if not experiment or experiment["status"].lower() != "active":
            logger.warning(f"Experiment {experiment_id} not found or not active")
            return None
        
        # 3. Calculate variant for user (deterministic)
        variant_key = self._calculate_variant_key(experiment, user_id)
        if not variant_key:
            logger.error(f"Failed to calculate variant for user {user_id} in experiment {experiment_id}")
            return None
        
        # 4. Check if user exists first
        user_exists = await self._check_user_exists(db, user_id)
        if not user_exists:
            logger.warning(f"User {user_id} does not exist")
            return None
        
        # 5. Get or create assignment using stored procedure
        try:
            assignment = await stored_procedure_dao.get_or_create_assignment(
                db, experiment_id, user_id, enroll
            )
            
            # Format response
            # Find the variant to get is_control
            variant = next((v for v in experiment["variants"] if v["id"] == assignment["variant_id"]), None)
            is_control = variant["is_control"] if variant else False
            
            result = {
                "experiment_id": experiment_id,
                "experiment_key": experiment["key"],
                "user_id": user_id,
                "variant_id": assignment["variant_id"],
                "variant_key": assignment["variant_key"],
                "variant_name": assignment["variant_name"],
                "is_control": is_control,
                "assigned_at": assignment["created_at"].isoformat() if assignment["created_at"] else None,
                "enrolled_at": assignment["enrolled_at"].isoformat() if assignment["enrolled_at"] else None,
                "version": experiment["version"],
                "source": "api"
            }
            
            # Cache the result
            await cache_manager.set(cache_key, result, self.cache_ttl)
            
            # Commit transaction
            await db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting/creating assignment: {e}")
            await db.rollback()
            raise
    
    async def get_bulk_assignments(
        self,
        db: AsyncSession,
        user_id: str,
        experiment_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Get assignments for multiple experiments using stored procedures.
        
        Args:
            db: Database session
            user_id: User ID
            experiment_ids: List of experiment IDs
        """
        # 1. Check cache for all experiments
        cache_keys = [self._get_cache_key(exp_id, user_id) for exp_id in experiment_ids]
        cached_results = await cache_manager.mget(cache_keys)
        
        # 2. Process cached results and find misses
        assignments = {}
        missing_experiments = []
        
        for exp_id, cache_key in zip(experiment_ids, cache_keys):
            if cache_key in cached_results:
                assignments[exp_id] = cached_results[cache_key]
            else:
                missing_experiments.append(exp_id)
        
        if not missing_experiments:
            return {"assignments": list(assignments.values())}
        
        # 3. Get existing assignments from DB using stored procedure
        try:
            db_assignments = await stored_procedure_dao.get_bulk_assignments(
                db, user_id, missing_experiments
            )
            
            # Process existing assignments
            existing_exp_ids = set()
            cache_updates = {}
            
            for assignment in db_assignments:
                exp_id = assignment["experiment_id"]
                existing_exp_ids.add(exp_id)
                
                # Get experiment details for formatting
                experiment = await self._get_experiment(db, exp_id)
                if experiment:
                    formatted = {
                        "experiment_id": exp_id,
                        "experiment_key": experiment["key"],
                        "user_id": user_id,
                        "variant_id": assignment["variant_id"],
                        "variant_key": assignment["variant_key"],
                        "variant_name": assignment["variant_name"],
                        "enrolled": assignment["enrolled_at"] is not None,
                        "enrolled_at": assignment["enrolled_at"].isoformat() if assignment["enrolled_at"] else None,
                        "created_at": assignment["created_at"].isoformat() if assignment["created_at"] else None,
                        "version": experiment["version"]
                    }
                    assignments[exp_id] = formatted
                    cache_updates[self._get_cache_key(exp_id, user_id)] = formatted
            
            # 4. Create new assignments for experiments without existing ones
            new_experiment_ids = set(missing_experiments) - existing_exp_ids
            
            for exp_id in new_experiment_ids:
                experiment = await self._get_experiment(db, exp_id)
                if experiment and experiment["status"].lower() == "active":
                    variant_key = self._calculate_variant_key(experiment, user_id)
                    
                    if variant_key:
                        assignment = await stored_procedure_dao.get_or_create_assignment(
                            db, exp_id, user_id, variant_key, enroll=False
                        )
                        
                        formatted = {
                            "experiment_id": exp_id,
                            "experiment_key": experiment["key"],
                            "user_id": user_id,
                            "variant_id": assignment["variant_id"],
                            "variant_key": assignment["variant_key"],
                            "variant_name": assignment["variant_name"],
                            "enrolled": False,
                            "enrolled_at": None,
                            "created_at": assignment["created_at"].isoformat() if assignment["created_at"] else None,
                            "version": experiment["version"]
                        }
                        assignments[exp_id] = formatted
                        cache_updates[self._get_cache_key(exp_id, user_id)] = formatted
            
            # 5. Bulk update cache
            if cache_updates:
                await cache_manager.mset(cache_updates, self.cache_ttl)
            
            # Commit transaction
            await db.commit()
            
            return {"assignments": list(assignments.values())}
            
        except Exception as e:
            logger.error(f"Error getting bulk assignments: {e}")
            await db.rollback()
            raise
    
    async def invalidate_assignment_cache(
        self,
        experiment_id: int,
        user_id: Optional[str] = None
    ):
        """Invalidate assignment cache."""
        if user_id:
            # Invalidate specific assignment
            cache_key = self._get_cache_key(experiment_id, user_id)
            await cache_manager.delete(cache_key)
        else:
            # Invalidate all assignments for experiment
            pattern = f"assignment:v1:exp:{experiment_id}:*"
            count = await cache_manager.invalidate_pattern(pattern)
            logger.info(f"Invalidated {count} assignment cache entries for experiment {experiment_id}")
    
    async def _get_experiment(
        self,
        db: AsyncSession,
        experiment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get experiment with variants using stored procedure."""
        return await stored_procedure_dao.get_experiment_with_variants(db, experiment_id)
    
    async def _check_user_exists(
        self,
        db: AsyncSession,
        user_id: str
    ) -> bool:
        """Check if user exists in the database."""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text("SELECT 1 FROM users WHERE user_id = :user_id LIMIT 1"),
                {"user_id": user_id}
            )
            return result.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False
    
    def _calculate_variant_key(
        self,
        experiment: Dict[str, Any],
        user_id: str
    ) -> Optional[str]:
        """Calculate variant key using deterministic hashing."""
        variants = experiment.get("variants", [])
        if not variants:
            return None
        
        # Create hash input
        hash_input = f"{experiment['id']}:{user_id}:{experiment.get('seed', self.hash_seed)}"
        
        # Generate hash value
        hash_value = mmh3.hash(hash_input, signed=False)
        
        # Map to bucket (0-9999)
        bucket = hash_value % self.bucket_size
        
        # Map bucket to variant based on allocation
        cumulative_allocation = 0
        for variant in variants:
            allocation_pct = variant.get("allocation_pct", 0)
            cumulative_allocation += allocation_pct
            
            # Convert percentage to bucket range
            threshold = (cumulative_allocation / 100.0) * self.bucket_size
            
            if bucket < threshold:
                return variant["key"]
        
        # Fallback to last variant (shouldn't happen with valid allocations)
        return variants[-1]["key"] if variants else None
    
    def _get_cache_key(self, experiment_id: int, user_id: str) -> str:
        """Get cache key for assignment with API versioning."""
        return f"assignment:v1:exp:{experiment_id}:user:{user_id}"


# Global service instance
assignment_service_v2 = AssignmentServiceV2()
