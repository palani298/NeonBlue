"""Tests for event tracking endpoints."""

import pytest
from httpx import AsyncClient


class TestEvents:
    """Test event tracking functionality."""
    
    @pytest.mark.asyncio
    async def test_record_event(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        sample_event_data: dict
    ):
        """Test recording a single event."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Update event data with experiment ID
        sample_event_data["experiment_id"] = experiment_id
        
        # Record event
        response = await test_client.post(
            "/api/v1/events",
            json=sample_event_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["experiment_id"] == experiment_id
        assert data["user_id"] == sample_event_data["user_id"]
        assert data["event_type"] == sample_event_data["event_type"]
        assert data["properties"] == sample_event_data["properties"]
    
    @pytest.mark.asyncio
    async def test_batch_events(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test recording batch events."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Create batch of events
        events = [
            {
                "experiment_id": experiment_id,
                "user_id": f"user_{i}",
                "event_type": "click" if i % 2 == 0 else "conversion",
                "properties": {"source": "test"}
            }
            for i in range(10)
        ]
        
        # Record batch
        response = await test_client.post(
            "/api/v1/events/batch",
            json={"events": events}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success_count"] == 10
        assert data["error_count"] == 0
    
    @pytest.mark.asyncio
    async def test_event_with_assignment(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test that events automatically create assignments."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        user_id = "event_user_123"
        
        # Record event (should create assignment)
        event_response = await test_client.post(
            "/api/v1/events",
            json={
                "experiment_id": experiment_id,
                "user_id": user_id,
                "event_type": "pageview",
                "properties": {}
            }
        )
        assert event_response.status_code == 201
        
        # Check that assignment was created
        assignment_response = await test_client.get(
            f"/api/v1/experiments/{experiment_id}/assignment/{user_id}"
        )
        assert assignment_response.status_code == 200
        assert assignment_response.json()["user_id"] == user_id
    
    @pytest.mark.asyncio
    async def test_invalid_experiment_event(
        self,
        test_client: AsyncClient
    ):
        """Test that events for non-existent experiments are rejected."""
        response = await test_client.post(
            "/api/v1/events",
            json={
                "experiment_id": 99999,
                "user_id": "test_user",
                "event_type": "click",
                "properties": {}
            }
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_event_properties_validation(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test that event properties are properly stored."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Complex properties
        properties = {
            "page": "homepage",
            "button": "cta",
            "position": 1,
            "timestamp": 1234567890,
            "metadata": {
                "browser": "chrome",
                "version": "120.0"
            }
        }
        
        response = await test_client.post(
            "/api/v1/events",
            json={
                "experiment_id": experiment_id,
                "user_id": "property_test_user",
                "event_type": "click",
                "properties": properties
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["properties"] == properties