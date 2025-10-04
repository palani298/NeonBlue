# Routing Engine - Intelligent destination selection for data routing
"""
The Routing Engine takes classified data and makes intelligent decisions about
where to route it based on:

1. Data classification results
2. System load and performance metrics
3. Business rules and priorities
4. Real-time vs batch processing requirements

It outputs a prioritized list of destinations for each data item.
"""

from typing import Dict, Any, List, Optional, Set
from enum import Enum
import asyncio
from datetime import datetime, timedelta
from structlog import get_logger

from .data_classifier import DataType, ProcessingType, StorageType

logger = get_logger(__name__)


class RoutingDecision(Enum):
    """Routing decision types"""
    PRIMARY = "primary"        # Must route here
    SECONDARY = "secondary"    # Should route here if possible
    OPTIONAL = "optional"      # Route here if beneficial
    SKIP = "skip"             # Don't route here


class RoutingEngine:
    """
    Intelligent routing engine that determines optimal data destinations
    
    Makes routing decisions based on:
    - Data classification
    - System performance and load
    - Business priorities and SLA requirements
    - Historical routing success patterns
    """
    
    def __init__(self):
        self.routing_rules = self._load_routing_rules()
        self.system_metrics = {}
        self.routing_history = []
        self.load_balancer_state = {}
        
    async def determine_destinations(self, data: Dict[str, Any], 
                                   classification: Dict[str, Any]) -> List[str]:
        """
        Determine optimal routing destinations for classified data
        
        Args:
            data: Original data payload
            classification: Data classification results
            
        Returns:
            List of destination names in priority order
        """
        try:
            # Get basic routing from classification
            storage_types = classification.get('storage_types', [])
            data_type = classification.get('data_type')
            priority = classification.get('priority', 5)
            ai_enhanced = classification.get('ai_enhanced', False)
            
            # Map storage types to destinations
            destinations = []
            routing_decisions = {}
            
            # Evaluate each potential destination
            for storage_type in storage_types:
                decision = await self._evaluate_destination(storage_type, data, classification)
                routing_decisions[storage_type] = decision
                
                if decision in [RoutingDecision.PRIMARY, RoutingDecision.SECONDARY]:
                    destinations.append(self._storage_type_to_destination(storage_type))
            
            # Add AI-enhanced destinations
            if ai_enhanced:
                destinations.append('chromadb')
                
            # Apply business rules and filters
            destinations = self._apply_business_rules(destinations, data, classification)
            
            # Load balancing and performance optimization
            destinations = await self._optimize_routing(destinations, data, classification)
            
            # Remove duplicates while preserving order
            final_destinations = list(dict.fromkeys(destinations))
            
            # Log routing decision
            logger.info("Routing destinations determined",
                       data_type=data_type,
                       destinations=final_destinations,
                       priority=priority,
                       routing_decisions=routing_decisions)
            
            return final_destinations
            
        except Exception as e:
            logger.error("Failed to determine routing destinations", error=str(e))
            # Return safe default
            return ['postgresql']
    
    async def _evaluate_destination(self, storage_type: str, data: Dict[str, Any], 
                                  classification: Dict[str, Any]) -> RoutingDecision:
        """Evaluate whether to route to a specific destination"""
        
        data_type = classification.get('data_type')
        priority = classification.get('priority', 5)
        processing_type = classification.get('processing_type')
        
        # Core routing logic based on storage type
        if storage_type == 'operational':
            # PostgreSQL is primary for operational data
            if data_type in ['experiment', 'assignment', 'user_data']:
                return RoutingDecision.PRIMARY
            return RoutingDecision.OPTIONAL
            
        elif storage_type == 'analytical':
            # ClickHouse is primary for analytics
            if data_type in ['event', 'analytics']:
                return RoutingDecision.PRIMARY
            if processing_type == 'batch':
                return RoutingDecision.SECONDARY
            return RoutingDecision.SKIP
            
        elif storage_type == 'semantic':
            # ChromaDB for AI-enhanced data
            if classification.get('ai_enhanced', False):
                return RoutingDecision.PRIMARY
            if data_type in ['experiment', 'optimization']:
                return RoutingDecision.SECONDARY
            return RoutingDecision.OPTIONAL
            
        elif storage_type == 'cache':
            # Redis for high-frequency access
            if priority <= 3:  # High priority
                return RoutingDecision.PRIMARY
            if data_type in ['assignment', 'user_data']:
                return RoutingDecision.SECONDARY
            return RoutingDecision.OPTIONAL
            
        return RoutingDecision.SKIP
    
    def _storage_type_to_destination(self, storage_type: str) -> str:
        """Map storage types to actual destination names"""
        mapping = {
            'operational': 'postgresql',
            'analytical': 'clickhouse', 
            'semantic': 'chromadb',
            'cache': 'redis'
        }
        return mapping.get(storage_type, 'postgresql')
    
    def _apply_business_rules(self, destinations: List[str], data: Dict[str, Any], 
                            classification: Dict[str, Any]) -> List[str]:
        """Apply business rules to filter and prioritize destinations"""
        
        data_type = classification.get('data_type')
        priority = classification.get('priority', 5)
        
        # Business rule 1: Critical data must go to operational store
        if priority <= 2:  # Critical priority
            if 'postgresql' not in destinations:
                destinations.insert(0, 'postgresql')
        
        # Business rule 2: Experiment data always gets semantic storage
        if data_type == 'experiment':
            if 'chromadb' not in destinations:
                destinations.append('chromadb')
        
        # Business rule 3: Events always get analytical storage
        if data_type == 'event':
            if 'clickhouse' not in destinations:
                destinations.append('clickhouse')
        
        # Business rule 4: Limit destinations for low priority data
        if priority >= 8:  # Low priority
            destinations = destinations[:2]  # Max 2 destinations
        
        # Business rule 5: Real-time data prioritization
        if classification.get('processing_type') == 'real_time':
            # Move operational stores to front
            operational_stores = ['postgresql', 'redis']
            reordered = []
            for store in operational_stores:
                if store in destinations:
                    reordered.append(store)
                    destinations.remove(store)
            destinations = reordered + destinations
        
        return destinations
    
    async def _optimize_routing(self, destinations: List[str], data: Dict[str, Any], 
                              classification: Dict[str, Any]) -> List[str]:
        """Optimize routing based on system performance and load"""
        
        if not destinations:
            return destinations
            
        # Get current system metrics
        system_load = await self._get_system_metrics()
        
        # Filter out overloaded destinations
        optimized_destinations = []
        for destination in destinations:
            load = system_load.get(destination, {}).get('load', 0.5)
            
            # Skip if destination is overloaded (unless critical)
            if load > 0.9 and classification.get('priority', 5) > 3:
                logger.warning(f"Skipping overloaded destination: {destination}", load=load)
                continue
                
            optimized_destinations.append(destination)
        
        # Ensure we have at least one destination
        if not optimized_destinations and destinations:
            optimized_destinations = [destinations[0]]  # Use first destination as fallback
            
        # Load balancing for multiple similar destinations
        optimized_destinations = self._apply_load_balancing(optimized_destinations, system_load)
        
        return optimized_destinations
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics"""
        # In a real implementation, this would query actual system metrics
        # For now, return simulated metrics
        return {
            'postgresql': {'load': 0.3, 'response_time': 50, 'available': True},
            'clickhouse': {'load': 0.6, 'response_time': 120, 'available': True},
            'chromadb': {'load': 0.4, 'response_time': 200, 'available': True},
            'redis': {'load': 0.2, 'response_time': 5, 'available': True}
        }
    
    def _apply_load_balancing(self, destinations: List[str], 
                            system_load: Dict[str, Any]) -> List[str]:
        """Apply load balancing for similar destination types"""
        
        # Group similar destinations
        analytical_stores = [d for d in destinations if d in ['clickhouse']]
        semantic_stores = [d for d in destinations if d in ['chromadb']]
        operational_stores = [d for d in destinations if d in ['postgresql']]
        cache_stores = [d for d in destinations if d in ['redis']]
        
        balanced_destinations = []
        
        # Sort each group by load (lowest first)
        for store_group in [operational_stores, cache_stores, analytical_stores, semantic_stores]:
            if store_group:
                sorted_group = sorted(store_group, 
                                    key=lambda x: system_load.get(x, {}).get('load', 1.0))
                balanced_destinations.extend(sorted_group)
        
        return balanced_destinations
    
    def _load_routing_rules(self) -> Dict[str, Any]:
        """Load routing rules configuration"""
        return {
            'max_destinations_per_request': 4,
            'critical_priority_threshold': 3,
            'overload_threshold': 0.9,
            'preferred_destinations': {
                'real_time': ['postgresql', 'redis'],
                'batch': ['clickhouse', 'chromadb'],
                'ai_enhanced': ['chromadb']
            },
            'fallback_destinations': ['postgresql'],
            'load_balancing_enabled': True
        }
    
    async def record_routing_result(self, routing_id: str, destinations: List[str], 
                                  results: Dict[str, Any]):
        """Record routing results for learning and optimization"""
        routing_record = {
            'routing_id': routing_id,
            'destinations': destinations,
            'results': results,
            'timestamp': datetime.utcnow().isoformat(),
            'success_rate': self._calculate_success_rate(results),
            'average_response_time': self._calculate_avg_response_time(results)
        }
        
        # Store in routing history (limited size)
        self.routing_history.append(routing_record)
        if len(self.routing_history) > 1000:
            self.routing_history = self.routing_history[-1000:]
        
        # Update load balancer state
        await self._update_load_balancer_state(routing_record)
    
    def _calculate_success_rate(self, results: Dict[str, Any]) -> float:
        """Calculate success rate from routing results"""
        if not results:
            return 0.0
            
        successful = sum(1 for r in results.values() if r.get('status') == 'success')
        total = len(results)
        
        return successful / total if total > 0 else 0.0
    
    def _calculate_avg_response_time(self, results: Dict[str, Any]) -> float:
        """Calculate average response time from routing results"""
        response_times = []
        
        for result in results.values():
            if 'response_time' in result:
                response_times.append(result['response_time'])
        
        return sum(response_times) / len(response_times) if response_times else 0.0
    
    async def _update_load_balancer_state(self, routing_record: Dict[str, Any]):
        """Update load balancer state based on routing results"""
        for destination in routing_record['destinations']:
            if destination not in self.load_balancer_state:
                self.load_balancer_state[destination] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'total_response_time': 0.0,
                    'last_updated': datetime.utcnow()
                }
            
            state = self.load_balancer_state[destination]
            result = routing_record['results'].get(destination, {})
            
            state['total_requests'] += 1
            if result.get('status') == 'success':
                state['successful_requests'] += 1
            
            if 'response_time' in result:
                state['total_response_time'] += result['response_time']
            
            state['last_updated'] = datetime.utcnow()
    
    async def get_routing_analytics(self) -> Dict[str, Any]:
        """Get analytics about routing performance"""
        if not self.routing_history:
            return {'status': 'no_data'}
        
        recent_history = [
            r for r in self.routing_history 
            if datetime.fromisoformat(r['timestamp']) > datetime.utcnow() - timedelta(hours=24)
        ]
        
        if not recent_history:
            return {'status': 'no_recent_data'}
        
        # Calculate analytics
        total_routings = len(recent_history)
        avg_success_rate = sum(r['success_rate'] for r in recent_history) / total_routings
        avg_destinations_per_routing = sum(len(r['destinations']) for r in recent_history) / total_routings
        
        # Destination usage
        destination_usage = {}
        for record in recent_history:
            for destination in record['destinations']:
                destination_usage[destination] = destination_usage.get(destination, 0) + 1
        
        return {
            'status': 'healthy',
            'period': '24h',
            'total_routings': total_routings,
            'average_success_rate': avg_success_rate,
            'average_destinations_per_routing': avg_destinations_per_routing,
            'destination_usage': destination_usage,
            'load_balancer_state': self.load_balancer_state.copy()
        }
