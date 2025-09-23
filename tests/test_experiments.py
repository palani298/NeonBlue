"""Tests for experiment endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestExperiments:
    """Test experiment CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_experiment(
        self, 
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test creating a new experiment."""
        response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == sample_experiment_data["key"]
        assert data["name"] == sample_experiment_data["name"]
        assert data["status"] == "draft"
        assert len(data["variants"]) == 2
        assert data["id"] is not None
    
    @pytest.mark.asyncio
    async def test_get_experiment(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test getting an experiment by ID."""
        # Create experiment first
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        # Get the experiment
        response = await test_client.get(f"/api/v1/experiments/{experiment_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == experiment_id
        assert data["key"] == sample_experiment_data["key"]
    
    @pytest.mark.asyncio
    async def test_list_experiments(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test listing experiments."""
        # Create multiple experiments
        for i in range(3):
            exp_data = sample_experiment_data.copy()
            exp_data["key"] = f"test_experiment_{i}"
            await test_client.post("/api/v1/experiments", json=exp_data)
        
        # List experiments
        response = await test_client.get("/api/v1/experiments")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
    
    @pytest.mark.asyncio
    async def test_activate_experiment(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test activating an experiment."""
        # Create experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        # Activate experiment
        response = await test_client.post(
            f"/api/v1/experiments/{experiment_id}/activate"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["version"] == 2  # Version should increment
    
    @pytest.mark.asyncio
    async def test_duplicate_experiment_key(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict
    ):
        """Test that duplicate experiment keys are rejected."""
        # Create first experiment
        response1 = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        assert response1.status_code == 201
        
        # Try to create duplicate
        response2 = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_variant_allocation(
        self,
        test_client: AsyncClient
    ):
        """Test that invalid variant allocations are rejected."""
        invalid_data = {
            "key": "invalid_experiment",
            "name": "Invalid Experiment",
            "variants": [
                {
                    "key": "control",
                    "name": "Control",
                    "allocation_pct": 60,
                    "is_control": True
                },
                {
                    "key": "treatment",
                    "name": "Treatment",
                    "allocation_pct": 60,  # Total > 100%
                    "is_control": False
                }
            ]
        }
        
        response = await test_client.post(
            "/api/v1/experiments",
            json=invalid_data
        )
        assert response.status_code == 400
