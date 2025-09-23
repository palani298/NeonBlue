"""Assignment service with deterministic hashing."""

import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import mmh3
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Experiment, Variant, Assignment,
    ExperimentStatus, OutboxEvent, OutboxEventType
)
from app.core.config import settings
from app.core.cache import cache_manager

logger = logging.getLogger(__name__)


class AssignmentService:
    """Service for managing experiment assignments."""
    
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
        Get or create assignment for user in experiment.
        
        Args:
            db: Database session
            experiment_id: Experiment ID
            user_id: User ID
            force_refresh: Force cache refresh
            enroll: Mark user as enrolled (exposed to experiment)
        """
        # 1. Check cache first (unless force refresh)
        if not force_refresh:
            cache_key = self._get_cache_key(experiment_id, user_id)
            cached = await cache_manager.get(cache_key)
            if cached:
                logger.debug(f"Assignment cache hit: exp={experiment_id}, user={user_id}")
                
                # Handle enrollment if needed
                if enroll and not cached.get("enrolled_at"):
                    await self._mark_enrolled(db, experiment_id, user_id)
                    cached["enrolled_at"] = datetime.now(timezone.utc).isoformat()
                    await cache_manager.set(cache_key, cached, self.cache_ttl)
                
                return cached
        
        # 2. Check database for existing assignment
        result = await db.execute(
            select(Assignment).options(
                selectinload(Assignment.variant),
                selectinload(Assignment.experiment)
            ).where(
                and_(
                    Assignment.experiment_id == experiment_id,
                    Assignment.user_id == user_id
                )
            )
        )
        assignment = result.scalar_one_or_none()
        
        if assignment:
            # Handle enrollment if needed
            if enroll and not assignment.enrolled_at:
                await self._mark_enrolled(db, experiment_id, user_id)
                assignment.enrolled_at = datetime.now(timezone.utc)
            
            # Format and cache
            assignment_dict = self._format_assignment(assignment)
            await cache_manager.set(
                self._get_cache_key(experiment_id, user_id),
                assignment_dict,
                self.cache_ttl
            )
            return assignment_dict
        
        # 3. Create new assignment
        assignment = await self._create_assignment(db, experiment_id, user_id, enroll)
        if assignment:
            assignment_dict = self._format_assignment(assignment)
            await cache_manager.set(
                self._get_cache_key(experiment_id, user_id),
                assignment_dict,
                self.cache_ttl
            )
            return assignment_dict
        
        return None
    
    async def get_bulk_assignments(
        self,
        db: AsyncSession,
        user_id: str,
        experiment_ids: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """Get assignments for one user across multiple experiments."""
        # 1. Bulk fetch from cache
        cache_keys = [self._get_cache_key(exp_id, user_id) for exp_id in experiment_ids]
        cached_results = await cache_manager.mget(cache_keys)
        
        # 2. Process cached results and find misses
        assignments = {}
        missing_experiments = []
        
        for exp_id, cache_key in zip(experiment_ids, cache_keys):
            cached = cached_results.get(cache_key)
            if cached:
                assignments[exp_id] = cached
            else:
                missing_experiments.append(exp_id)
        
        # 3. Bulk fetch/create missing assignments
        if missing_experiments:
            # Fetch existing assignments
            result = await db.execute(
                select(Assignment).options(
                    selectinload(Assignment.variant),
                    selectinload(Assignment.experiment)
                ).where(
                    and_(
                        Assignment.user_id == user_id,
                        Assignment.experiment_id.in_(missing_experiments)
                    )
                )
            )
            existing_assignments = result.scalars().all()
            
            # Process existing assignments
            existing_exp_ids = set()
            cache_updates = {}
            
            for assignment in existing_assignments:
                exp_id = assignment.experiment_id
                existing_exp_ids.add(exp_id)
                assignment_dict = self._format_assignment(assignment)
                assignments[exp_id] = assignment_dict
                cache_updates[self._get_cache_key(exp_id, user_id)] = assignment_dict
            
            # Create new assignments for remaining experiments
            new_experiment_ids = set(missing_experiments) - existing_exp_ids
            if new_experiment_ids:
                for exp_id in new_experiment_ids:
                    assignment = await self._create_assignment(db, exp_id, user_id, False)
                    if assignment:
                        assignment_dict = self._format_assignment(assignment)
                        assignments[exp_id] = assignment_dict
                        cache_updates[self._get_cache_key(exp_id, user_id)] = assignment_dict
            
            # Bulk update cache
            if cache_updates:
                await cache_manager.mset(cache_updates, self.cache_ttl)
        
        return assignments
    
    async def _create_assignment(
        self,
        db: AsyncSession,
        experiment_id: int,
        user_id: str,
        enroll: bool
    ) -> Optional[Assignment]:
        """Create new assignment using deterministic hashing."""
        # Fetch experiment with variants
        result = await db.execute(
            select(Experiment).options(
                selectinload(Experiment.variants)
            ).where(
                and_(
                    Experiment.id == experiment_id,
                    Experiment.status == ExperimentStatus.ACTIVE
                )
            )
        )
        experiment = result.scalar_one_or_none()
        
        if not experiment or not experiment.variants:
            logger.warning(f"Experiment {experiment_id} not found or has no variants")
            return None
        
        # Calculate variant using deterministic hashing
        variant = self._calculate_variant(experiment, user_id)
        if not variant:
            logger.error(f"Failed to calculate variant for exp={experiment_id}, user={user_id}")
            return None
        
        # Create assignment
        now = datetime.now(timezone.utc)
        assignment = Assignment(
            experiment_id=experiment_id,
            user_id=user_id,
            variant_id=variant.id,
            version=experiment.version,
            source="hash",
            assigned_at=now,
            enrolled_at=now if enroll else None
        )
        
        db.add(assignment)
        
        # Add to outbox for CDC
        outbox_event = OutboxEvent(
            aggregate_id=f"{experiment_id}:{user_id}",
            aggregate_type="assignment",
            event_type=OutboxEventType.ASSIGNMENT_CREATED,
            payload={
                "experiment_id": experiment_id,
                "user_id": user_id,
                "variant_id": variant.id,
                "variant_key": variant.key,
                "assigned_at": now.isoformat(),
                "enrolled": enroll
            }
        )
        db.add(outbox_event)
        
        # If enrolling, add enrollment event too
        if enroll:
            enrollment_event = OutboxEvent(
                aggregate_id=f"{experiment_id}:{user_id}",
                aggregate_type="assignment",
                event_type=OutboxEventType.ASSIGNMENT_ENROLLED,
                payload={
                    "experiment_id": experiment_id,
                    "user_id": user_id,
                    "variant_id": variant.id,
                    "enrolled_at": now.isoformat()
                }
            )
            db.add(enrollment_event)
        
        # Commit transaction (assignment + outbox events are atomic)
        await db.commit()
        
        # Reload with relationships
        await db.refresh(assignment, ["variant", "experiment"])
        
        return assignment
    
    async def _mark_enrolled(
        self,
        db: AsyncSession,
        experiment_id: int,
        user_id: str
    ):
        """Mark assignment as enrolled (user exposed to experiment)."""
        result = await db.execute(
            select(Assignment).where(
                and_(
                    Assignment.experiment_id == experiment_id,
                    Assignment.user_id == user_id,
                    Assignment.enrolled_at.is_(None)
                )
            )
        )
        assignment = result.scalar_one_or_none()
        
        if assignment:
            now = datetime.now(timezone.utc)
            assignment.enrolled_at = now
            
            # Add enrollment event to outbox
            outbox_event = OutboxEvent(
                aggregate_id=f"{experiment_id}:{user_id}",
                aggregate_type="assignment",
                event_type=OutboxEventType.ASSIGNMENT_ENROLLED,
                payload={
                    "experiment_id": experiment_id,
                    "user_id": user_id,
                    "variant_id": assignment.variant_id,
                    "enrolled_at": now.isoformat()
                }
            )
            db.add(outbox_event)
            
            await db.commit()
            
            # Invalidate cache
            cache_key = self._get_cache_key(experiment_id, user_id)
            await cache_manager.delete(cache_key)
    
    def _calculate_variant(self, experiment: Experiment, user_id: str) -> Optional[Variant]:
        """Calculate variant using deterministic hashing."""
        # Create hash input
        hash_input = f"{user_id}:{experiment.seed}:{self.hash_seed}"
        
        # Calculate bucket (0 to bucket_size-1)
        bucket = mmh3.hash(hash_input, signed=False) % self.bucket_size
        
        # Sort variants by ID for consistency
        variants = sorted(experiment.variants, key=lambda v: v.id)
        
        # Calculate cumulative allocation ranges
        cumulative = 0
        for variant in variants:
            # Convert percentage to bucket range
            variant_buckets = int(variant.allocation_pct * self.bucket_size / 100)
            cumulative += variant_buckets
            
            if bucket < cumulative:
                return variant
        
        # Fallback to last variant (shouldn't happen with correct allocations)
        return variants[-1] if variants else None
    
    def _format_assignment(self, assignment: Assignment) -> Dict[str, Any]:
        """Format assignment for response."""
        return {
            "experiment_id": assignment.experiment_id,
            "experiment_key": assignment.experiment.key if assignment.experiment else None,
            "user_id": assignment.user_id,
            "variant_id": assignment.variant_id,
            "variant_key": assignment.variant.key if assignment.variant else None,
            "variant_name": assignment.variant.name if assignment.variant else None,
            "is_control": assignment.variant.is_control if assignment.variant else False,
            "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            "enrolled_at": assignment.enrolled_at.isoformat() if assignment.enrolled_at else None,
            "version": assignment.version,
            "source": assignment.source
        }
    
    def _get_cache_key(self, experiment_id: int, user_id: str) -> str:
        """Get cache key for assignment."""
        return f"assignment:{experiment_id}:{user_id}"


# Global assignment service instance
assignment_service = AssignmentService()
