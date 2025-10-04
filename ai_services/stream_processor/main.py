# Kafka Stream Processor - Bridge between Kafka and MCP Router
"""
The Stream Processor consumes events from Kafka topics and routes them through
the MCP (Model Context Protocol) system for intelligent data distribution.

Flow:
1. Consume messages from Kafka topics (experiments_events, user_events, etc.)
2. Parse and validate incoming messages
3. Send to MCP Router for intelligent classification and routing
4. Handle success/failure responses and logging
5. Maintain processing metrics and health status

This creates the bridge between your existing Kafka-based architecture and 
the new AI-enhanced MCP system.
"""

import asyncio
import json
import signal
import sys
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import traceback
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
import httpx
from structlog import get_logger

from ..core.config import config


logger = get_logger(__name__)


class KafkaMCPProcessor:
    """
    Kafka to MCP Router bridge processor
    
    Consumes Kafka messages and routes them through the MCP system for
    intelligent data distribution to PostgreSQL, ClickHouse, and ChromaDB.
    """
    
    def __init__(self):
        self.consumer = None
        self.mcp_client = httpx.AsyncClient(base_url=f"http://{config.mcp_router_host}")
        self.running = False
        self.processed_count = 0
        self.error_count = 0
        self.start_time = datetime.utcnow()
        
        # Topics to consume from
        self.topics = [
            'experiments_events',    # From your existing flow
            'user_events',          
            'analytics_events',
            'assignment_events',
            'optimization_events'
        ]
        
        # Processing metrics
        self.metrics = {
            'messages_consumed': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'mcp_routing_success': 0,
            'mcp_routing_failed': 0,
            'topics_metrics': {topic: 0 for topic in self.topics},
            'last_processed': None,
            'last_error': None
        }
        
        # Shutdown handling
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize Kafka consumer and connections"""
        try:
            logger.info("Initializing Kafka MCP Processor...")
            
            # Initialize Kafka consumer
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=config.kafka_bootstrap_servers,
                group_id=config.kafka_consumer_group,
                auto_offset_reset='latest',  # Start from latest for new deployment
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                consumer_timeout_ms=1000,
                value_deserializer=self._deserialize_message
            )
            
            # Start consumer
            await self.consumer.start()
            
            # Test MCP Router connection
            health_response = await self.mcp_client.get("/health")
            if health_response.status_code != 200:
                raise Exception(f"MCP Router unhealthy: {health_response.status_code}")
            
            logger.info("Kafka MCP Processor initialized successfully",
                       topics=self.topics,
                       bootstrap_servers=config.kafka_bootstrap_servers,
                       consumer_group=config.kafka_consumer_group,
                       mcp_router=config.mcp_router_host)
            
        except Exception as e:
            logger.error("Failed to initialize Kafka MCP Processor", error=str(e))
            raise
    
    async def start_processing(self):
        """Start the main processing loop"""
        self.running = True
        logger.info("Starting Kafka MCP Processor...")
        
        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, self._signal_handler)
        
        try:
            # Main processing loop
            await self._processing_loop()
            
        except Exception as e:
            logger.error("Fatal error in processing loop", error=str(e))
            raise
        finally:
            await self.shutdown()
    
    async def _processing_loop(self):
        """Main Kafka message processing loop"""
        logger.info("Kafka MCP processing loop started")
        
        while self.running:
            try:
                # Consume messages with timeout
                msg_batch = await asyncio.wait_for(
                    self.consumer.getmany(timeout_ms=1000, max_records=10),
                    timeout=2.0
                )
                
                if not msg_batch:
                    continue  # No messages, continue loop
                
                # Process messages by topic
                processing_tasks = []
                for topic_partition, messages in msg_batch.items():
                    for message in messages:
                        task = asyncio.create_task(
                            self._process_message(message, topic_partition.topic)
                        )
                        processing_tasks.append(task)
                
                # Process messages concurrently
                if processing_tasks:
                    results = await asyncio.gather(*processing_tasks, return_exceptions=True)
                    
                    # Count results
                    for result in results:
                        if isinstance(result, Exception):
                            self.error_count += 1
                            logger.error("Message processing failed", error=str(result))
                        else:
                            self.processed_count += 1
                
                # Update metrics
                self.metrics['last_processed'] = datetime.utcnow().isoformat()
                
            except asyncio.TimeoutError:
                # Normal timeout, continue processing
                continue
            except KafkaError as e:
                logger.error("Kafka error", error=str(e))
                await asyncio.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.error("Unexpected error in processing loop", 
                           error=str(e), traceback=traceback.format_exc())
                await asyncio.sleep(1)
    
    async def _process_message(self, message, topic: str):
        """Process individual Kafka message"""
        try:
            # Parse message
            if message.value is None:
                logger.warning("Received null message", topic=topic, offset=message.offset)
                return
            
            data = message.value
            message_key = message.key.decode('utf-8') if message.key else None
            
            # Add message metadata
            enhanced_data = {
                **data,
                '_kafka_metadata': {
                    'topic': topic,
                    'partition': message.partition,
                    'offset': message.offset,
                    'timestamp': message.timestamp,
                    'key': message_key
                }
            }
            
            # Route through MCP system
            routing_response = await self._route_through_mcp(enhanced_data, topic)
            
            # Update metrics
            self.metrics['messages_consumed'] += 1
            self.metrics['topics_metrics'][topic] += 1
            
            if routing_response.get('status') == 'success':
                self.metrics['messages_processed'] += 1
                self.metrics['mcp_routing_success'] += 1
                
                logger.info("Message processed successfully",
                           topic=topic,
                           offset=message.offset,
                           routing_id=routing_response.get('routing_id'),
                           destinations=routing_response.get('destinations'))
            else:
                self.metrics['messages_failed'] += 1
                self.metrics['mcp_routing_failed'] += 1
                logger.error("Message routing failed", 
                           topic=topic, offset=message.offset,
                           error=routing_response.get('error'))
            
        except Exception as e:
            self.metrics['messages_failed'] += 1
            self.metrics['last_error'] = str(e)
            logger.error("Failed to process message",
                        topic=topic,
                        offset=getattr(message, 'offset', None),
                        error=str(e),
                        traceback=traceback.format_exc())
            raise
    
    async def _route_through_mcp(self, data: Dict[str, Any], topic: str) -> Dict[str, Any]:
        """Route data through MCP Router"""
        try:
            # Prepare routing request
            routing_data = {
                **data,
                '_source_topic': topic,
                '_processed_at': datetime.utcnow().isoformat()
            }
            
            # Send to MCP Router
            response = await self.mcp_client.post("/route", json=routing_data, timeout=30.0)
            
            if response.status_code == 200:
                return {
                    'status': 'success',
                    **response.json()
                }
            else:
                return {
                    'status': 'error',
                    'error': f"MCP Router returned {response.status_code}: {response.text}"
                }
                
        except httpx.TimeoutException:
            return {
                'status': 'error',
                'error': 'MCP Router timeout'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': f"MCP Router communication failed: {str(e)}"
            }
    
    def _deserialize_message(self, serialized_value: bytes) -> Dict[str, Any]:
        """Deserialize Kafka message value"""
        try:
            if serialized_value is None:
                return {}
            
            # Try JSON deserialization
            return json.loads(serialized_value.decode('utf-8'))
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to deserialize message as JSON", error=str(e))
            # Return raw string in a dict
            return {
                'raw_data': serialized_value.decode('utf-8', errors='replace'),
                'deserialization_error': str(e)
            }
        except Exception as e:
            logger.error("Message deserialization failed", error=str(e))
            return {
                'deserialization_failed': True,
                'error': str(e)
            }
    
    def _signal_handler(self):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received")
        self.running = False
        self.shutdown_event.set()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get processor status and metrics"""
        uptime = datetime.utcnow() - self.start_time
        
        return {
            'status': 'running' if self.running else 'stopped',
            'uptime_seconds': int(uptime.total_seconds()),
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'success_rate': (
                self.processed_count / (self.processed_count + self.error_count)
                if (self.processed_count + self.error_count) > 0 else 0
            ),
            'metrics': self.metrics.copy(),
            'topics': self.topics,
            'consumer_group': config.kafka_consumer_group,
            'mcp_router': config.mcp_router_host
        }
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Kafka MCP Processor...")
        
        self.running = False
        
        # Stop Kafka consumer
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("Kafka consumer stopped")
            except Exception as e:
                logger.error("Error stopping Kafka consumer", error=str(e))
        
        # Close HTTP client
        if self.mcp_client:
            await self.mcp_client.aclose()
            logger.info("MCP client closed")
        
        # Final metrics log
        final_metrics = await self.get_status()
        logger.info("Kafka MCP Processor shutdown complete", final_metrics=final_metrics)


# Global processor instance
processor = KafkaMCPProcessor()


async def main():
    """Main entry point"""
    try:
        logger.info("Starting Kafka MCP Stream Processor")
        
        # Initialize processor
        await processor.initialize()
        
        # Start processing
        await processor.start_processing()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error("Fatal error", error=str(e), traceback=traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("Stream processor exiting")


if __name__ == "__main__":
    # Configure asyncio for better performance
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error("Process failed", error=str(e))
        sys.exit(1)
