"""Create all tables

Revision ID: 003
Revises: 002
Create Date: 2025-09-24 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create experiments table
    op.create_table('experiments',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'ACTIVE', 'PAUSED', 'ARCHIVED', name='experimentstatus'), nullable=False),
        sa.Column('seed', sa.String(length=255), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index('idx_experiment_status', 'experiments', ['status'], unique=False)
    op.create_index('idx_experiment_key', 'experiments', ['key'], unique=False)

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
    op.create_index('idx_user_email', 'users', ['email'], unique=False)

    # Create variants table
    op.create_table('variants',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('experiment_id', sa.BigInteger(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('allocation_pct', sa.Integer(), nullable=False),
        sa.Column('is_control', sa.Boolean(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', 'key')
    )
    op.create_index('idx_variant_experiment', 'variants', ['experiment_id'], unique=False)

    # Create assignments table
    op.create_table('assignments',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('experiment_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', 'user_id')
    )
    op.create_index('idx_assignment_experiment', 'assignments', ['experiment_id'], unique=False)
    op.create_index('idx_assignment_user', 'assignments', ['user_id'], unique=False)
    op.create_index('idx_assignment_variant', 'assignments', ['variant_id'], unique=False)
    op.create_index('idx_assignment_time', 'assignments', ['assigned_at'], unique=False)
    op.create_index('idx_assignment_enrolled', 'assignments', ['enrolled_at'], unique=False)

    # Create events table
    op.create_table('events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('experiment_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('variant_id', sa.BigInteger(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assignment_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', 'timestamp')
    )
    op.create_index('idx_events_experiment_time', 'events', ['experiment_id', 'timestamp'], unique=False)
    op.create_index('idx_events_user_time', 'events', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_events_type_time', 'events', ['event_type', 'timestamp'], unique=False)
    op.create_index('idx_events_properties', 'events', ['properties'], unique=False, postgresql_using='gin')

    # Create api_tokens table
    op.create_table('api_tokens',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rate_limit', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('idx_api_token_active', 'api_tokens', ['is_active'], unique=False)
    op.create_index('idx_api_token_expires', 'api_tokens', ['expires_at'], unique=False)


def downgrade():
    op.drop_table('api_tokens')
    op.drop_table('events')
    op.drop_table('assignments')
    op.drop_table('variants')
    op.drop_table('users')
    op.drop_table('experiments')
    op.execute('DROP TYPE IF EXISTS experimentstatus')
