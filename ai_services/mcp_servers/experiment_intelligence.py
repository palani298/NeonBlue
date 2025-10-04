# Experiment Intelligence MCP Server
"""
AI-powered experiment analysis and recommendations using Model Context Protocol (MCP).

This MCP server provides intelligent experiment analysis capabilities:
1. Semantic experiment analysis using ChromaDB similarity search
2. AI-powered performance insights and recommendations  
3. Statistical significance validation with contextual understanding
4. Experiment optimization suggestions based on historical patterns
5. Predictive analytics for experiment outcomes

The server connects to ChromaDB for semantic search, PostgreSQL for operational data,
and ClickHouse for analytics, providing a comprehensive AI-enhanced view of experiments.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
import openai
from contextlib import asynccontextmanager
from structlog import get_logger

from ..core.config import config
from ..core.chromadb_manager import vector_store


logger = get_logger(__name__)


class ExperimentAnalysisRequest(BaseModel):
    experiment_id: str
    analysis_type: str = "comprehensive"  # comprehensive, quick, predictive
    context: Optional[Dict[str, Any]] = None


class OptimizationRequest(BaseModel):
    experiment_id: str
    current_performance: Dict[str, Any]
    optimization_goals: List[str] = ["conversion_rate", "statistical_power"]


class ExperimentIntelligenceServer:
    """
    MCP Server for AI-powered experiment intelligence
    
    Provides tools for:
    - Analyzing experiment performance with AI insights
    - Finding similar experiments and patterns
    - Generating optimization recommendations
    - Predicting experiment outcomes
    - Statistical analysis with contextual understanding
    """
    
    def __init__(self):
        self.openai_client = None
        self.initialized = False
        
        # Analysis templates and prompts
        self.analysis_prompts = {
            "comprehensive": """
                Analyze this experiment data comprehensively:
                
                Experiment Data: {experiment_data}
                Similar Experiments: {similar_experiments}
                Performance Metrics: {performance_metrics}
                
                Provide insights on:
                1. Statistical significance and reliability
                2. Conversion rate patterns and trends
                3. User segment performance differences
                4. Comparison with similar experiments
                5. Key success/failure factors
                6. Actionable recommendations
                
                Focus on practical, data-driven insights.
            """,
            
            "optimization": """
                Based on this experiment data and similar successful experiments, 
                recommend specific optimizations:
                
                Current Experiment: {experiment_data}
                Current Performance: {performance_metrics}
                Successful Patterns: {success_patterns}
                Optimization Goals: {goals}
                
                Provide:
                1. Top 3 optimization recommendations
                2. Expected impact for each recommendation
                3. Implementation priority and effort
                4. Risk factors to consider
                5. Success metrics to track
                
                Be specific and actionable.
            """,
            
            "predictive": """
                Predict the likely outcome of this experiment:
                
                Experiment Configuration: {experiment_config}
                Historical Patterns: {historical_data}
                Similar Experiments: {similar_experiments}
                
                Predict:
                1. Likely conversion rate improvement
                2. Confidence level of success
                3. Optimal sample size and duration
                4. Key risk factors
                5. Early indicators to monitor
                
                Provide quantitative estimates where possible.
            """
        }
        
    async def initialize(self):
        """Initialize the MCP server"""
        try:
            # Initialize OpenAI client
            if config.openai_api_key:
                self.openai_client = openai.AsyncOpenAI(api_key=config.openai_api_key)
            else:
                logger.warning("No OpenAI API key provided - AI features will be limited")
            
            # Initialize ChromaDB connection
            if not vector_store.client:
                await vector_store.initialize()
            
            self.initialized = True
            logger.info("Experiment Intelligence MCP Server initialized")
            
        except Exception as e:
            logger.error("Failed to initialize Experiment Intelligence server", error=str(e))
            raise
    
    async def analyze_experiment_performance(self, experiment_id: str, 
                                           analysis_type: str = "comprehensive",
                                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze experiment performance with AI insights
        
        This is the main MCP tool for comprehensive experiment analysis
        """
        try:
            logger.info("Starting experiment analysis", 
                       experiment_id=experiment_id, 
                       analysis_type=analysis_type)
            
            # 1. Get experiment data from various sources
            experiment_data = await self._get_experiment_data(experiment_id)
            
            # 2. Find similar experiments using semantic search
            similar_experiments = await self._find_similar_experiments(experiment_data)
            
            # 3. Get performance metrics
            performance_metrics = await self._get_performance_metrics(experiment_id)
            
            # 4. Perform AI analysis
            ai_insights = await self._generate_ai_insights(
                experiment_data, similar_experiments, performance_metrics, analysis_type
            )
            
            # 5. Calculate statistical analysis
            statistical_analysis = await self._perform_statistical_analysis(
                experiment_data, performance_metrics
            )
            
            # 6. Generate recommendations
            recommendations = await self._generate_recommendations(
                experiment_data, similar_experiments, performance_metrics, ai_insights
            )
            
            analysis_result = {
                'experiment_id': experiment_id,
                'analysis_type': analysis_type,
                'experiment_data': experiment_data,
                'performance_metrics': performance_metrics,
                'similar_experiments': similar_experiments[:5],  # Top 5 most similar
                'ai_insights': ai_insights,
                'statistical_analysis': statistical_analysis,
                'recommendations': recommendations,
                'confidence_score': self._calculate_confidence_score(
                    statistical_analysis, len(similar_experiments)
                ),
                'analyzed_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Experiment analysis completed", 
                       experiment_id=experiment_id,
                       similar_experiments_found=len(similar_experiments),
                       confidence_score=analysis_result['confidence_score'])
            
            return analysis_result
            
        except Exception as e:
            logger.error("Experiment analysis failed", 
                        experiment_id=experiment_id, 
                        error=str(e))
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    async def recommend_experiment_optimization(self, experiment_id: str,
                                              current_performance: Dict[str, Any],
                                              optimization_goals: List[str]) -> Dict[str, Any]:
        """
        Generate AI-powered experiment optimization recommendations
        
        MCP tool for intelligent experiment optimization
        """
        try:
            logger.info("Generating optimization recommendations", 
                       experiment_id=experiment_id, 
                       goals=optimization_goals)
            
            # Get experiment data
            experiment_data = await self._get_experiment_data(experiment_id)
            
            # Find successful optimization patterns
            optimization_patterns = await self._find_optimization_patterns(
                experiment_data, optimization_goals
            )
            
            # Get similar successful experiments
            successful_experiments = await self._find_successful_experiments(
                experiment_data, min_improvement=0.1  # 10% minimum improvement
            )
            
            # Generate AI-powered recommendations
            ai_recommendations = await self._generate_optimization_recommendations(
                experiment_data, current_performance, optimization_patterns, 
                successful_experiments, optimization_goals
            )
            
            # Calculate expected impact
            impact_analysis = await self._calculate_expected_impact(
                current_performance, ai_recommendations, successful_experiments
            )
            
            optimization_result = {
                'experiment_id': experiment_id,
                'current_performance': current_performance,
                'optimization_goals': optimization_goals,
                'recommendations': ai_recommendations,
                'impact_analysis': impact_analysis,
                'successful_patterns': optimization_patterns[:10],  # Top 10 patterns
                'confidence_score': self._calculate_optimization_confidence(
                    len(optimization_patterns), len(successful_experiments)
                ),
                'generated_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Optimization recommendations generated", 
                       experiment_id=experiment_id,
                       recommendations_count=len(ai_recommendations),
                       confidence_score=optimization_result['confidence_score'])
            
            return optimization_result
            
        except Exception as e:
            logger.error("Optimization recommendation failed", 
                        experiment_id=experiment_id, 
                        error=str(e))
            raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
    
    async def predict_experiment_outcome(self, experiment_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict experiment outcome before running
        
        MCP tool for predictive experiment analysis
        """
        try:
            logger.info("Predicting experiment outcome", 
                       experiment_type=experiment_config.get('type'))
            
            # Find similar experiment patterns
            similar_experiments = await self._find_similar_experiments(experiment_config)
            
            # Get historical success patterns
            historical_data = await self._get_historical_patterns(experiment_config)
            
            # Generate AI prediction
            prediction = await self._generate_outcome_prediction(
                experiment_config, similar_experiments, historical_data
            )
            
            # Calculate statistical predictions
            statistical_prediction = await self._calculate_statistical_prediction(
                similar_experiments, historical_data
            )
            
            # Risk analysis
            risk_analysis = await self._analyze_risks(
                experiment_config, similar_experiments
            )
            
            prediction_result = {
                'experiment_config': experiment_config,
                'prediction': prediction,
                'statistical_prediction': statistical_prediction,
                'risk_analysis': risk_analysis,
                'similar_experiments': similar_experiments[:10],
                'confidence_score': self._calculate_prediction_confidence(
                    len(similar_experiments), statistical_prediction
                ),
                'predicted_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Experiment outcome predicted", 
                       predicted_outcome=prediction.get('outcome'),
                       confidence_score=prediction_result['confidence_score'])
            
            return prediction_result
            
        except Exception as e:
            logger.error("Outcome prediction failed", error=str(e))
            raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
    
    async def _get_experiment_data(self, experiment_id: str) -> Dict[str, Any]:
        """Get comprehensive experiment data from all sources"""
        # In a real implementation, this would query PostgreSQL
        # For now, return mock data
        return {
            'experiment_id': experiment_id,
            'name': f'Experiment {experiment_id}',
            'type': 'conversion_optimization',
            'status': 'running',
            'hypothesis': 'Improving checkout flow will increase conversion rates',
            'variants': [
                {'name': 'control', 'traffic_allocation': 0.5},
                {'name': 'treatment', 'traffic_allocation': 0.5}
            ],
            'target_segment': 'mobile_users',
            'industry': 'ecommerce',
            'created_at': datetime.utcnow().isoformat()
        }
    
    async def _find_similar_experiments(self, experiment_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar experiments using semantic search"""
        try:
            # Create search query from experiment data
            search_query = f"""
                {experiment_data.get('type', '')} experiment for {experiment_data.get('target_segment', 'all users')}
                in {experiment_data.get('industry', 'general')} industry.
                Hypothesis: {experiment_data.get('hypothesis', '')}
            """
            
            # Search ChromaDB for similar experiments
            results = await vector_store.semantic_search(
                query=search_query,
                collection_name=config.experiments_collection,
                n_results=20,
                filters={'outcome': {'$in': ['success', 'failure', 'neutral']}}
            )
            
            return results.get('results', [])
            
        except Exception as e:
            logger.warning("Failed to find similar experiments", error=str(e))
            return []
    
    async def _get_performance_metrics(self, experiment_id: str) -> Dict[str, Any]:
        """Get experiment performance metrics"""
        # Mock performance data - in reality, query ClickHouse
        return {
            'conversion_rate': {
                'control': 0.12,
                'treatment': 0.15
            },
            'sample_size': {
                'control': 5000,
                'treatment': 5000
            },
            'statistical_significance': 0.95,
            'p_value': 0.032,
            'confidence_interval': {'lower': 0.01, 'upper': 0.05},
            'effect_size': 0.25
        }
    
    async def _generate_ai_insights(self, experiment_data: Dict[str, Any], 
                                  similar_experiments: List[Dict[str, Any]],
                                  performance_metrics: Dict[str, Any],
                                  analysis_type: str) -> Dict[str, Any]:
        """Generate AI insights using OpenAI"""
        if not self.openai_client:
            return {'insights': 'AI analysis unavailable - no API key', 'confidence': 0.0}
        
        try:
            prompt = self.analysis_prompts[analysis_type].format(
                experiment_data=json.dumps(experiment_data, indent=2),
                similar_experiments=json.dumps([exp['metadata'] for exp in similar_experiments[:5]], indent=2),
                performance_metrics=json.dumps(performance_metrics, indent=2)
            )
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert data scientist analyzing A/B test experiments. Provide clear, actionable insights based on statistical analysis and historical patterns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            insights_text = response.choices[0].message.content
            
            return {
                'insights': insights_text,
                'confidence': 0.8,
                'model_used': 'gpt-4',
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to generate AI insights", error=str(e))
            return {
                'insights': f'AI analysis failed: {str(e)}',
                'confidence': 0.0
            }
    
    async def _perform_statistical_analysis(self, experiment_data: Dict[str, Any],
                                          performance_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Perform statistical analysis of experiment results"""
        try:
            # Extract metrics
            control_rate = performance_metrics.get('conversion_rate', {}).get('control', 0)
            treatment_rate = performance_metrics.get('conversion_rate', {}).get('treatment', 0)
            control_size = performance_metrics.get('sample_size', {}).get('control', 0)
            treatment_size = performance_metrics.get('sample_size', {}).get('treatment', 0)
            
            # Calculate lift
            if control_rate > 0:
                lift = (treatment_rate - control_rate) / control_rate
                lift_percentage = lift * 100
            else:
                lift = 0
                lift_percentage = 0
            
            # Statistical power calculation (simplified)
            total_sample = control_size + treatment_size
            statistical_power = min(0.99, max(0.05, total_sample / 10000))
            
            # Significance assessment
            p_value = performance_metrics.get('p_value', 0.5)
            is_significant = p_value < 0.05
            
            return {
                'lift_percentage': round(lift_percentage, 2),
                'absolute_lift': round(treatment_rate - control_rate, 4),
                'statistical_power': round(statistical_power, 3),
                'is_statistically_significant': is_significant,
                'p_value': p_value,
                'confidence_level': performance_metrics.get('statistical_significance', 0.95),
                'sample_size_total': total_sample,
                'sample_size_adequacy': 'adequate' if total_sample > 1000 else 'insufficient',
                'recommendation': 'implement' if is_significant and lift > 0 else 'continue_testing'
            }
            
        except Exception as e:
            logger.error("Statistical analysis failed", error=str(e))
            return {'error': str(e)}
    
    async def _generate_recommendations(self, experiment_data: Dict[str, Any],
                                      similar_experiments: List[Dict[str, Any]],
                                      performance_metrics: Dict[str, Any],
                                      ai_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Statistical recommendations
        if performance_metrics.get('is_statistically_significant'):
            if performance_metrics.get('lift_percentage', 0) > 0:
                recommendations.append({
                    'type': 'implementation',
                    'priority': 'high',
                    'title': 'Implement winning variant',
                    'description': f"Treatment variant shows {performance_metrics.get('lift_percentage', 0):.1f}% improvement",
                    'expected_impact': 'positive',
                    'confidence': 0.9
                })
        
        # Sample size recommendations
        total_sample = performance_metrics.get('sample_size_total', 0)
        if total_sample < 1000:
            recommendations.append({
                'type': 'sample_size',
                'priority': 'medium',
                'title': 'Increase sample size',
                'description': f'Current sample size ({total_sample}) may be insufficient for reliable results',
                'expected_impact': 'improved_reliability',
                'confidence': 0.8
            })
        
        # Similar experiment recommendations
        successful_similar = [exp for exp in similar_experiments 
                             if exp['metadata'].get('outcome') == 'success']
        if successful_similar:
            recommendations.append({
                'type': 'optimization',
                'priority': 'medium',
                'title': 'Apply successful patterns',
                'description': f'Found {len(successful_similar)} similar successful experiments with applicable patterns',
                'expected_impact': 'increased_success_probability',
                'confidence': 0.7
            })
        
        return recommendations
    
    async def _find_optimization_patterns(self, experiment_data: Dict[str, Any],
                                        optimization_goals: List[str]) -> List[Dict[str, Any]]:
        """Find successful optimization patterns"""
        try:
            search_query = f"successful optimization {' '.join(optimization_goals)} {experiment_data.get('type', '')}"
            
            results = await vector_store.semantic_search(
                query=search_query,
                collection_name=config.optimization_patterns_collection,
                n_results=20,
                filters={'outcome': 'success'}
            )
            
            return results.get('results', [])
            
        except Exception as e:
            logger.warning("Failed to find optimization patterns", error=str(e))
            return []
    
    async def _find_successful_experiments(self, experiment_data: Dict[str, Any],
                                         min_improvement: float = 0.1) -> List[Dict[str, Any]]:
        """Find similar successful experiments"""
        try:
            search_query = f"successful {experiment_data.get('type', '')} experiment {experiment_data.get('industry', '')}"
            
            results = await vector_store.semantic_search(
                query=search_query,
                collection_name=config.experiments_collection,
                n_results=30,
                filters={
                    'outcome': 'success',
                    'improvement_percentage': {'$gte': min_improvement * 100}
                }
            )
            
            return results.get('results', [])
            
        except Exception as e:
            logger.warning("Failed to find successful experiments", error=str(e))
            return []
    
    async def _generate_optimization_recommendations(self, experiment_data: Dict[str, Any],
                                                   current_performance: Dict[str, Any],
                                                   optimization_patterns: List[Dict[str, Any]],
                                                   successful_experiments: List[Dict[str, Any]],
                                                   goals: List[str]) -> List[Dict[str, Any]]:
        """Generate AI-powered optimization recommendations"""
        if not self.openai_client:
            return [{'recommendation': 'AI optimization unavailable', 'confidence': 0.0}]
        
        try:
            prompt = self.analysis_prompts["optimization"].format(
                experiment_data=json.dumps(experiment_data, indent=2),
                performance_metrics=json.dumps(current_performance, indent=2),
                success_patterns=json.dumps([p['metadata'] for p in optimization_patterns[:5]], indent=2),
                goals=', '.join(goals)
            )
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert conversion optimization specialist. Provide specific, actionable recommendations based on successful patterns and current performance data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse the AI response into structured recommendations
            recommendations_text = response.choices[0].message.content
            
            # For now, return as single recommendation - could be enhanced to parse into multiple
            return [{
                'type': 'ai_optimization',
                'priority': 'high',
                'recommendations': recommendations_text,
                'confidence': 0.8,
                'generated_at': datetime.utcnow().isoformat()
            }]
            
        except Exception as e:
            logger.error("Failed to generate optimization recommendations", error=str(e))
            return [{'error': str(e), 'confidence': 0.0}]
    
    async def _calculate_expected_impact(self, current_performance: Dict[str, Any],
                                       recommendations: List[Dict[str, Any]],
                                       successful_experiments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate expected impact of recommendations"""
        if not successful_experiments:
            return {'expected_lift': 0.0, 'confidence': 0.0}
        
        # Calculate average improvement from similar successful experiments
        improvements = []
        for exp in successful_experiments:
            metadata = exp.get('metadata', {})
            improvement = metadata.get('improvement_percentage', 0)
            if improvement > 0:
                improvements.append(improvement / 100)  # Convert to decimal
        
        if improvements:
            avg_improvement = statistics.mean(improvements)
            improvement_std = statistics.stdev(improvements) if len(improvements) > 1 else 0.1
            
            return {
                'expected_lift_percentage': round(avg_improvement * 100, 1),
                'confidence_interval': {
                    'lower': round((avg_improvement - improvement_std) * 100, 1),
                    'upper': round((avg_improvement + improvement_std) * 100, 1)
                },
                'confidence': min(0.9, len(improvements) / 10),
                'based_on_experiments': len(improvements)
            }
        
        return {'expected_lift_percentage': 0.0, 'confidence': 0.0}
    
    def _calculate_confidence_score(self, statistical_analysis: Dict[str, Any], 
                                  similar_experiments_count: int) -> float:
        """Calculate overall confidence score for analysis"""
        confidence_factors = []
        
        # Statistical confidence
        if statistical_analysis.get('statistical_power', 0) > 0.8:
            confidence_factors.append(0.3)
        elif statistical_analysis.get('statistical_power', 0) > 0.5:
            confidence_factors.append(0.2)
        else:
            confidence_factors.append(0.1)
        
        # Sample size confidence
        sample_size = statistical_analysis.get('sample_size_total', 0)
        if sample_size > 5000:
            confidence_factors.append(0.3)
        elif sample_size > 1000:
            confidence_factors.append(0.2)
        else:
            confidence_factors.append(0.1)
        
        # Similar experiments confidence
        if similar_experiments_count > 10:
            confidence_factors.append(0.4)
        elif similar_experiments_count > 5:
            confidence_factors.append(0.3)
        else:
            confidence_factors.append(0.2)
        
        return min(1.0, sum(confidence_factors))
    
    def _calculate_optimization_confidence(self, patterns_count: int, 
                                         successful_experiments_count: int) -> float:
        """Calculate confidence for optimization recommendations"""
        base_confidence = 0.5
        
        # Boost based on patterns found
        pattern_boost = min(0.3, patterns_count * 0.03)
        
        # Boost based on successful experiments
        success_boost = min(0.2, successful_experiments_count * 0.02)
        
        return min(1.0, base_confidence + pattern_boost + success_boost)
    
    def _calculate_prediction_confidence(self, similar_experiments_count: int,
                                       statistical_prediction: Dict[str, Any]) -> float:
        """Calculate confidence for outcome prediction"""
        base_confidence = 0.4
        
        # Similar experiments boost
        similar_boost = min(0.4, similar_experiments_count * 0.04)
        
        # Statistical model confidence
        stat_confidence = statistical_prediction.get('confidence', 0.5) * 0.2
        
        return min(1.0, base_confidence + similar_boost + stat_confidence)
    
    async def _get_historical_patterns(self, experiment_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical patterns for prediction"""
        # Mock historical data - would query ClickHouse in reality
        return {
            'success_rate': 0.65,
            'average_lift': 0.15,
            'common_failure_reasons': ['insufficient_sample_size', 'poor_targeting'],
            'optimal_duration_days': 14
        }
    
    async def _generate_outcome_prediction(self, experiment_config: Dict[str, Any],
                                         similar_experiments: List[Dict[str, Any]],
                                         historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered outcome prediction"""
        if not self.openai_client:
            return {'outcome': 'unknown', 'confidence': 0.0}
        
        try:
            prompt = self.analysis_prompts["predictive"].format(
                experiment_config=json.dumps(experiment_config, indent=2),
                historical_data=json.dumps(historical_data, indent=2),
                similar_experiments=json.dumps([exp['metadata'] for exp in similar_experiments[:5]], indent=2)
            )
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a predictive analytics expert specializing in A/B test outcomes. Provide quantitative predictions with confidence levels."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=600
            )
            
            prediction_text = response.choices[0].message.content
            
            return {
                'prediction': prediction_text,
                'confidence': 0.75,
                'model_used': 'gpt-4'
            }
            
        except Exception as e:
            logger.error("Failed to generate outcome prediction", error=str(e))
            return {'outcome': f'Prediction failed: {str(e)}', 'confidence': 0.0}
    
    async def _calculate_statistical_prediction(self, similar_experiments: List[Dict[str, Any]],
                                              historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistical prediction based on historical data"""
        if not similar_experiments:
            return {'predicted_outcome': 'unknown', 'confidence': 0.0}
        
        # Analyze outcomes of similar experiments
        outcomes = [exp['metadata'].get('outcome', 'unknown') for exp in similar_experiments]
        success_count = outcomes.count('success')
        total_count = len([o for o in outcomes if o != 'unknown'])
        
        if total_count == 0:
            return {'predicted_outcome': 'unknown', 'confidence': 0.0}
        
        success_rate = success_count / total_count
        historical_success_rate = historical_data.get('success_rate', 0.5)
        
        # Weighted prediction
        predicted_success_rate = (success_rate * 0.7) + (historical_success_rate * 0.3)
        
        return {
            'predicted_outcome': 'success' if predicted_success_rate > 0.6 else 'neutral' if predicted_success_rate > 0.4 else 'failure',
            'success_probability': round(predicted_success_rate, 3),
            'confidence': min(0.9, total_count / 10),
            'based_on_similar_experiments': total_count,
            'historical_success_rate': historical_success_rate
        }
    
    async def _analyze_risks(self, experiment_config: Dict[str, Any],
                           similar_experiments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze potential risks for the experiment"""
        risks = []
        
        # Sample size risk
        proposed_duration = experiment_config.get('duration_days', 14)
        if proposed_duration < 7:
            risks.append({
                'type': 'sample_size',
                'severity': 'medium',
                'description': 'Short experiment duration may lead to insufficient sample size',
                'mitigation': 'Consider extending to at least 14 days'
            })
        
        # Seasonality risk
        if experiment_config.get('industry') == 'ecommerce':
            risks.append({
                'type': 'seasonality',
                'severity': 'low',
                'description': 'E-commerce experiments may be affected by seasonal patterns',
                'mitigation': 'Monitor for seasonal effects and adjust analysis accordingly'
            })
        
        # Failed similar experiments
        failed_similar = [exp for exp in similar_experiments 
                         if exp['metadata'].get('outcome') == 'failure']
        if len(failed_similar) > len(similar_experiments) * 0.4:
            risks.append({
                'type': 'historical_failure',
                'severity': 'high',
                'description': f'{len(failed_similar)} out of {len(similar_experiments)} similar experiments failed',
                'mitigation': 'Review failure patterns and adjust experiment design'
            })
        
        return {
            'risk_count': len(risks),
            'overall_risk_level': 'high' if any(r['severity'] == 'high' for r in risks) else 'medium' if risks else 'low',
            'risks': risks
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the MCP server"""
        return {
            'status': 'healthy' if self.initialized else 'initializing',
            'openai_available': self.openai_client is not None,
            'chromadb_available': vector_store.client is not None,
            'initialized': self.initialized
        }


# Global server instance
intelligence_server = ExperimentIntelligenceServer()


# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    await intelligence_server.initialize()
    yield


app = FastAPI(
    title="Experiment Intelligence MCP Server",
    description="AI-powered experiment analysis and optimization recommendations",
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


# MCP Tool Endpoints
@app.post("/analyze_experiment_performance")
async def analyze_experiment_performance(request: ExperimentAnalysisRequest):
    """MCP Tool: Analyze experiment performance with AI insights"""
    return await intelligence_server.analyze_experiment_performance(
        request.experiment_id, request.analysis_type, request.context
    )


@app.post("/recommend_experiment_optimization")
async def recommend_experiment_optimization(request: OptimizationRequest):
    """MCP Tool: Generate experiment optimization recommendations"""
    return await intelligence_server.recommend_experiment_optimization(
        request.experiment_id, request.current_performance, request.optimization_goals
    )


@app.post("/predict_experiment_outcome")
async def predict_experiment_outcome(experiment_config: Dict[str, Any]):
    """MCP Tool: Predict experiment outcome before running"""
    return await intelligence_server.predict_experiment_outcome(experiment_config)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await intelligence_server.health_check()


if __name__ == "__main__":
    uvicorn.run(
        "ai_services.mcp_servers.experiment_intelligence:app",
        host="0.0.0.0",
        port=config.mcp_port,
        log_level=config.log_level.lower()
    )
