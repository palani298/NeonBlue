# Data Classifier - AI-powered data type classification for intelligent routing
"""
The Data Classifier analyzes incoming data and determines:
1. Data type (experiment, event, user_data, analytics)
2. Processing requirements (real-time, batch, AI-enhanced)
3. Storage needs (operational, analytical, semantic)
4. Priority and routing preferences

This enables intelligent routing to appropriate data stores.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import re
from datetime import datetime
from structlog import get_logger

logger = get_logger(__name__)


class DataType(Enum):
    """Data type classifications"""
    EXPERIMENT = "experiment"
    EVENT = "event" 
    USER_DATA = "user_data"
    ANALYTICS = "analytics"
    ASSIGNMENT = "assignment"
    OPTIMIZATION = "optimization"
    UNKNOWN = "unknown"


class ProcessingType(Enum):
    """Processing requirement classifications"""
    REAL_TIME = "real_time"
    NEAR_REAL_TIME = "near_real_time"
    BATCH = "batch"
    AI_ENHANCED = "ai_enhanced"
    ARCHIVE = "archive"


class StorageType(Enum):
    """Storage requirement classifications"""
    OPERATIONAL = "operational"      # PostgreSQL - CRUD operations
    ANALYTICAL = "analytical"        # ClickHouse - analytics queries
    SEMANTIC = "semantic"           # ChromaDB - similarity/AI search
    CACHE = "cache"                # Redis - temporary/session data


class DataClassifier:
    """
    AI-powered data classifier for intelligent routing decisions
    
    Analyzes data structure, content, and context to determine:
    - Where data should be stored
    - How it should be processed  
    - What AI enhancements to apply
    """
    
    def __init__(self):
        self.classification_rules = self._load_classification_rules()
        
    async def classify_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify incoming data for routing decisions
        
        Returns comprehensive classification including:
        - data_type: Primary data category
        - processing_type: Processing requirements
        - storage_types: Recommended storage destinations
        - priority: Processing priority (1-10)
        - ai_enhanced: Whether to apply AI processing
        - metadata: Additional classification metadata
        """
        try:
            # Primary data type detection
            data_type = self._detect_data_type(data)
            
            # Processing requirements
            processing_type = self._determine_processing_type(data, data_type)
            
            # Storage destinations
            storage_types = self._determine_storage_types(data, data_type)
            
            # Priority assessment  
            priority = self._assess_priority(data, data_type)
            
            # AI enhancement determination
            ai_enhanced = self._should_ai_enhance(data, data_type)
            
            # Additional metadata
            metadata = self._extract_metadata(data, data_type)
            
            classification = {
                'data_type': data_type.value,
                'processing_type': processing_type.value,
                'storage_types': [st.value for st in storage_types],
                'priority': priority,
                'ai_enhanced': ai_enhanced,
                'metadata': metadata,
                'classified_at': datetime.utcnow().isoformat(),
                'confidence_score': self._calculate_confidence(data, data_type)
            }
            
            logger.info("Data classified", 
                       data_type=data_type.value,
                       storage_types=[st.value for st in storage_types],
                       priority=priority,
                       ai_enhanced=ai_enhanced)
            
            return classification
            
        except Exception as e:
            logger.error("Data classification failed", error=str(e))
            # Return safe defaults
            return {
                'data_type': DataType.UNKNOWN.value,
                'processing_type': ProcessingType.BATCH.value,
                'storage_types': [StorageType.OPERATIONAL.value],
                'priority': 5,
                'ai_enhanced': False,
                'metadata': {},
                'classified_at': datetime.utcnow().isoformat(),
                'confidence_score': 0.0,
                'classification_error': str(e)
            }
    
    def _detect_data_type(self, data: Dict[str, Any]) -> DataType:
        """Detect primary data type from structure and content"""
        
        # Check for explicit type markers
        if 'event_type' in data or 'event_name' in data:
            return DataType.EVENT
            
        if 'experiment_id' in data and 'variants' in data:
            return DataType.EXPERIMENT
            
        if 'user_id' in data and 'assignment_id' in data:
            return DataType.ASSIGNMENT
            
        if 'optimization_type' in data or 'improvement_percentage' in data:
            return DataType.OPTIMIZATION
            
        # Check for user-centric data
        if 'user_id' in data and any(k in data for k in ['profile', 'preferences', 'segment']):
            return DataType.USER_DATA
            
        # Check for analytics data
        if any(k in data for k in ['metrics', 'aggregates', 'timestamp', 'dimensions']):
            return DataType.ANALYTICS
            
        # Default classification based on structure
        if len(data) > 10 and 'timestamp' in data:
            return DataType.EVENT
            
        return DataType.UNKNOWN
    
    def _determine_processing_type(self, data: Dict[str, Any], data_type: DataType) -> ProcessingType:
        """Determine processing requirements based on data characteristics"""
        
        # Real-time processing for critical events
        if data_type == DataType.EVENT:
            if data.get('event_type') in ['conversion', 'signup', 'purchase', 'error']:
                return ProcessingType.REAL_TIME
            return ProcessingType.NEAR_REAL_TIME
            
        # Real-time for assignment data
        if data_type == DataType.ASSIGNMENT:
            return ProcessingType.REAL_TIME
            
        # AI-enhanced processing for experiments and optimizations
        if data_type in [DataType.EXPERIMENT, DataType.OPTIMIZATION]:
            return ProcessingType.AI_ENHANCED
            
        # Batch processing for analytics and bulk data
        if data_type == DataType.ANALYTICS:
            return ProcessingType.BATCH
            
        # User data can be near real-time
        if data_type == DataType.USER_DATA:
            return ProcessingType.NEAR_REAL_TIME
            
        return ProcessingType.BATCH
    
    def _determine_storage_types(self, data: Dict[str, Any], data_type: DataType) -> List[StorageType]:
        """Determine where data should be stored"""
        storage_types = []
        
        # Operational data always goes to PostgreSQL
        if data_type in [DataType.EXPERIMENT, DataType.ASSIGNMENT, DataType.USER_DATA]:
            storage_types.append(StorageType.OPERATIONAL)
            
        # Analytics data goes to ClickHouse
        if data_type in [DataType.EVENT, DataType.ANALYTICS]:
            storage_types.append(StorageType.ANALYTICAL)
            
        # AI-enhanced data goes to ChromaDB
        if data_type in [DataType.EXPERIMENT, DataType.OPTIMIZATION]:
            storage_types.append(StorageType.SEMANTIC)
            
        # Events with rich context get semantic storage too
        if data_type == DataType.EVENT and self._has_rich_context(data):
            storage_types.append(StorageType.SEMANTIC)
            
        # High-frequency access patterns get cache
        if data_type in [DataType.ASSIGNMENT, DataType.USER_DATA]:
            storage_types.append(StorageType.CACHE)
            
        # Ensure at least one storage type
        if not storage_types:
            storage_types.append(StorageType.OPERATIONAL)
            
        return storage_types
    
    def _assess_priority(self, data: Dict[str, Any], data_type: DataType) -> int:
        """Assess processing priority (1=highest, 10=lowest)"""
        
        # Critical real-time events
        if data_type == DataType.EVENT and data.get('event_type') in ['error', 'failure']:
            return 1
            
        # User assignments need fast processing
        if data_type == DataType.ASSIGNMENT:
            return 2
            
        # Conversion events are high priority
        if data_type == DataType.EVENT and data.get('event_type') in ['conversion', 'purchase']:
            return 3
            
        # Experiment data is moderately high priority
        if data_type == DataType.EXPERIMENT:
            return 4
            
        # Regular events
        if data_type == DataType.EVENT:
            return 5
            
        # User data updates
        if data_type == DataType.USER_DATA:
            return 6
            
        # Analytics and optimization can be lower priority
        if data_type in [DataType.ANALYTICS, DataType.OPTIMIZATION]:
            return 7
            
        return 8  # Default priority
    
    def _should_ai_enhance(self, data: Dict[str, Any], data_type: DataType) -> bool:
        """Determine if data should receive AI enhancement"""
        
        # Always enhance experiments and optimizations
        if data_type in [DataType.EXPERIMENT, DataType.OPTIMIZATION]:
            return True
            
        # Enhance events with rich context
        if data_type == DataType.EVENT and self._has_rich_context(data):
            return True
            
        # Enhance user data with behavioral patterns
        if data_type == DataType.USER_DATA and 'behavior' in data:
            return True
            
        return False
    
    def _has_rich_context(self, data: Dict[str, Any]) -> bool:
        """Check if event data has rich contextual information"""
        context_indicators = [
            'user_journey', 'session_id', 'referrer', 'page_content',
            'interaction_sequence', 'device_info', 'location',
            'experiment_variants', 'personalization_data'
        ]
        
        return sum(1 for indicator in context_indicators if indicator in data) >= 3
    
    def _extract_metadata(self, data: Dict[str, Any], data_type: DataType) -> Dict[str, Any]:
        """Extract additional metadata for routing decisions"""
        metadata = {}
        
        # Common metadata
        if 'timestamp' in data:
            metadata['has_timestamp'] = True
            metadata['data_recency'] = self._calculate_recency(data['timestamp'])
            
        if 'user_id' in data:
            metadata['has_user_context'] = True
            
        if 'experiment_id' in data:
            metadata['has_experiment_context'] = True
            
        # Data size estimation
        metadata['estimated_size'] = len(str(data))
        metadata['field_count'] = len(data)
        
        # Nested data detection
        nested_fields = [k for k, v in data.items() if isinstance(v, (dict, list))]
        if nested_fields:
            metadata['has_nested_data'] = True
            metadata['nested_fields'] = nested_fields
            
        return metadata
    
    def _calculate_recency(self, timestamp: str) -> str:
        """Calculate how recent the data is"""
        try:
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                dt = timestamp
                
            age = datetime.utcnow() - dt.replace(tzinfo=None)
            
            if age.total_seconds() < 60:
                return "very_recent"  # < 1 minute
            elif age.total_seconds() < 3600:
                return "recent"       # < 1 hour
            elif age.total_seconds() < 86400:
                return "today"        # < 1 day
            else:
                return "older"        # > 1 day
                
        except Exception:
            return "unknown"
    
    def _calculate_confidence(self, data: Dict[str, Any], data_type: DataType) -> float:
        """Calculate confidence score for the classification"""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for clear type indicators
        if data_type != DataType.UNKNOWN:
            confidence += 0.3
            
        # Strong field indicators
        type_indicators = {
            DataType.EXPERIMENT: ['experiment_id', 'variants', 'hypothesis'],
            DataType.EVENT: ['event_type', 'event_name', 'timestamp'],
            DataType.USER_DATA: ['user_id', 'profile', 'preferences'],
            DataType.ASSIGNMENT: ['assignment_id', 'variant_id'],
            DataType.OPTIMIZATION: ['optimization_type', 'improvement_percentage']
        }
        
        if data_type in type_indicators:
            matching_indicators = sum(1 for field in type_indicators[data_type] if field in data)
            confidence += (matching_indicators / len(type_indicators[data_type])) * 0.2
            
        return min(confidence, 1.0)
    
    def _load_classification_rules(self) -> Dict[str, Any]:
        """Load classification rules (could be from config/database)"""
        return {
            'priority_events': ['error', 'failure', 'conversion', 'purchase', 'signup'],
            'ai_enhancement_fields': ['content', 'description', 'text', 'journey', 'behavior'],
            'real_time_types': ['assignment', 'critical_event'],
            'semantic_storage_types': ['experiment', 'optimization', 'rich_event']
        }
