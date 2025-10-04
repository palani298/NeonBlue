# MCP Router - Central Intelligence Hub for Data Routing
"""
The MCP Router is the central intelligence layer that receives data from Kafka
and intelligently routes it to appropriate data stores:

- PostgreSQL: Core operational data (users, experiments, assignments)  
- ClickHouse: Time-series analytics and aggregated metrics
- ChromaDB: Semantic embeddings for similarity search and AI insights

The router makes intelligent decisions about data placement based on:
- Data type and structure
- Query patterns and access requirements  
- AI/ML processing needs
- Real-time vs analytical workload requirements
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import traceback

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from structlog import get_logger
from contextlib import asynccontextmanager

from ..core.config import config
from ..core.chromadb_manager import vector_store
from .data_classifier import DataClassifier
from .routing_engine import RoutingEngine
from .processors import PostgreSQLProcessor, ClickHouseProcessor, ChromaDBProcessor
from .redis_processor import RedisProcessor


logger = get_logger(__name__)


class MCPRouter:
    """
    Central MCP Router for intelligent data distribution
    
    This router analyzes incoming data and routes it to appropriate stores:
    - High-frequency operational data → PostgreSQL
    - Analytics and time-series data → ClickHouse  
    - Contextual/semantic data → ChromaDB for AI processing
    """
    
    def __init__(self):
        self.classifier = DataClassifier()
        self.routing_engine = RoutingEngine()
        self.processors = {
            'postgresql': PostgreSQLProcessor(),
            'clickhouse': ClickHouseProcessor(), 
            'chromadb': ChromaDBProcessor(),
            'redis': RedisProcessor()
        }
        self._processing_queue = asyncio.Queue()
        self._processing_task = None
        self.stats = {
            'total_processed': 0,
            'postgresql_routed': 0,
            'clickhouse_routed': 0,
            'chromadb_routed': 0,
            'redis_routed': 0,
            'errors': 0,
            'started_at': datetime.utcnow()
        }
        
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing MCP Router...")
            
            # Initialize ChromaDB connection
            await vector_store.initialize()
            
            # Initialize processors
            for name, processor in self.processors.items():
                await processor.initialize()
                logger.info(f"Initialized {name} processor")
            
            # Start background processing
            self._processing_task = asyncio.create_task(self._process_queue())
            
            logger.info("MCP Router initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize MCP Router", error=str(e))
            raise
    
    async def route_data(self, data: Dict[str, Any], source: str = "kafka") -> Dict[str, Any]:
        """
        Main routing method - intelligently distribute data to appropriate stores
        
        Args:
            data: Data payload to route
            source: Source system (kafka, api, etc.)
            
        Returns:
            Routing results and destinations
        """
        try:
            # Classify the data
            classification = await self.classifier.classify_data(data)
            
            # Determine routing destinations
            destinations = await self.routing_engine.determine_destinations(data, classification)
            
            # Queue for async processing
            routing_task = {
                'data': data,
                'classification': classification,
                'destinations': destinations,
                'source': source,
                'timestamp': datetime.utcnow().isoformat(),
                'routing_id': self._generate_routing_id(data)
            }
            
            await self._processing_queue.put(routing_task)
            
            # Update stats
            self.stats['total_processed'] += 1
            
            logger.info("Data queued for routing", 
                       routing_id=routing_task['routing_id'],
                       destinations=destinations,
                       classification=classification)
            
            return {
                'routing_id': routing_task['routing_id'],
                'destinations': destinations,
                'classification': classification,
                'queued_at': routing_task['timestamp']
            }
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error("Failed to route data", error=str(e), data_type=type(data).__name__)
            raise
    
    async def _process_queue(self):
        """Background task to process routing queue"""
        logger.info("Started MCP Router processing queue")
        
        while True:
            try:
                # Get next item from queue
                routing_task = await self._processing_queue.get()
                
                # Process the routing task
                await self._execute_routing(routing_task)
                
                # Mark task as done
                self._processing_queue.task_done()
                
            except Exception as e:
                logger.error("Error in processing queue", error=str(e))
                await asyncio.sleep(1)  # Brief pause before continuing
    
    async def _execute_routing(self, routing_task: Dict[str, Any]):
        """Execute the actual data routing to destinations"""
        data = routing_task['data']
        destinations = routing_task['destinations']
        routing_id = routing_task['routing_id']
        
        results = {}
        
        # Route to each destination
        for destination in destinations:
            try:
                processor = self.processors.get(destination)
                if not processor:
                    logger.warning(f"No processor found for destination: {destination}")
                    continue
                
                # Process data for this destination
                result = await processor.process_data(data, routing_task)
                results[destination] = {
                    'status': 'success',
                    'result': result,
                    'processed_at': datetime.utcnow().isoformat()
                }
                
                # Update stats
                stat_key = f"{destination}_routed"
                if stat_key in self.stats:
                    self.stats[stat_key] += 1
                
                logger.info(f"Successfully routed to {destination}", 
                           routing_id=routing_id, destination=destination)
                
            except Exception as e:
                results[destination] = {
                    'status': 'error',
                    'error': str(e),
                    'traceback': traceback.format_exc()
                }
                self.stats['errors'] += 1
                logger.error(f"Failed to route to {destination}", 
                           routing_id=routing_id, destination=destination, error=str(e))
        
        # Log overall routing results
        successful_destinations = [d for d, r in results.items() if r['status'] == 'success']
        failed_destinations = [d for d, r in results.items() if r['status'] == 'error']
        
        logger.info("Routing completed", 
                   routing_id=routing_id,
                   successful=successful_destinations,
                   failed=failed_destinations)
    
    def _generate_routing_id(self, data: Dict[str, Any]) -> str:
        """Generate unique routing ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        data_hash = hash(str(data)) % 10000
        return f"route_{timestamp}_{data_hash:04d}"
    
    async def get_status(self) -> Dict[str, Any]:
        """Get router status and statistics"""
        queue_size = self._processing_queue.qsize()
        uptime = datetime.utcnow() - self.stats['started_at']
        
        # Get ChromaDB health
        chromadb_health = await vector_store.health_check()
        
        return {
            'status': 'healthy',
            'uptime_seconds': int(uptime.total_seconds()),
            'queue_size': queue_size,
            'processing_active': self._processing_task is not None and not self._processing_task.done(),
            'statistics': self.stats.copy(),
            'processors': {
                name: await processor.health_check() 
                for name, processor in self.processors.items()
            },
            'chromadb_health': chromadb_health
        }
    
    async def shutdown(self):
        """Clean shutdown of the router"""
        logger.info("Shutting down MCP Router...")
        
        # Stop processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Wait for queue to empty
        await self._processing_queue.join()
        
        # Shutdown processors
        for name, processor in self.processors.items():
            try:
                await processor.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down {name} processor", error=str(e))
        
        # Close vector store
        await vector_store.close()
        
        logger.info("MCP Router shutdown complete")


# Global router instance
router = MCPRouter()


# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await router.initialize()
    yield
    # Shutdown
    await router.shutdown()


app = FastAPI(
    title="MCP Router - Intelligent Data Distribution",
    description="Central intelligence hub for routing experiment data to appropriate stores",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Endpoints
@app.post("/route")
async def route_data(data: Dict[str, Any], background_tasks: BackgroundTasks):
    """Route data through the MCP system"""
    try:
        result = await router.route_data(data, source="api")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get router status and health information"""
    return await router.get_status()


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    status = await router.get_status()
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/stats")
async def get_statistics():
    """Get detailed routing statistics"""
    status = await router.get_status()
    return status["statistics"]


if __name__ == "__main__":
    uvicorn.run(
        "ai_services.mcp_router.main:app",
        host="0.0.0.0",
        port=config.mcp_port,
        log_level=config.log_level.lower(),
        reload=False
    )
