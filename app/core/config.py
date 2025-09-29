"""Application configuration."""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    app_name: str = "Experimentation Platform"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=4, env="WORKERS")
    
    # Database
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/experiments",
        env="DATABASE_URL"
    )
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")
    
    # Redis
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    redis_decode_responses: bool = True
    
    # ClickHouse (for analytics)
    clickhouse_host: str = Field(default="localhost", env="CLICKHOUSE_HOST")
    clickhouse_port: int = Field(default=8123, env="CLICKHOUSE_PORT")
    clickhouse_database: str = Field(default="experiments_analytics", env="CLICKHOUSE_DATABASE")
    clickhouse_user: str = Field(default="default", env="CLICKHOUSE_USER")
    clickhouse_password: str = Field(default="", env="CLICKHOUSE_PASSWORD")
    
    # Kafka (for CDC)
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        env="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_prefix: str = Field(default="experiments", env="KAFKA_TOPIC_PREFIX")
    
    # Authentication
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        env="SECRET_KEY"
    )
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    bearer_tokens: List[str] = Field(
        default_factory=lambda: ["test-token-1", "test-token-2"],
        env="BEARER_TOKENS"
    )
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")  # seconds
    
    # API Timing Middleware
    enable_timing_middleware: bool = Field(default=True, env="ENABLE_TIMING_MIDDLEWARE")
    slow_api_threshold_ms: int = Field(default=1000, env="SLOW_API_THRESHOLD_MS")
    
    # Experimentation Settings
    assignment_hash_seed: str = Field(
        default="default-seed-change-in-production",
        env="ASSIGNMENT_HASH_SEED"
    )
    assignment_bucket_size: int = Field(default=10000, env="ASSIGNMENT_BUCKET_SIZE")
    assignment_cache_ttl: int = Field(default=604800, env="ASSIGNMENT_CACHE_TTL")  # 7 days
    
    # Transactional Outbox
    outbox_enabled: bool = Field(default=True, env="OUTBOX_ENABLED")
    outbox_batch_size: int = Field(default=100, env="OUTBOX_BATCH_SIZE")
    outbox_poll_interval: int = Field(default=5, env="OUTBOX_POLL_INTERVAL")  # seconds
    
    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS"
    )
    
    # Monitoring
    prometheus_enabled: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    opentelemetry_enabled: bool = Field(default=False, env="OPENTELEMETRY_ENABLED")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
