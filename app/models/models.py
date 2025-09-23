"""Database models for experimentation platform."""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean,
    DateTime, ForeignKey, UniqueConstraint, Index, Text,
    CheckConstraint, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.models.base import Base, TimestampMixin


class ExperimentStatus(str, enum.Enum):
    """Experiment status enum."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class EventType(str, enum.Enum):
    """Event type enum."""
    ASSIGNMENT = "assignment"
    EXPOSURE = "exposure"
    CLICK = "click"
    CONVERSION = "conversion"
    PURCHASE = "purchase"
    CUSTOM = "custom"


class OutboxEventType(str, enum.Enum):
    """Outbox event types for CDC."""
    EVENT_CREATED = "event.created"
    ASSIGNMENT_CREATED = "assignment.created"
    ASSIGNMENT_ENROLLED = "assignment.enrolled"


class Experiment(Base, TimestampMixin):
    """Experiment model."""
    
    __tablename__ = "experiments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        SQLEnum(ExperimentStatus),
        default=ExperimentStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # Experiment configuration
    seed = Column(String(255), nullable=False)  # For deterministic hashing
    version = Column(Integer, default=1, nullable=False)
    config = Column(JSONB, default={}, nullable=False)  # Additional settings
    
    # Timing
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    variants = relationship("Variant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="experiment")
    
    # Indexes
    __table_args__ = (
        Index("idx_experiment_status_dates", "status", "starts_at", "ends_at"),
    )


class Variant(Base, TimestampMixin):
    """Variant model."""
    
    __tablename__ = "variants"
    
    id = Column(BigInteger, primary_key=True, index=True)
    experiment_id = Column(
        BigInteger,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False
    )
    key = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Allocation
    allocation_pct = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Percentage allocation (0-100)"
    )
    is_control = Column(Boolean, default=False, nullable=False)
    
    # Configuration
    config = Column(JSONB, default={}, nullable=False)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="variants")
    assignments = relationship("Assignment", back_populates="variant")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("experiment_id", "key", name="uq_variant_experiment_key"),
        CheckConstraint("allocation_pct >= 0 AND allocation_pct <= 100", name="ck_allocation_pct"),
        Index("idx_variant_experiment", "experiment_id"),
    )


class Assignment(Base, TimestampMixin):
    """User assignment to experiment variant."""
    
    __tablename__ = "assignments"
    
    id = Column(BigInteger, primary_key=True, index=True)
    experiment_id = Column(
        BigInteger,
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(String(255), nullable=False)
    variant_id = Column(
        BigInteger,
        ForeignKey("variants.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Assignment metadata
    version = Column(Integer, nullable=False, comment="Experiment version at assignment")
    source = Column(
        String(50),
        default="hash",
        nullable=False,
        comment="Assignment source: hash, override, forced"
    )
    context = Column(JSONB, default={}, nullable=False, comment="Assignment context")
    
    # Timing
    assigned_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    enrolled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When user was actually exposed to the experiment"
    )
    
    # Relationships
    experiment = relationship("Experiment", back_populates="assignments")
    variant = relationship("Variant", back_populates="assignments")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("experiment_id", "user_id", name="uq_assignment_experiment_user"),
        Index("idx_assignment_user", "user_id"),
        Index("idx_assignment_lookup", "experiment_id", "user_id"),
        Index("idx_assignment_time", "assigned_at"),
        Index("idx_assignment_enrolled", "enrolled_at"),
    )


class Event(Base):
    """Event model - partitioned by timestamp."""
    
    __tablename__ = "events"
    __table_args__ = (
        # Define partitioning
        {"postgresql_partition_by": "RANGE (timestamp)"},
        Index("idx_events_experiment_time", "experiment_id", "timestamp"),
        Index("idx_events_user_time", "user_id", "timestamp"),
        Index("idx_events_type_time", "event_type", "timestamp"),
        Index("idx_events_properties", "properties", postgresql_using="gin"),
    )
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    
    # Core fields
    experiment_id = Column(BigInteger, nullable=False)
    user_id = Column(String(255), nullable=False)
    variant_id = Column(BigInteger, nullable=True)
    event_type = Column(String(50), nullable=False)
    
    # Timestamps
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        primary_key=True  # Part of composite PK for partitioning
    )
    assignment_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Denormalized assignment timestamp for efficient filtering"
    )
    
    # Event data
    properties = Column(JSONB, default={}, nullable=False)
    
    # Metadata
    session_id = Column(String(255), nullable=True)
    request_id = Column(String(255), nullable=True)


class OutboxEvent(Base):
    """Transactional outbox for CDC events."""
    
    __tablename__ = "outbox_events"
    
    id = Column(BigInteger, primary_key=True, index=True)
    aggregate_id = Column(String(255), nullable=False, comment="Entity ID (experiment_id, user_id, etc)")
    aggregate_type = Column(String(50), nullable=False, comment="Entity type (experiment, assignment, event)")
    event_type = Column(
        SQLEnum(OutboxEventType),
        nullable=False,
        comment="Type of domain event"
    )
    
    # Event payload
    payload = Column(JSONB, nullable=False, comment="Full event data")
    
    # Processing metadata
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Indexes for efficient polling
    __table_args__ = (
        Index("idx_outbox_unprocessed", "processed_at", "created_at"),
        Index("idx_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )


class ApiToken(Base, TimestampMixin):
    """API tokens for bearer authentication."""
    
    __tablename__ = "api_tokens"
    
    id = Column(BigInteger, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Token metadata
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Permissions (could be expanded)
    scopes = Column(JSONB, default=[], nullable=False)
    
    # Rate limiting per token
    rate_limit = Column(Integer, nullable=True, comment="Requests per minute")
    
    __table_args__ = (
        Index("idx_token_active", "is_active", "expires_at"),
    )
