"""Tests for assignment endpoints and logic."""

import pytest
from httpx import AsyncClient


class TestAssignments:
    """Test user assignment functionality."""
    
    @pytest.mark.asyncio
    async def test_get_assignment(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        clean_redis
    ):
        """Test getting user assignment."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Get assignment
        response = await test_client.get(
            f"/api/v1/experiments/{experiment_id}/assignment/user123"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["experiment_id"] == experiment_id
        assert data["user_id"] == "user123"
        assert data["variant_key"] in ["control", "treatment"]
        assert data["enrolled"] is False
    
    @pytest.mark.asyncio
    async def test_assignment_idempotency(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        clean_redis
    ):
        """Test that assignments are idempotent."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Get assignment multiple times
        assignments = []
        for _ in range(5):
            response = await test_client.get(
                f"/api/v1/experiments/{experiment_id}/assignment/user456"
            )
            assignments.append(response.json()["variant_key"])
        
        # All assignments should be the same
        assert len(set(assignments)) == 1
    
    @pytest.mark.asyncio
    async def test_enrollment(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        clean_redis
    ):
        """Test user enrollment."""
        # Create and activate experiment
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Get assignment without enrollment
        response1 = await test_client.get(
            f"/api/v1/experiments/{experiment_id}/assignment/user789"
        )
        assert response1.json()["enrolled"] is False
        
        # Get assignment with enrollment
        response2 = await test_client.get(
            f"/api/v1/experiments/{experiment_id}/assignment/user789?enroll=true"
        )
        assert response2.json()["enrolled"] is True
        
        # Verify enrollment persists
        response3 = await test_client.get(
            f"/api/v1/experiments/{experiment_id}/assignment/user789"
        )
        assert response3.json()["enrolled"] is True
    
    @pytest.mark.asyncio
    async def test_bulk_assignments(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        clean_redis
    ):
        """Test bulk assignment endpoint."""
        # Create multiple experiments
        experiment_ids = []
        for i in range(3):
            exp_data = sample_experiment_data.copy()
            exp_data["key"] = f"bulk_test_{i}"
            create_response = await test_client.post(
                "/api/v1/experiments",
                json=exp_data
            )
            exp_id = create_response.json()["id"]
            await test_client.post(f"/api/v1/experiments/{exp_id}/activate")
            experiment_ids.append(exp_id)
        
        # Get bulk assignments
        response = await test_client.post(
            "/api/v1/assignments/bulk",
            json={
                "user_id": "bulk_user",
                "experiment_ids": experiment_ids
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["assignments"]) == 3
        
        # Verify each assignment
        for assignment in data["assignments"]:
            assert assignment["experiment_id"] in experiment_ids
            assert assignment["user_id"] == "bulk_user"
            assert assignment["variant_key"] in ["control", "treatment"]
    
    @pytest.mark.asyncio
    async def test_assignment_distribution(
        self,
        test_client: AsyncClient,
        sample_experiment_data: dict,
        clean_redis
    ):
        """Test that assignment distribution roughly matches allocation percentages."""
        # Create experiment with specific allocations
        create_response = await test_client.post(
            "/api/v1/experiments",
            json=sample_experiment_data
        )
        experiment_id = create_response.json()["id"]
        
        await test_client.post(f"/api/v1/experiments/{experiment_id}/activate")
        
        # Get assignments for many users
        assignments = {"control": 0, "treatment": 0}
        for i in range(1000):
            response = await test_client.get(
                f"/api/v1/experiments/{experiment_id}/assignment/user_{i}"
            )
            variant = response.json()["variant_key"]
            assignments[variant] += 1
        
        # Check distribution (should be roughly 50/50 with some tolerance)
        control_pct = assignments["control"] / 1000
        assert 0.45 <= control_pct <= 0.55  # Allow 5% deviation