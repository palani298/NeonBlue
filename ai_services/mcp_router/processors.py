# Data Processors - Destination-specific data handlers
"""
Data processors handle the actual routing and storage of data to specific destinations:

1. PostgreSQLProcessor - Operational data storage and CRUD operations
2. ClickHouseProcessor - Analytics data and time-series storage
3. ChromaDBProcessor - Vector embeddings and semantic search data
4. RedisProcessor - Cache and session data with cache-aside pattern

Each processor optimizes data format and storage patterns for its target system.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import traceback
from abc import ABC, abstractmethod

import asyncpg
import clickhouse_connect
import redis.asyncio as redis
from structlog import get_logger

from ..core.config import config
from ..core.chromadb_manager import vector_store
from .redis_processor import RedisProcessor


logger = get_logger(__name__)


class BaseProcessor(ABC):
    """Base class for all data processors"""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.connection = None
        self.stats = {
            'processed_count': 0,
            'error_count': 0,
            'last_processed': None,
            'last_error': None
        }
    
    @abstractmethod
    async def initialize(self):
        """Initialize the processor and its connections"""
        pass
    
    @abstractmethod
    async def process_data(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Process and store data"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check processor health"""
        pass
    
    async def shutdown(self):
        """Clean shutdown of processor"""
        if self.connection:
            try:
                await self.connection.close()
            except Exception as e:
                logger.warning(f"Error closing {self.name} connection", error=str(e))
        
        logger.info(f"{self.name} processor shutdown complete")
    
    def _update_stats(self, success: bool, error: Optional[str] = None):
        """Update processor statistics"""
        if success:
            self.stats['processed_count'] += 1
            self.stats['last_processed'] = datetime.utcnow().isoformat()
        else:
            self.stats['error_count'] += 1
            self.stats['last_error'] = error
    
    def _transform_for_storage(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Base transformation for storage - can be overridden"""
        return {
            **data,
            'mcp_routing_id': routing_task.get('routing_id'),
            'mcp_processed_at': datetime.utcnow().isoformat(),
            'mcp_classification': routing_task.get('classification', {}),
            'mcp_source': routing_task.get('source', 'unknown')
        }
    
    def _generate_cache_key(self, data: Dict[str, Any], data_type: str, routing_task: Dict[str, Any]) -> str:
        """Generate cache key for cache-aside pattern"""
        routing_id = routing_task.get('routing_id', 'unknown')
        
        if data_type == 'experiment':
            experiment_id = data.get('experiment_id', 'unknown')
            return f"{self.name.lower()}:experiment:{experiment_id}"
            
        elif data_type == 'assignment':
            experiment_id = data.get('experiment_id', 'unknown')
            user_id = data.get('user_id', 'unknown')
            return f"{self.name.lower()}:assignment:{experiment_id}:{user_id}"
            
        elif data_type == 'user_data':
            user_id = data.get('user_id', 'unknown')
            return f"{self.name.lower()}:user:{user_id}:profile"
            
        elif data_type == 'event':
            experiment_id = data.get('experiment_id', 'unknown')
            variant_id = data.get('variant_id', 'unknown')
            event_type = data.get('event_type', 'unknown')
            hour = datetime.utcnow().strftime("%Y%m%d%H")
            return f"{self.name.lower()}:metrics:{experiment_id}:{variant_id}:{event_type}:{hour}"
            
        else:
            return f"{self.name.lower()}:{data_type}:{routing_id}"


class PostgreSQLProcessor(BaseProcessor):
    """
    PostgreSQL processor for operational data
    
    Handles:
    - User data and profiles
    - Experiment configurations
    - Assignment records
    - Operational metadata
    """
    
    def __init__(self):
        super().__init__("PostgreSQL")
        self.connection_pool = None
    
    async def initialize(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.connection_pool = await asyncpg.create_pool(
                config.database_url,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            
            self.initialized = True
            logger.info("PostgreSQL processor initialized", database_url=config.database_url.split('@')[1])
            
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL processor", error=str(e))
            raise
    
    async def process_data(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data for PostgreSQL storage"""
        try:
            classification = routing_task.get('classification', {})
            data_type = classification.get('data_type')
            
            # Transform data for storage
            transformed_data = self._transform_for_storage(data, routing_task)
            
            # Route to appropriate table/handler based on data type
            if data_type == 'experiment':
                result = await self._store_experiment_data(transformed_data)
            elif data_type == 'assignment':
                result = await self._store_assignment_data(transformed_data)
            elif data_type == 'user_data':
                result = await self._store_user_data(transformed_data)
            elif data_type == 'event':
                result = await self._store_event_data(transformed_data)
            else:
                # Generic storage for unknown types
                result = await self._store_generic_data(transformed_data, data_type)
            
            self._update_stats(True)
            
            logger.info("PostgreSQL processing completed", 
                       data_type=data_type,
                       routing_id=routing_task.get('routing_id'),
                       result_id=result.get('id'))
            
            return result
            
        except Exception as e:
            error_msg = f"PostgreSQL processing failed: {str(e)}"
            self._update_stats(False, error_msg)
            logger.error("PostgreSQL processing failed", 
                        error=str(e),
                        routing_id=routing_task.get('routing_id'),
                        traceback=traceback.format_exc())
            raise
    
    async def _store_experiment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store experiment data in experiments table"""
        async with self.connection_pool.acquire() as conn:
            # Upsert experiment record
            query = """
                INSERT INTO experiments (
                    experiment_id, name, hypothesis, type, status, 
                    created_at, updated_at, configuration, mcp_metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                ) ON CONFLICT (experiment_id) 
                DO UPDATE SET
                    updated_at = $7,
                    configuration = $8,
                    mcp_metadata = $9
                RETURNING id, experiment_id
            """
            
            mcp_metadata = {
                'routing_id': data.get('mcp_routing_id'),
                'processed_at': data.get('mcp_processed_at'),
                'classification': data.get('mcp_classification')
            }
            
            result = await conn.fetchrow(
                query,
                data.get('experiment_id'),
                data.get('name'),
                data.get('hypothesis'),
                data.get('type', 'unknown'),
                data.get('status', 'draft'),
                data.get('created_at', datetime.utcnow()),
                datetime.utcnow(),
                json.dumps(data.get('configuration', {})),
                json.dumps(mcp_metadata)
            )
            
            return {'id': result['id'], 'experiment_id': result['experiment_id']}
    
    async def _store_assignment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store assignment data in assignments table"""
        async with self.connection_pool.acquire() as conn:
            query = """
                INSERT INTO assignments (
                    assignment_id, user_id, experiment_id, variant_id,
                    assigned_at, mcp_metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (assignment_id)
                DO UPDATE SET mcp_metadata = $6
                RETURNING id, assignment_id
            """
            
            mcp_metadata = {
                'routing_id': data.get('mcp_routing_id'),
                'processed_at': data.get('mcp_processed_at'),
                'classification': data.get('mcp_classification')
            }
            
            result = await conn.fetchrow(
                query,
                data.get('assignment_id'),
                data.get('user_id'),
                data.get('experiment_id'),
                data.get('variant_id'),
                data.get('assigned_at', datetime.utcnow()),
                json.dumps(mcp_metadata)
            )
            
            return {'id': result['id'], 'assignment_id': result['assignment_id']}
    
    async def _store_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store user data in users table"""
        async with self.connection_pool.acquire() as conn:
            query = """
                INSERT INTO users (
                    user_id, profile_data, preferences, segment,
                    created_at, updated_at, mcp_metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    profile_data = $2,
                    preferences = $3,
                    segment = $4,
                    updated_at = $6,
                    mcp_metadata = $7
                RETURNING id, user_id
            """
            
            mcp_metadata = {
                'routing_id': data.get('mcp_routing_id'),
                'processed_at': data.get('mcp_processed_at'),
                'classification': data.get('mcp_classification')
            }
            
            result = await conn.fetchrow(
                query,
                data.get('user_id'),
                json.dumps(data.get('profile_data', {})),
                json.dumps(data.get('preferences', {})),
                data.get('segment', 'unknown'),
                data.get('created_at', datetime.utcnow()),
                datetime.utcnow(),
                json.dumps(mcp_metadata)
            )
            
            return {'id': result['id'], 'user_id': result['user_id']}
    
    async def _store_event_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store event data in events table"""
        async with self.connection_pool.acquire() as conn:
            query = """
                INSERT INTO events (
                    event_id, user_id, event_type, properties,
                    timestamp, mcp_metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, event_id
            """
            
            mcp_metadata = {
                'routing_id': data.get('mcp_routing_id'),
                'processed_at': data.get('mcp_processed_at'),
                'classification': data.get('mcp_classification')
            }
            
            result = await conn.fetchrow(
                query,
                data.get('event_id', f"event_{datetime.utcnow().isoformat()}"),
                data.get('user_id'),
                data.get('event_type'),
                json.dumps(data.get('properties', {})),
                data.get('timestamp', datetime.utcnow()),
                json.dumps(mcp_metadata)
            )
            
            return {'id': result['id'], 'event_id': result['event_id']}
    
    async def _store_generic_data(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """Store generic data in mcp_data table"""
        async with self.connection_pool.acquire() as conn:
            # Create generic storage table if needed
            create_table_query = """
                CREATE TABLE IF NOT EXISTS mcp_data (
                    id SERIAL PRIMARY KEY,
                    data_type VARCHAR(50),
                    data_payload JSONB,
                    routing_metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            await conn.execute(create_table_query)
            
            # Insert data
            query = """
                INSERT INTO mcp_data (data_type, data_payload, routing_metadata)
                VALUES ($1, $2, $3)
                RETURNING id
            """
            
            routing_metadata = {
                'routing_id': data.get('mcp_routing_id'),
                'processed_at': data.get('mcp_processed_at'),
                'classification': data.get('mcp_classification')
            }
            
            result = await conn.fetchrow(
                query,
                data_type,
                json.dumps(data),
                json.dumps(routing_metadata)
            )
            
            return {'id': result['id'], 'data_type': data_type}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check PostgreSQL processor health"""
        try:
            if not self.connection_pool:
                return {'status': 'unhealthy', 'error': 'No connection pool'}
            
            async with self.connection_pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            return {
                'status': 'healthy',
                'initialized': self.initialized,
                'stats': self.stats.copy(),
                'pool_size': len(self.connection_pool._holders)
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': self.stats.copy()
            }


class ClickHouseProcessor(BaseProcessor):
    """
    ClickHouse processor for analytics data
    
    Handles:
    - Event data and time-series
    - Analytics aggregations
    - Performance metrics
    - Historical data
    """
    
    def __init__(self):
        super().__init__("ClickHouse")
        self.client = None
    
    async def initialize(self):
        """Initialize ClickHouse client"""
        try:
            self.client = clickhouse_connect.get_client(
                host=config.clickhouse_host,
                port=config.clickhouse_port,
                database='experiments'
            )
            
            # Test connection
            await asyncio.get_event_loop().run_in_executor(
                None, self.client.ping
            )
            
            # Ensure tables exist
            await self._ensure_tables()
            
            self.initialized = True
            logger.info("ClickHouse processor initialized", 
                       host=config.clickhouse_host,
                       port=config.clickhouse_port)
            
        except Exception as e:
            logger.error("Failed to initialize ClickHouse processor", error=str(e))
            raise
    
    async def _ensure_tables(self):
        """Ensure required ClickHouse tables exist"""
        # Events table for time-series data
        events_table = """
            CREATE TABLE IF NOT EXISTS mcp_events (
                event_id String,
                user_id String,
                experiment_id String,
                event_type String,
                timestamp DateTime,
                properties String,
                mcp_routing_id String,
                mcp_processed_at DateTime,
                date Date MATERIALIZED toDate(timestamp)
            ) ENGINE = MergeTree()
            ORDER BY (date, timestamp, user_id)
            PARTITION BY toYYYYMM(date)
        """
        
        # Analytics aggregations table
        analytics_table = """
            CREATE TABLE IF NOT EXISTS mcp_analytics (
                metric_name String,
                dimensions String,
                value Float64,
                timestamp DateTime,
                date Date MATERIALIZED toDate(timestamp),
                mcp_routing_id String
            ) ENGINE = MergeTree()
            ORDER BY (date, metric_name, timestamp)
            PARTITION BY toYYYYMM(date)
        """
        
        await asyncio.get_event_loop().run_in_executor(
            None, self.client.command, events_table
        )
        await asyncio.get_event_loop().run_in_executor(
            None, self.client.command, analytics_table
        )
    
    async def process_data(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data for ClickHouse storage"""
        try:
            classification = routing_task.get('classification', {})
            data_type = classification.get('data_type')
            
            # Transform data for ClickHouse
            transformed_data = self._transform_for_clickhouse(data, routing_task)
            
            # Route based on data type
            if data_type == 'event':
                result = await self._store_event_data(transformed_data)
            elif data_type == 'analytics':
                result = await self._store_analytics_data(transformed_data)
            else:
                # Store in generic events table with data_type as event_type
                transformed_data['event_type'] = data_type or 'unknown'
                result = await self._store_event_data(transformed_data)
            
            self._update_stats(True)
            
            logger.info("ClickHouse processing completed",
                       data_type=data_type,
                       routing_id=routing_task.get('routing_id'))
            
            return result
            
        except Exception as e:
            error_msg = f"ClickHouse processing failed: {str(e)}"
            self._update_stats(False, error_msg)
            logger.error("ClickHouse processing failed",
                        error=str(e),
                        routing_id=routing_task.get('routing_id'),
                        traceback=traceback.format_exc())
            raise
    
    def _transform_for_clickhouse(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for ClickHouse storage"""
        # Convert timestamp to ClickHouse format
        timestamp = data.get('timestamp', datetime.utcnow())
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        
        return {
            'event_id': data.get('event_id', f"ch_event_{datetime.utcnow().isoformat()}"),
            'user_id': data.get('user_id', ''),
            'experiment_id': data.get('experiment_id', ''),
            'event_type': data.get('event_type', 'unknown'),
            'timestamp': timestamp,
            'properties': json.dumps(data.get('properties', data)),  # Store full data as properties
            'mcp_routing_id': routing_task.get('routing_id', ''),
            'mcp_processed_at': datetime.utcnow()
        }
    
    async def _store_event_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store event data in ClickHouse events table"""
        await asyncio.get_event_loop().run_in_executor(
            None,
            self.client.insert,
            'mcp_events',
            [[
                data['event_id'],
                data['user_id'],
                data['experiment_id'],
                data['event_type'],
                data['timestamp'],
                data['properties'],
                data['mcp_routing_id'],
                data['mcp_processed_at']
            ]]
        )
        
        return {'event_id': data['event_id'], 'stored_at': data['mcp_processed_at']}
    
    async def _store_analytics_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store analytics data in ClickHouse analytics table"""
        # Extract metrics from the data
        metrics = data.get('metrics', {})
        if not metrics:
            # Convert data to generic metric
            metrics = {'count': 1}
        
        rows = []
        for metric_name, value in metrics.items():
            rows.append([
                metric_name,
                json.dumps(data.get('dimensions', {})),
                float(value),
                data['timestamp'],
                data['mcp_routing_id']
            ])
        
        await asyncio.get_event_loop().run_in_executor(
            None,
            self.client.insert,
            'mcp_analytics',
            rows
        )
        
        return {'metrics_stored': len(metrics), 'stored_at': data['mcp_processed_at']}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ClickHouse processor health"""
        try:
            if not self.client:
                return {'status': 'unhealthy', 'error': 'No client connection'}
            
            # Test with a simple query
            await asyncio.get_event_loop().run_in_executor(
                None, self.client.query, 'SELECT 1'
            )
            
            return {
                'status': 'healthy',
                'initialized': self.initialized,
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': self.stats.copy()
            }


class ChromaDBProcessor(BaseProcessor):
    """
    ChromaDB processor for semantic search and AI data
    
    Handles:
    - Vector embeddings
    - Experiment context storage
    - Semantic search data
    - AI-enhanced metadata
    """
    
    def __init__(self):
        super().__init__("ChromaDB")
    
    async def initialize(self):
        """Initialize ChromaDB processor"""
        try:
            # ChromaDB is initialized via the vector_store singleton
            if not vector_store.client:
                await vector_store.initialize()
            
            self.initialized = True
            logger.info("ChromaDB processor initialized")
            
        except Exception as e:
            logger.error("Failed to initialize ChromaDB processor", error=str(e))
            raise
    
    async def process_data(self, data: Dict[str, Any], routing_task: Dict[str, Any]) -> Dict[str, Any]:
        """Process data for ChromaDB storage"""
        try:
            classification = routing_task.get('classification', {})
            data_type = classification.get('data_type')
            
            # Route based on data type
            if data_type == 'experiment':
                result = await self._store_experiment_context(data)
            elif data_type == 'optimization':
                result = await self._store_optimization_pattern(data)
            elif data_type == 'event' and classification.get('ai_enhanced'):
                result = await self._store_enhanced_event(data)
            elif data_type == 'user_data' and 'journey' in data:
                result = await self._store_user_journey(data)
            else:
                # Generic storage in events collection
                result = await self._store_generic_context(data, data_type)
            
            self._update_stats(True)
            
            logger.info("ChromaDB processing completed",
                       data_type=data_type,
                       routing_id=routing_task.get('routing_id'),
                       doc_id=result.get('doc_id'))
            
            return result
            
        except Exception as e:
            error_msg = f"ChromaDB processing failed: {str(e)}"
            self._update_stats(False, error_msg)
            logger.error("ChromaDB processing failed",
                        error=str(e),
                        routing_id=routing_task.get('routing_id'),
                        traceback=traceback.format_exc())
            raise
    
    async def _store_experiment_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store experiment context in ChromaDB"""
        doc_id = await vector_store.store_experiment_context(data)
        return {'doc_id': doc_id, 'collection': 'experiments'}
    
    async def _store_optimization_pattern(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store optimization pattern in ChromaDB"""
        doc_id = await vector_store.store_optimization_pattern(data)
        return {'doc_id': doc_id, 'collection': 'optimization_patterns'}
    
    async def _store_user_journey(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store user journey in ChromaDB"""
        doc_id = await vector_store.store_user_journey(data)
        return {'doc_id': doc_id, 'collection': 'user_journeys'}
    
    async def _store_enhanced_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store AI-enhanced event in ChromaDB"""
        # Transform event to context format
        context_data = {
            'event_id': data.get('event_id'),
            'event_type': data.get('event_type'),
            'user_context': data.get('user_context', {}),
            'experiment_context': data.get('experiment_context', {}),
            'semantic_features': data.get('semantic_features', {}),
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat())
        }
        
        # Store in events collection
        collection = vector_store.collections[config.events_collection]
        doc_id = f"event_{data.get('event_id', '')}_{datetime.utcnow().isoformat()}"
        
        # Generate description for embedding
        description_parts = []
        if event_type := data.get('event_type'):
            description_parts.append(f"Event: {event_type}")
        if user_id := data.get('user_id'):
            description_parts.append(f"User: {user_id}")
        if experiment_id := data.get('experiment_id'):
            description_parts.append(f"Experiment: {experiment_id}")
        if properties := data.get('properties'):
            description_parts.append(f"Context: {json.dumps(properties)[:200]}")
        
        context_text = ". ".join(description_parts)
        
        # Metadata
        metadata = {
            'event_id': data.get('event_id'),
            'event_type': data.get('event_type'),
            'user_id': data.get('user_id', ''),
            'experiment_id': data.get('experiment_id', ''),
            'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
            'ai_enhanced': True
        }
        
        collection.add(
            documents=[context_text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        return {'doc_id': doc_id, 'collection': 'events'}
    
    async def _store_generic_context(self, data: Dict[str, Any], data_type: str) -> Dict[str, Any]:
        """Store generic data context in ChromaDB"""
        # Use events collection as fallback
        collection = vector_store.collections[config.events_collection]
        doc_id = f"generic_{data_type}_{datetime.utcnow().isoformat()}"
        
        # Create basic description
        context_text = f"Data type: {data_type}. Content: {json.dumps(data)[:500]}"
        
        metadata = {
            'data_type': data_type,
            'timestamp': datetime.utcnow().isoformat(),
            'generic_storage': True
        }
        
        collection.add(
            documents=[context_text],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        return {'doc_id': doc_id, 'collection': 'events', 'type': 'generic'}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB processor health"""
        try:
            health_info = await vector_store.health_check()
            return {
                **health_info,
                'initialized': self.initialized,
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'stats': self.stats.copy()
            }
