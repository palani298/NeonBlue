#!/usr/bin/env python3
"""
Demo usage script for the Experimentation Platform API.

This script demonstrates:
1. Creating an experiment
2. Getting assignments (showing idempotency)
3. Recording events
4. Fetching results with statistical analysis
"""

import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
AUTH_TOKEN = "test-token-1"
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json"
}


def create_experiment() -> int:
    """Create a sample experiment."""
    print("Creating experiment...")
    
    experiment_data = {
        "key": f"demo_test_{int(time.time())}",
        "name": "Demo Color Test",
        "description": "Testing button colors for conversion optimization",
        "variants": [
            {
                "key": "control",
                "name": "Blue Button (Control)",
                "allocation_pct": 33,
                "is_control": True,
                "config": {"color": "#0066CC"}
            },
            {
                "key": "green",
                "name": "Green Button",
                "allocation_pct": 33,
                "is_control": False,
                "config": {"color": "#00AA00"}
            },
            {
                "key": "red",
                "name": "Red Button",
                "allocation_pct": 34,
                "is_control": False,
                "config": {"color": "#CC0000"}
            }
        ]
    }
    
    response = requests.post(
        f"{API_BASE_URL}/experiments",
        headers=HEADERS,
        json=experiment_data
    )
    response.raise_for_status()
    
    experiment = response.json()
    print(f"✅ Created experiment: {experiment['name']} (ID: {experiment['id']})")
    return experiment['id']


def demonstrate_idempotent_assignment(experiment_id: int, user_id: str) -> Dict[str, Any]:
    """Show that assignments are idempotent."""
    print(f"\nDemonstrating idempotent assignment for user {user_id}...")
    
    # First assignment
    response1 = requests.get(
        f"{API_BASE_URL}/experiments/{experiment_id}/assignment/{user_id}",
        headers=HEADERS
    )
    response1.raise_for_status()
    assignment1 = response1.json()
    
    print(f"  First call - Variant: {assignment1['variant_key']}")
    
    # Second assignment (should be same)
    response2 = requests.get(
        f"{API_BASE_URL}/experiments/{experiment_id}/assignment/{user_id}",
        headers=HEADERS
    )
    response2.raise_for_status()
    assignment2 = response2.json()
    
    print(f"  Second call - Variant: {assignment2['variant_key']}")
    
    assert assignment1['variant_id'] == assignment2['variant_id'], "Assignments should be identical!"
    print("  ✅ Assignments are idempotent!")
    
    return assignment1


def simulate_user_behavior(experiment_id: int, num_users: int = 100):
    """Simulate user behavior with events."""
    print(f"\nSimulating {num_users} users...")
    
    conversion_rates = {
        "control": 0.10,  # 10% conversion
        "green": 0.12,    # 12% conversion
        "red": 0.15       # 15% conversion (winner!)
    }
    
    for i in range(num_users):
        user_id = f"demo_user_{i}"
        
        # Get assignment (with enrollment)
        response = requests.get(
            f"{API_BASE_URL}/experiments/{experiment_id}/assignment/{user_id}?enroll=true",
            headers=HEADERS
        )
        response.raise_for_status()
        assignment = response.json()
        
        # Record impression event
        event_data = {
            "experiment_id": experiment_id,
            "user_id": user_id,
            "event_type": "impression",
            "properties": {
                "page": "homepage",
                "variant": assignment['variant_key']
            }
        }
        requests.post(f"{API_BASE_URL}/events", headers=HEADERS, json=event_data)
        
        # Record click event (80% of users click)
        if random.random() < 0.8:
            event_data["event_type"] = "click"
            event_data["properties"]["action"] = "button_click"
            requests.post(f"{API_BASE_URL}/events", headers=HEADERS, json=event_data)
        
        # Record conversion based on variant performance
        variant_key = assignment['variant_key']
        if random.random() < conversion_rates.get(variant_key, 0.10):
            event_data["event_type"] = "conversion"
            event_data["properties"]["value"] = random.uniform(10, 100)
            requests.post(f"{API_BASE_URL}/events", headers=HEADERS, json=event_data)
        
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1} users...")
    
    print(f"✅ Simulated {num_users} users with events")


def demonstrate_bulk_assignments(experiment_id: int):
    """Demonstrate bulk assignment endpoint."""
    print("\nDemonstrating bulk assignments...")
    
    # Create multiple experiments
    experiment_ids = [experiment_id]
    for i in range(2):
        exp_data = {
            "key": f"feature_flag_{i}_{int(time.time())}",
            "name": f"Feature Flag {i}",
            "variants": [
                {"key": "off", "name": "Off", "allocation_pct": 50, "is_control": True},
                {"key": "on", "name": "On", "allocation_pct": 50, "is_control": False}
            ]
        }
        response = requests.post(f"{API_BASE_URL}/experiments", headers=HEADERS, json=exp_data)
        if response.status_code == 201:
            experiment_ids.append(response.json()['id'])
    
    # Bulk assignment request
    bulk_request = {
        "user_id": "bulk_test_user",
        "experiment_ids": experiment_ids
    }
    
    start_time = time.time()
    response = requests.post(
        f"{API_BASE_URL}/assignments/bulk",
        headers=HEADERS,
        json=bulk_request
    )
    response.raise_for_status()
    duration = (time.time() - start_time) * 1000
    
    result = response.json()
    print(f"  Got {len(result['assignments'])} assignments in {duration:.2f}ms")
    for exp_id, assignment in result['assignments'].items():
        print(f"    Experiment {exp_id}: {assignment['variant_key']}")
    
    print("✅ Bulk assignments completed")


def fetch_and_display_results(experiment_id: int):
    """Fetch and display experiment results."""
    print("\nFetching experiment results...")
    
    # Wait a moment for events to be processed
    time.sleep(2)
    
    response = requests.get(
        f"{API_BASE_URL}/experiments/{experiment_id}/results",
        headers=HEADERS,
        params={
            "granularity": "day",
            "include_ci": True,
            "min_sample": 10,
            "event_type": ["impression", "click", "conversion"]
        }
    )
    response.raise_for_status()
    
    results = response.json()
    
    print("\n📊 Experiment Results:")
    print(f"  Experiment: {results.get('experiment_name', 'N/A')}")
    print(f"  Status: {results.get('status', 'N/A')}")
    
    print("\n  Variant Performance:")
    for variant in results.get('variants', []):
        print(f"\n  {variant['name']} ({'Control' if variant['is_control'] else 'Treatment'}):")
        
        metrics = variant.get('metrics', {})
        if 'conversion_rate' in metrics:
            cr = metrics['conversion_rate']
            print(f"    Conversion Rate: {cr.get('value', 0):.2%}")
            
            if 'ci_lower' in cr and 'ci_upper' in cr:
                print(f"    95% CI: [{cr['ci_lower']:.2%}, {cr['ci_upper']:.2%}]")
            
            if 'lift_vs_control' in cr:
                print(f"    Lift vs Control: {cr['lift_vs_control']:.1f}%")
            
            if 'p_value' in cr:
                significance = "✅ Significant" if cr.get('is_significant') else "❌ Not Significant"
                print(f"    P-value: {cr['p_value']:.4f} {significance}")
        
        if 'unique_users' in metrics:
            print(f"    Sample Size: {metrics['unique_users']['value']}")
    
    summary = results.get('summary', {})
    if summary:
        print(f"\n  📈 Summary:")
        print(f"    Total Users: {summary.get('total_users', 0)}")
        print(f"    Winning Variant: {summary.get('winning_variant', 'N/A')}")
        print(f"    Statistical Power: {summary.get('statistical_power', 0):.0%}")
        print(f"    Recommendation: {summary.get('recommendation', 'N/A')}")


def demonstrate_rate_limiting():
    """Demonstrate rate limiting."""
    print("\nDemonstrating rate limiting...")
    
    # Make rapid requests
    for i in range(5):
        response = requests.get(
            f"{API_BASE_URL}/experiments",
            headers=HEADERS
        )
        
        # Check rate limit headers
        remaining = response.headers.get('X-RateLimit-Remaining', 'N/A')
        limit = response.headers.get('X-RateLimit-Limit', 'N/A')
        
        print(f"  Request {i+1}: Status {response.status_code}, "
              f"Remaining: {remaining}/{limit}")
        
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 'N/A')
            print(f"  ⚠️ Rate limited! Retry after {retry_after} seconds")
            break


def main():
    """Run the demo."""
    print("=" * 60)
    print("Experimentation Platform Demo")
    print("=" * 60)
    
    try:
        # Check API health
        response = requests.get(f"http://localhost:8000/health")
        response.raise_for_status()
        print("✅ API is healthy\n")
        
        # Run demonstrations
        experiment_id = create_experiment()
        
        # Activate the experiment
        response = requests.post(
            f"{API_BASE_URL}/experiments/{experiment_id}/activate",
            headers=HEADERS
        )
        response.raise_for_status()
        print("✅ Experiment activated")
        
        demonstrate_idempotent_assignment(experiment_id, "demo_user_123")
        simulate_user_behavior(experiment_id, num_users=100)
        demonstrate_bulk_assignments(experiment_id)
        fetch_and_display_results(experiment_id)
        demonstrate_rate_limiting()
        
        print("\n" + "=" * 60)
        print("✅ Demo completed successfully!")
        print("=" * 60)
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        print("Make sure the API is running: docker-compose up -d")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
