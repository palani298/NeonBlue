"""Add stored procedures for experimentation platform

Revision ID: 001
Revises: 
Create Date: 2025-09-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create all stored procedures."""
    
    # Read the stored procedures SQL file
    with open('/workspace/init/postgres/02_stored_procedures.sql', 'r') as f:
        sql_content = f.read()
    
    # Execute the SQL to create stored procedures
    connection = op.get_bind()
    connection.execute(text(sql_content))
    
    print("✅ Created stored procedures for:")
    print("  - Experiments (create, get, list, activate)")
    print("  - Assignments (get_or_create, bulk_get)")
    print("  - Events (record, batch_record)")
    print("  - Analytics (metrics, daily, funnel, stats)")
    print("  - Utilities (cleanup, stats)")


def downgrade():
    """Drop all stored procedures."""
    
    connection = op.get_bind()
    
    # Drop all functions (stored procedures)
    procedures_to_drop = [
        # Experiment procedures
        'create_experiment',
        'get_experiment_with_variants',
        'list_active_experiments',
        'activate_experiment',
        
        # Assignment procedures
        'get_or_create_assignment',
        'get_bulk_assignments',
        
        # Event procedures
        'record_event',
        'record_batch_events',
        
        # Analytics procedures
        'get_experiment_metrics',
        'get_daily_metrics',
        'get_funnel_metrics',
        'get_experiment_stats',
        
        # Utility procedures
        'cleanup_old_events'
    ]
    
    for proc_name in procedures_to_drop:
        try:
            # PostgreSQL requires CASCADE to drop functions that might have dependencies
            connection.execute(text(f"DROP FUNCTION IF EXISTS {proc_name} CASCADE"))
            print(f"  ✅ Dropped {proc_name}")
        except Exception as e:
            print(f"  ⚠️  Could not drop {proc_name}: {e}")
    
    print("✅ Dropped all stored procedures")