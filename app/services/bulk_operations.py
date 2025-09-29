"""True bulk operations using PostgreSQL arrays."""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BulkOperationsService:
    """Service for true bulk operations using PostgreSQL arrays."""
    
    async def create_bulk_experiments(
        self,
        db: AsyncSession,
        experiments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create multiple experiments using PostgreSQL arrays.
        
        Args:
            db: Database session
            experiments: List of experiment dictionaries
            
        Returns:
            Dictionary with created and failed experiments
        """
        if not experiments:
            return {"created": [], "failed": []}
        
        # Prepare arrays
        keys = [exp["key"] for exp in experiments]
        names = [exp["name"] for exp in experiments]
        descriptions = [exp.get("description", "") for exp in experiments]
        statuses = ["DRAFT"] * len(experiments)
        seeds = [f"bulk-{exp['key']}-{i}" for i, exp in enumerate(experiments)]
        versions = [1] * len(experiments)
        configs = [json.dumps(exp.get("config", {})) for exp in experiments]
        
        try:
            # Build VALUES clause for bulk insert
            values_clauses = []
            params = {}
            
            for i, (key, name, description, status, seed, version, config) in enumerate(zip(keys, names, descriptions, statuses, seeds, versions, configs)):
                values_clauses.append(f"(:key_{i}, :name_{i}, :description_{i}, :status_{i}, :seed_{i}, :version_{i}, :config_{i}, now(), now())")
                params.update({
                    f"key_{i}": key,
                    f"name_{i}": name,
                    f"description_{i}": description,
                    f"status_{i}": status,
                    f"seed_{i}": seed,
                    f"version_{i}": version,
                    f"config_{i}": config  # Keep as JSON string for asyncpg
                })
            
            # Single bulk insert using VALUES
            result = await db.execute(text(f"""
                INSERT INTO experiments (key, name, description, status, seed, version, config, created_at, updated_at)
                VALUES {', '.join(values_clauses)}
                RETURNING id, key, name, description, status, seed, version, config, created_at, updated_at
            """), params)
            
            created_experiments = result.fetchall()
            
            # Create variants for each experiment
            await self._create_bulk_variants(db, experiments, created_experiments)
            
            await db.commit()
            
            # Format response to match ExperimentResponse schema
            formatted_experiments = []
            for row in created_experiments:
                exp_dict = dict(row._mapping)
                # Add missing fields for Pydantic validation
                exp_dict.update({
                    "starts_at": None,
                    "ends_at": None,
                    "variants": []  # Will be populated by variants creation
                })
                formatted_experiments.append(exp_dict)
            
            return {
                "created": formatted_experiments,
                "failed": []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk experiment creation failed: {e}")
            return {
                "created": [],
                "failed": [{"error": str(e), "experiments": experiments}]
            }
    
    async def _create_bulk_variants(
        self,
        db: AsyncSession,
        experiments: List[Dict[str, Any]],
        created_experiments: List[Any]
    ) -> None:
        """Create variants for bulk experiments."""
        if not experiments or not created_experiments:
            return
        
        # Prepare variant arrays
        experiment_ids = []
        variant_keys = []
        variant_names = []
        variant_descriptions = []
        allocation_pcts = []
        is_controls = []
        variant_configs = []
        
        for i, exp in enumerate(experiments):
            experiment_id = created_experiments[i].id
            for variant in exp.get("variants", []):
                experiment_ids.append(experiment_id)
                variant_keys.append(variant["key"])
                variant_names.append(variant["name"])
                variant_descriptions.append(variant.get("description", ""))
                allocation_pcts.append(variant["allocation_pct"])
                is_controls.append(variant.get("is_control", False))
                variant_configs.append(json.dumps(variant.get("config", {})))
        
        if experiment_ids:
            # Build VALUES clause for bulk variant insert
            values_clauses = []
            params = {}
            
            for i, (exp_id, key, name, description, allocation_pct, is_control, config) in enumerate(zip(experiment_ids, variant_keys, variant_names, variant_descriptions, allocation_pcts, is_controls, variant_configs)):
                values_clauses.append(f"(:exp_id_{i}, :key_{i}, :name_{i}, :description_{i}, :allocation_pct_{i}, :is_control_{i}, :config_{i}, now(), now())")
                params.update({
                    f"exp_id_{i}": exp_id,
                    f"key_{i}": key,
                    f"name_{i}": name,
                    f"description_{i}": description,
                    f"allocation_pct_{i}": allocation_pct,
                    f"is_control_{i}": is_control,
                    f"config_{i}": config  # Keep as JSON string for asyncpg
                })
            
            await db.execute(text(f"""
                INSERT INTO variants (experiment_id, key, name, description, allocation_pct, is_control, config, created_at, updated_at)
                VALUES {', '.join(values_clauses)}
            """), params)
    
    async def create_bulk_assignments(
        self,
        db: AsyncSession,
        assignments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create multiple assignments using PostgreSQL arrays.
        
        Args:
            db: Database session
            assignments: List of assignment dictionaries
            
        Returns:
            Dictionary with successful and failed assignments
        """
        if not assignments:
            return {"successful": [], "failed": []}
        
        # Prepare arrays
        experiment_ids = [a["experiment_id"] for a in assignments]
        user_ids = [a["user_id"] for a in assignments]
        variant_ids = [a.get("variant_id") for a in assignments]
        sources = [a.get("source", "api") for a in assignments]
        contexts = [json.dumps(a.get("context", {})) for a in assignments]
        
        try:
            # Build VALUES clause for bulk assignment insert
            values_clauses = []
            params = {}
            
            for i, (exp_id, user_id, variant_id, source, context) in enumerate(zip(experiment_ids, user_ids, variant_ids, sources, contexts)):
                values_clauses.append(f"(:exp_id_{i}, :user_id_{i}, :variant_id_{i}, :source_{i}, :context_{i}, now(), now(), now())")
                params.update({
                    f"exp_id_{i}": exp_id,
                    f"user_id_{i}": user_id,
                    f"variant_id_{i}": variant_id,
                    f"source_{i}": source,
                    f"context_{i}": context  # Keep as JSON string for asyncpg
                })
            
            # Single bulk insert with conflict handling
            result = await db.execute(text(f"""
                INSERT INTO assignments (experiment_id, user_id, variant_id, source, context, assigned_at, created_at, updated_at)
                VALUES {', '.join(values_clauses)}
                ON CONFLICT (experiment_id, user_id) DO UPDATE SET
                    variant_id = EXCLUDED.variant_id,
                    source = EXCLUDED.source,
                    context = EXCLUDED.context,
                    updated_at = now()
                RETURNING id, experiment_id, user_id, variant_id, source, assigned_at
            """), params)
            
            successful_assignments = result.fetchall()
            await db.commit()
            
            return {
                "successful": [dict(row._mapping) for row in successful_assignments],
                "failed": []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk assignment creation failed: {e}")
            return {
                "successful": [],
                "failed": [{"error": str(e), "assignments": assignments}]
            }
    
    async def record_bulk_events(
        self,
        db: AsyncSession,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Record multiple events using PostgreSQL arrays.
        
        Args:
            db: Database session
            events: List of event dictionaries
            
        Returns:
            Dictionary with recorded and failed events
        """
        if not events:
            return {"recorded": 0, "failed": 0, "events": [], "errors": []}
        
        # Prepare arrays
        experiment_ids = [e["experiment_id"] for e in events]
        user_ids = [e["user_id"] for e in events]
        event_types = [e["event_type"] for e in events]
        properties = [json.dumps(e.get("properties", {})) for e in events]
        timestamps = [e.get("timestamp", datetime.now(timezone.utc)) for e in events]
        session_ids = [e.get("session_id") for e in events]
        request_ids = [e.get("request_id") for e in events]
        
        try:
            # Build VALUES clause for bulk event insert
            values_clauses = []
            params = {}
            
            for i, (exp_id, user_id, event_type, props, timestamp, session_id, request_id) in enumerate(zip(experiment_ids, user_ids, event_types, properties, timestamps, session_ids, request_ids)):
                values_clauses.append(f"(:exp_id_{i}, :user_id_{i}, :event_type_{i}, :props_{i}, :timestamp_{i}, :session_id_{i}, :request_id_{i}, now(), now())")
                params.update({
                    f"exp_id_{i}": exp_id,
                    f"user_id_{i}": user_id,
                    f"event_type_{i}": event_type,
                    f"props_{i}": props,  # Keep as JSON string for asyncpg
                    f"timestamp_{i}": timestamp,
                    f"session_id_{i}": session_id,
                    f"request_id_{i}": request_id
                })
            
            # Single bulk insert
            result = await db.execute(text(f"""
                INSERT INTO events (experiment_id, user_id, event_type, properties, timestamp, session_id, request_id, created_at, updated_at)
                VALUES {', '.join(values_clauses)}
                RETURNING id, experiment_id, user_id, event_type, timestamp, session_id, request_id
            """), params)
            
            recorded_events = result.fetchall()
            await db.commit()
            
            return {
                "recorded": len(recorded_events),
                "failed": 0,
                "events": [dict(row._mapping) for row in recorded_events],
                "errors": []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk event recording failed: {e}")
            return {
                "recorded": 0,
                "failed": len(events),
                "events": [],
                "errors": [{"error": str(e)}]
            }
    
    async def update_bulk_assignments(
        self,
        db: AsyncSession,
        assignment_ids: List[int],
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update multiple assignments using PostgreSQL arrays.
        
        Args:
            db: Database session
            assignment_ids: List of assignment IDs to update
            updates: Dictionary of fields to update
            
        Returns:
            Dictionary with successful and failed updates
        """
        if not assignment_ids:
            return {"successful": [], "failed": []}
        
        # Build dynamic update query
        update_fields = []
        params = {"assignment_ids": assignment_ids}
        
        if "variant_id" in updates:
            update_fields.append("variant_id = :variant_id")
            params["variant_id"] = updates["variant_id"]
        
        if "source" in updates:
            update_fields.append("source = :source")
            params["source"] = updates["source"]
        
        if "context" in updates:
            update_fields.append("context = :context")
            params["context"] = json.dumps(updates["context"])  # Convert to JSON string for asyncpg
        
        if not update_fields:
            return {"successful": [], "failed": []}
        
        update_fields.append("updated_at = now()")
        
        try:
            result = await db.execute(text(f"""
                UPDATE assignments 
                SET {', '.join(update_fields)}
                WHERE id = ANY(:assignment_ids)
                RETURNING id, experiment_id, user_id, variant_id, source, updated_at
            """), params)
            
            successful_updates = result.fetchall()
            await db.commit()
            
            return {
                "successful": [dict(row._mapping) for row in successful_updates],
                "failed": []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk assignment update failed: {e}")
            return {
                "successful": [],
                "failed": [{"error": str(e), "assignment_ids": assignment_ids}]
            }
    
    async def delete_bulk_assignments(
        self,
        db: AsyncSession,
        assignment_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Delete multiple assignments using PostgreSQL arrays.
        
        Args:
            db: Database session
            assignment_ids: List of assignment IDs to delete
            
        Returns:
            Dictionary with successful and failed deletions
        """
        if not assignment_ids:
            return {"successful": [], "failed": []}
        
        try:
            result = await db.execute(text("""
                DELETE FROM assignments 
                WHERE id = ANY(:assignment_ids)
                RETURNING id, experiment_id, user_id
            """), {"assignment_ids": assignment_ids})
            
            successful_deletions = result.fetchall()
            await db.commit()
            
            return {
                "successful": [dict(row._mapping) for row in successful_deletions],
                "failed": []
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk assignment deletion failed: {e}")
            return {
                "successful": [],
                "failed": [{"error": str(e), "assignment_ids": assignment_ids}]
            }


# Global service instance
bulk_operations_service = BulkOperationsService()
