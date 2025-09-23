"""Demo script showing how to use stored procedure-based services."""

import asyncio
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.services.assignment_v2 import assignment_service_v2
from app.services.events_v2 import event_service_v2
from app.services.analytics_v2 import analytics_service_v2
from app.core.stored_procedures import stored_procedure_dao


async def demo_stored_procedures():
    """Demonstrate using stored procedures for all operations."""
    
    # Create async engine
    engine = create_async_engine(
        str(settings.database_url),
        echo=True,  # Enable SQL logging
        future=True
    )
    
    # Create session factory
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as db:
        print("\n" + "="*60)
        print("STORED PROCEDURES DEMO")
        print("="*60)
        
        # 1. Create experiment using stored procedure
        print("\n1. Creating experiment with stored procedure...")
        
        experiment_data = await stored_procedure_dao.create_experiment(
            db=db,
            key="sp_demo_experiment",
            name="Stored Procedure Demo",
            description="Testing stored procedures implementation",
            variants=[
                {
                    "key": "control",
                    "name": "Control Group",
                    "allocation_pct": 50,
                    "is_control": True,
                    "config": {}
                },
                {
                    "key": "treatment",
                    "name": "Treatment Group",
                    "allocation_pct": 50,
                    "is_control": False,
                    "config": {"feature": "enabled"}
                }
            ],
            status="draft"
        )
        
        experiment_id = experiment_data["id"]
        print(f"✅ Created experiment {experiment_id}")
        print(json.dumps(experiment_data, indent=2, default=str))
        
        # 2. Activate experiment
        print("\n2. Activating experiment...")
        success, message, new_version = await stored_procedure_dao.activate_experiment(
            db, experiment_id
        )
        print(f"✅ {message} (version: {new_version})")
        
        # 3. Get experiment with variants
        print("\n3. Getting experiment with variants...")
        experiment = await stored_procedure_dao.get_experiment_with_variants(
            db, experiment_id
        )
        print(f"Experiment: {experiment['name']}")
        print(f"Status: {experiment['status']}")
        print(f"Variants: {len(experiment['variants'])}")
        
        # 4. Get assignment using service (which uses stored procedure internally)
        print("\n4. Getting user assignment...")
        assignment = await assignment_service_v2.get_assignment(
            db=db,
            experiment_id=experiment_id,
            user_id="demo_user_123",
            enroll=True
        )
        print(f"✅ User assigned to: {assignment['variant_key']}")
        print(json.dumps(assignment, indent=2, default=str))
        
        # 5. Record event using stored procedure
        print("\n5. Recording event...")
        event_result = await stored_procedure_dao.record_event(
            db=db,
            experiment_id=experiment_id,
            user_id="demo_user_123",
            event_type="click",
            properties={"button": "cta", "page": "homepage"},
            value=None
        )
        print(f"✅ Event recorded: {event_result['id']}")
        
        # 6. Record batch events
        print("\n6. Recording batch events...")
        batch_events = [
            {
                "experiment_id": experiment_id,
                "user_id": f"user_{i}",
                "event_type": "conversion" if i % 3 == 0 else "click",
                "properties": {"source": "demo"},
                "value": 10.0 if i % 3 == 0 else None
            }
            for i in range(10)
        ]
        
        batch_result = await stored_procedure_dao.record_batch_events(
            db, batch_events
        )
        print(f"✅ Batch result: {batch_result['success_count']} success, {batch_result['error_count']} errors")
        
        # 7. Get experiment metrics
        print("\n7. Getting experiment metrics...")
        metrics = await stored_procedure_dao.get_experiment_metrics(
            db=db,
            experiment_id=experiment_id,
            start_date=None,
            end_date=None,
            event_types=None
        )
        
        for variant in metrics:
            print(f"\nVariant: {variant['variant_key']}")
            print(f"  Users: {variant['unique_users']}")
            print(f"  Events: {variant['total_events']}")
            print(f"  Conversions: {variant['conversion_count']}")
            print(f"  Conversion Rate: {variant['conversion_rate']}%")
        
        # 8. Get daily metrics
        print("\n8. Getting daily metrics...")
        daily_metrics = await stored_procedure_dao.get_daily_metrics(
            db, experiment_id, days=7
        )
        
        for metric in daily_metrics[:3]:  # Show first 3 days
            print(f"Date: {metric['date']}, Variant: {metric['variant_key']}, "
                  f"Users: {metric['unique_users']}, Events: {metric['total_events']}")
        
        # 9. Get experiment statistics
        print("\n9. Getting experiment statistics...")
        stats = await stored_procedure_dao.get_experiment_stats(
            db, experiment_id
        )
        print(f"Total Users: {stats['total_users']}")
        print(f"Enrolled Users: {stats['enrolled_users']}")
        print(f"Total Events: {stats['total_events']}")
        print(f"Avg Events/User: {stats['avg_events_per_user']}")
        
        # 10. Funnel analysis
        print("\n10. Performing funnel analysis...")
        funnel_steps = ["pageview", "click", "conversion"]
        funnel_metrics = await stored_procedure_dao.get_funnel_metrics(
            db, experiment_id, funnel_steps
        )
        
        for metric in funnel_metrics:
            print(f"Variant: {metric['variant_key']}, Step: {metric['step']}, "
                  f"Users: {metric['users_reached']}, Rate: {metric['conversion_rate']}%")
        
        # 11. Using analytics service (wraps stored procedures)
        print("\n11. Getting comprehensive analytics...")
        results = await analytics_service_v2.get_experiment_results(
            db=db,
            experiment_id=experiment_id,
            include_ci=True,
            min_sample=1  # Low for demo
        )
        
        print(f"Summary: {results['summary']}")
        
        # Commit all changes
        await db.commit()
        
        print("\n" + "="*60)
        print("✅ DEMO COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Benefits of Stored Procedures:")
        print("1. ⚡ Better performance - operations happen in the database")
        print("2. 🔒 Enhanced security - no direct table access needed")
        print("3. 🎯 Atomic operations - complex logic in single transaction")
        print("4. 📊 Centralized business logic - easier to maintain")
        print("5. 🔄 Reduced network traffic - fewer round trips")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(demo_stored_procedures())