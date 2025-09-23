"""Database connection and session management."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    str(settings.database_url),
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database."""
    try:
        # Import all models to ensure they're registered
        from app.models import models  # noqa
        from app.models.base import Base
        
        # Create tables
        async with engine.begin() as conn:
            # In production, use Alembic migrations instead
            await conn.run_sync(Base.metadata.create_all)
            
            # Create partitions for events table
            await create_event_partitions(conn)
            
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def create_event_partitions(conn):
    """Create monthly partitions for events table."""
    from datetime import datetime, timedelta
    
    # Create partitions for the next 3 months
    current_date = datetime.now()
    
    for i in range(3):
        partition_date = current_date + timedelta(days=30 * i)
        partition_name = f"events_{partition_date.strftime('%Y_%m')}"
        start_date = partition_date.replace(day=1).strftime('%Y-%m-%d')
        
        # Calculate end date (first day of next month)
        if partition_date.month == 12:
            end_date = partition_date.replace(year=partition_date.year + 1, month=1, day=1)
        else:
            end_date = partition_date.replace(month=partition_date.month + 1, day=1)
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Create partition
        create_partition_sql = f"""
        CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF events
        FOR VALUES FROM ('{start_date}') TO ('{end_date_str}');
        """
        
        try:
            await conn.execute(create_partition_sql)
            logger.info(f"Created partition {partition_name}")
            
            # Create indexes on partition
            index_sqls = [
                f"CREATE INDEX IF NOT EXISTS idx_{partition_name}_exp_time ON {partition_name} (experiment_id, timestamp);",
                f"CREATE INDEX IF NOT EXISTS idx_{partition_name}_user_time ON {partition_name} (user_id, timestamp);",
                f"CREATE INDEX IF NOT EXISTS idx_{partition_name}_type_time ON {partition_name} (event_type, timestamp);",
                f"CREATE INDEX IF NOT EXISTS idx_{partition_name}_props ON {partition_name} USING gin (properties);"
            ]
            
            for index_sql in index_sqls:
                await conn.execute(index_sql)
                
        except Exception as e:
            logger.warning(f"Failed to create partition {partition_name}: {e}")


async def close_db():
    """Close database connection."""
    await engine.dispose()
    logger.info("Database connection closed")
