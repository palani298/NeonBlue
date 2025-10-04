# ChromaDB Manager - Vector Store for Semantic Search
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import openai
import numpy as np
from structlog import get_logger

from .config import config


logger = get_logger(__name__)


class ExperimentVectorStore:
    """
    ChromaDB integration for semantic experiment analytics and similarity search
    
    This class manages vector embeddings for:
    - Experiment configurations and results
    - User behavioral patterns and journeys  
    - Optimization strategies and patterns
    - Event data with contextual information
    """
    
    def __init__(self):
        self.client = None
        self.collections = {}
        self.openai_client = openai.AsyncOpenAI(api_key=config.openai_api_key) if config.openai_api_key else None
        self._embedding_function = None
        
    async def initialize(self):
        """Initialize ChromaDB client and collections"""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.HttpClient(host=config.chromadb_host.split(':')[0], 
                                            port=int(config.chromadb_host.split(':')[1]))
            
            # Set up embedding function
            if config.openai_api_key:
                self._embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=config.openai_api_key,
                    model_name=config.embedding_model
                )
            else:
                # Fallback to sentence transformers
                self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            
            # Create collections
            await self._create_collections()
            
            logger.info("ChromaDB initialized successfully", 
                       host=config.chromadb_host, 
                       collections=list(self.collections.keys()))
            
        except Exception as e:
            logger.error("Failed to initialize ChromaDB", error=str(e))
            raise
    
    async def _create_collections(self):
        """Create ChromaDB collections with proper configuration"""
        
        collection_configs = {
            config.experiments_collection: {
                "metadata": {"hnsw:space": "cosine", "description": "Experiment configurations, results, and insights"}
            },
            config.user_journeys_collection: {
                "metadata": {"hnsw:space": "cosine", "description": "User behavioral patterns and journey data"}
            },
            config.optimization_patterns_collection: {
                "metadata": {"hnsw:space": "cosine", "description": "Successful optimization strategies and patterns"}
            },
            config.events_collection: {
                "metadata": {"hnsw:space": "cosine", "description": "Event data with AI-enhanced context"}
            }
        }
        
        for collection_name, collection_config in collection_configs.items():
            try:
                collection = self.client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=self._embedding_function,
                    metadata=collection_config["metadata"]
                )
                self.collections[collection_name] = collection
                logger.info(f"Created/Retrieved collection: {collection_name}")
                
            except Exception as e:
                logger.error(f"Failed to create collection {collection_name}", error=str(e))
                raise
    
    async def store_experiment_context(self, experiment_data: Dict[str, Any]) -> str:
        """
        Store experiment with rich context for semantic search
        
        Args:
            experiment_data: Experiment configuration and results
            
        Returns:
            Document ID for the stored experiment
        """
        try:
            # Generate comprehensive context description
            context_text = self._generate_experiment_description(experiment_data)
            
            # Generate unique ID
            doc_id = f"exp_{experiment_data.get('experiment_id', '')}_{self._generate_hash(context_text)}"
            
            # Prepare metadata
            metadata = {
                "experiment_id": experiment_data.get("experiment_id"),
                "experiment_type": experiment_data.get("type", "unknown"),
                "industry": experiment_data.get("industry", "general"),
                "user_segment": experiment_data.get("target_segment", "all"),
                "conversion_rate": float(experiment_data.get("conversion_rate", 0.0)),
                "statistical_power": float(experiment_data.get("statistical_power", 0.0)),
                "outcome": experiment_data.get("outcome", "pending"),
                "sample_size": int(experiment_data.get("sample_size", 0)),
                "duration_days": int(experiment_data.get("duration_days", 0)),
                "timestamp": experiment_data.get("created_at", datetime.utcnow().isoformat()),
                "tags": json.dumps(experiment_data.get("tags", []))
            }
            
            # Store in ChromaDB
            self.collections[config.experiments_collection].add(
                documents=[context_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info("Stored experiment context", experiment_id=doc_id, outcome=metadata["outcome"])
            return doc_id
            
        except Exception as e:
            logger.error("Failed to store experiment context", error=str(e), experiment_id=experiment_data.get("experiment_id"))
            raise
    
    async def store_user_journey(self, journey_data: Dict[str, Any]) -> str:
        """Store user journey with behavioral context"""
        try:
            # Generate journey description
            context_text = self._generate_journey_description(journey_data)
            
            # Generate unique ID
            doc_id = f"journey_{journey_data.get('user_id', '')}_{self._generate_hash(context_text)}"
            
            # Prepare metadata
            metadata = {
                "user_id": journey_data.get("user_id"),
                "user_segment": journey_data.get("user_segment", "unknown"),
                "journey_length": int(journey_data.get("journey_length", 0)),
                "session_duration": int(journey_data.get("session_duration", 0)),
                "conversion_outcome": journey_data.get("conversion_outcome", "none"),
                "value": float(journey_data.get("value", 0.0)),
                "device_type": journey_data.get("device_type", "unknown"),
                "traffic_source": journey_data.get("traffic_source", "unknown"),
                "experiment_variants": json.dumps(journey_data.get("experiment_variants", [])),
                "timestamp": journey_data.get("timestamp", datetime.utcnow().isoformat())
            }
            
            # Store in ChromaDB
            self.collections[config.user_journeys_collection].add(
                documents=[context_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info("Stored user journey", journey_id=doc_id, outcome=metadata["conversion_outcome"])
            return doc_id
            
        except Exception as e:
            logger.error("Failed to store user journey", error=str(e))
            raise
    
    async def store_optimization_pattern(self, optimization_data: Dict[str, Any]) -> str:
        """Store successful optimization patterns"""
        try:
            context_text = self._generate_optimization_description(optimization_data)
            doc_id = f"opt_{optimization_data.get('optimization_id', '')}_{self._generate_hash(context_text)}"
            
            metadata = {
                "optimization_type": optimization_data.get("optimization_type"),
                "outcome": optimization_data.get("outcome", "unknown"),
                "improvement_percentage": float(optimization_data.get("improvement_percentage", 0.0)),
                "applied_to_segments": json.dumps(optimization_data.get("applied_to_segments", [])),
                "industry": optimization_data.get("industry", "general"),
                "implementation_effort": optimization_data.get("implementation_effort", "unknown"),
                "statistical_significance": float(optimization_data.get("statistical_significance", 0.0)),
                "timestamp": optimization_data.get("timestamp", datetime.utcnow().isoformat())
            }
            
            self.collections[config.optimization_patterns_collection].add(
                documents=[context_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info("Stored optimization pattern", optimization_id=doc_id, improvement=metadata["improvement_percentage"])
            return doc_id
            
        except Exception as e:
            logger.error("Failed to store optimization pattern", error=str(e))
            raise
    
    async def semantic_search(self, query: str, collection_name: str, 
                            n_results: int = 10, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform semantic search across specified collection
        
        Args:
            query: Natural language query
            collection_name: Target collection name
            n_results: Number of results to return
            filters: Metadata filters
            
        Returns:
            Search results with documents, metadata, and distances
        """
        try:
            if collection_name not in self.collections:
                raise ValueError(f"Collection {collection_name} not found")
            
            # Perform semantic search
            results = self.collections[collection_name].query(
                query_texts=[query],
                n_results=n_results,
                where=filters,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = {
                "query": query,
                "collection": collection_name,
                "total_results": len(results["documents"][0]) if results["documents"] else 0,
                "results": []
            }
            
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    result_item = {
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity_score": 1 - results["distances"][0][i],  # Convert distance to similarity
                        "distance": results["distances"][0][i]
                    }
                    formatted_results["results"].append(result_item)
            
            logger.info("Semantic search completed", query=query, collection=collection_name, 
                       results_count=formatted_results["total_results"])
            
            return formatted_results
            
        except Exception as e:
            logger.error("Semantic search failed", error=str(e), query=query, collection=collection_name)
            raise
    
    async def find_similar_experiments(self, experiment_description: str, 
                                     filters: Optional[Dict] = None, 
                                     min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """Find experiments similar to the given description"""
        results = await self.semantic_search(
            query=experiment_description,
            collection_name=config.experiments_collection,
            n_results=20,
            filters=filters
        )
        
        # Filter by minimum similarity
        similar_experiments = [
            result for result in results["results"] 
            if result["similarity_score"] >= min_similarity
        ]
        
        return similar_experiments
    
    async def find_successful_optimization_patterns(self, context: str, 
                                                  improvement_threshold: float = 10.0) -> List[Dict[str, Any]]:
        """Find successful optimization patterns based on context"""
        filters = {
            "outcome": "success",
            "improvement_percentage": {"$gte": improvement_threshold}
        }
        
        results = await self.semantic_search(
            query=context,
            collection_name=config.optimization_patterns_collection,
            n_results=30,
            filters=filters
        )
        
        return results["results"]
    
    def _generate_experiment_description(self, experiment_data: Dict[str, Any]) -> str:
        """Generate comprehensive experiment description for embedding"""
        description_parts = []
        
        # Basic info
        if name := experiment_data.get("name"):
            description_parts.append(f"Experiment: {name}")
        
        if exp_type := experiment_data.get("type"):
            description_parts.append(f"Type: {exp_type}")
        
        if hypothesis := experiment_data.get("hypothesis"):
            description_parts.append(f"Hypothesis: {hypothesis}")
        
        # Configuration
        if variants := experiment_data.get("variants"):
            variant_descriptions = [f"{v.get('name', '')}: {v.get('description', '')}" for v in variants]
            description_parts.append(f"Variants: {'; '.join(variant_descriptions)}")
        
        # Results
        if outcome := experiment_data.get("outcome"):
            description_parts.append(f"Outcome: {outcome}")
        
        if conv_rate := experiment_data.get("conversion_rate"):
            description_parts.append(f"Conversion rate improvement: {conv_rate * 100:.1f}%")
        
        # Context
        if segment := experiment_data.get("target_segment"):
            description_parts.append(f"Target segment: {segment}")
        
        if industry := experiment_data.get("industry"):
            description_parts.append(f"Industry: {industry}")
        
        if tags := experiment_data.get("tags"):
            description_parts.append(f"Tags: {', '.join(tags)}")
        
        return ". ".join(description_parts)
    
    def _generate_journey_description(self, journey_data: Dict[str, Any]) -> str:
        """Generate user journey description for embedding"""
        description_parts = []
        
        # Journey flow
        if steps := journey_data.get("journey_steps"):
            step_names = [step.get("step_name", "") for step in steps]
            description_parts.append(f"User journey: {' -> '.join(step_names)}")
        
        # User context
        if segment := journey_data.get("user_segment"):
            description_parts.append(f"User segment: {segment}")
        
        if device := journey_data.get("device_type"):
            description_parts.append(f"Device: {device}")
        
        # Session info
        if duration := journey_data.get("session_duration"):
            description_parts.append(f"Session duration: {duration} seconds")
        
        if outcome := journey_data.get("conversion_outcome"):
            description_parts.append(f"Outcome: {outcome}")
        
        if value := journey_data.get("value"):
            description_parts.append(f"Value: ${value:.2f}")
        
        return ". ".join(description_parts)
    
    def _generate_optimization_description(self, optimization_data: Dict[str, Any]) -> str:
        """Generate optimization pattern description for embedding"""
        description_parts = []
        
        if opt_type := optimization_data.get("optimization_type"):
            description_parts.append(f"Optimization type: {opt_type}")
        
        if strategy := optimization_data.get("strategy"):
            description_parts.append(f"Strategy: {strategy}")
        
        if improvement := optimization_data.get("improvement_percentage"):
            description_parts.append(f"Improvement: {improvement:.1f}%")
        
        if segments := optimization_data.get("applied_to_segments"):
            description_parts.append(f"Applied to segments: {', '.join(segments)}")
        
        if description := optimization_data.get("description"):
            description_parts.append(f"Description: {description}")
        
        return ". ".join(description_parts)
    
    def _generate_hash(self, text: str) -> str:
        """Generate consistent hash for text"""
        return hashlib.md5(text.encode()).hexdigest()[:8]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB health and collection status"""
        try:
            health_info = {
                "status": "healthy",
                "collections": {},
                "total_documents": 0
            }
            
            for collection_name, collection in self.collections.items():
                count = collection.count()
                health_info["collections"][collection_name] = {
                    "document_count": count,
                    "status": "active"
                }
                health_info["total_documents"] += count
            
            return health_info
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "collections": {},
                "total_documents": 0
            }
    
    async def close(self):
        """Clean up resources"""
        # ChromaDB client doesn't need explicit closing
        logger.info("ChromaDB manager closed")


# Global instance
vector_store = ExperimentVectorStore()
