"""Add User model and update relationships

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table('users',
    sa.Column('user_id', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_index('idx_user_active', 'users', ['is_active'], unique=False)
    op.create_index('idx_user_email', 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)

    # Add user_id columns to assignments and events tables
    op.add_column('assignments', sa.Column('user_id', sa.String(length=255), nullable=True))
    op.add_column('events', sa.Column('user_id', sa.String(length=255), nullable=True))
    
    # Create foreign key constraints
    op.create_foreign_key('fk_assignments_user_id', 'assignments', 'users', ['user_id'], ['user_id'])
    op.create_foreign_key('fk_events_user_id', 'events', 'users', ['user_id'], ['user_id'])
    
    # Create indexes
    op.create_index('idx_assignment_user', 'assignments', ['user_id'], unique=False)
    op.create_index('idx_events_user_time', 'events', ['user_id', 'timestamp'], unique=False)
    
    # Update unique constraint for assignments
    op.drop_constraint('uq_assignment_experiment_user', 'assignments', type_='unique')
    op.create_unique_constraint('uq_assignment_experiment_user', 'assignments', ['experiment_id', 'user_id'])


def downgrade():
    # Drop foreign key constraints
    op.drop_constraint('fk_events_user_id', 'events', type_='foreignkey')
    op.drop_constraint('fk_assignments_user_id', 'assignments', type_='foreignkey')
    
    # Drop indexes
    op.drop_index('idx_events_user_time', table_name='events')
    op.drop_index('idx_assignment_user', table_name='assignments')
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_index('idx_user_email', table_name='users')
    op.drop_index('idx_user_active', table_name='users')
    
    # Restore original unique constraint
    op.drop_constraint('uq_assignment_experiment_user', 'assignments', type_='unique')
    op.create_unique_constraint('uq_assignment_experiment_user', 'assignments', ['experiment_id', 'user_id'])
    
    # Drop user_id columns
    op.drop_column('events', 'user_id')
    op.drop_column('assignments', 'user_id')
    
    # Drop users table
    op.drop_table('users')
