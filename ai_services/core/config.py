# AI Services Configuration
import os
from typing import Optional
from pydantic import BaseSettings


class AIConfig(BaseSettings):
    """Configuration for AI Services"""
    
    # Database connections
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://experiments:password@localhost:5432/experiments")
    clickhouse_host: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    clickhouse_port: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    chromadb_host: str = os.getenv("CHROMADB_HOST", "localhost:8000")
    
    # Redis configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_pool_size: int = int(os.getenv("REDIS_POOL_SIZE", "10"))
    redis_decode_responses: bool = True
    
    # Kafka configuration
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_consumer_group: str = os.getenv("CONSUMER_GROUP_ID", "ai_processor")
    
    # AI API Keys
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # MCP Configuration
    mcp_router_host: str = os.getenv("MCP_ROUTER_HOST", "localhost:8000")
    mcp_server_name: str = os.getenv("MCP_SERVER_NAME", "default")
    mcp_port: int = int(os.getenv("MCP_PORT", "8000"))
    
    # AI Processing Settings
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
    max_batch_size: int = int(os.getenv("MAX_BATCH_SIZE", "100"))
    processing_interval: int = int(os.getenv("PROCESSING_INTERVAL", "10"))  # seconds
    
    # ChromaDB Collections
    experiments_collection: str = "experiments"
    user_journeys_collection: str = "user_journeys"
    optimization_patterns_collection: str = "optimization_patterns"
    events_collection: str = "events"
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"


# Global configuration instance
config = AIConfig()
