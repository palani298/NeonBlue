#!/usr/bin/env python3
"""
Generate API tokens for different access levels
"""

import secrets
import string
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any


def generate_secure_token(prefix: str = "", length: int = 32) -> str:
    """Generate a cryptographically secure token"""
    # Use URL-safe base64 characters
    alphabet = string.ascii_letters + string.digits + '-_'
    token_suffix = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}_{token_suffix}" if prefix else token_suffix


def generate_api_tokens() -> Dict[str, Any]:
    """Generate a complete set of API tokens for different access levels"""
    
    tokens = {
        # Administrative access - full permissions
        "admin": {
            "token": generate_secure_token("admin", 40),
            "name": "Admin Token",
            "description": "Full administrative access to all resources",
            "scopes": ["*"],
            "rate_limit": 1000,  # requests per minute
            "expires_days": 365,
            "is_active": True
        },
        
        # Read-only access
        "readonly": {
            "token": generate_secure_token("readonly", 32),
            "name": "Read-Only Token", 
            "description": "Read-only access to experiments, assignments, and analytics",
            "scopes": [
                "experiments:read",
                "assignments:read", 
                "users:read",
                "analytics:read",
                "events:read"
            ],
            "rate_limit": 500,
            "expires_days": 180,
            "is_active": True
        },
        
        # Write access (can create/update but not delete)
        "write": {
            "token": generate_secure_token("write", 32),
            "name": "Write Access Token",
            "description": "Create and update experiments, assignments, and events",
            "scopes": [
                "experiments:read",
                "experiments:write",
                "assignments:read",
                "assignments:write",
                "users:read",
                "users:write",
                "events:read",
                "events:write",
                "analytics:read"
            ],
            "rate_limit": 300,
            "expires_days": 180,
            "is_active": True
        },
        
        # Analytics-focused access
        "analytics": {
            "token": generate_secure_token("analytics", 32),
            "name": "Analytics Token",
            "description": "Access to analytics data and reporting endpoints",
            "scopes": [
                "analytics:read",
                "analytics:write",
                "experiments:read",
                "events:read",
                "results:read"
            ],
            "rate_limit": 200,
            "expires_days": 90,
            "is_active": True
        },
        
        # Service-to-service communication
        "service": {
            "token": generate_secure_token("service", 40),
            "name": "Service Token",
            "description": "Inter-service communication and automated processes",
            "scopes": [
                "experiments:read",
                "experiments:write",
                "assignments:read", 
                "assignments:write",
                "events:read",
                "events:write",
                "users:read",
                "users:write"
            ],
            "rate_limit": 2000,  # High rate limit for services
            "expires_days": 365,
            "is_active": True
        },
        
        # Demo/Testing token
        "demo": {
            "token": generate_secure_token("demo", 24),
            "name": "Demo Token",
            "description": "Limited access for demonstrations and testing",
            "scopes": [
                "experiments:read",
                "assignments:read",
                "analytics:read",
                "events:read"
            ],
            "rate_limit": 100,
            "expires_days": 30,
            "is_active": True
        },
        
        # External API access (for partners/integrations)
        "external": {
            "token": generate_secure_token("ext", 36),
            "name": "External API Token",
            "description": "External partner/integration access",
            "scopes": [
                "experiments:read",
                "assignments:read",
                "events:write",  # Can send events
                "results:read"
            ],
            "rate_limit": 150,
            "expires_days": 90,
            "is_active": True
        },
        
        # Monitoring/Health check token
        "monitoring": {
            "token": generate_secure_token("monitor", 28),
            "name": "Monitoring Token",
            "description": "Health checks and monitoring endpoints",
            "scopes": [
                "health:read",
                "metrics:read",
                "status:read"
            ],
            "rate_limit": 1000,
            "expires_days": 365,
            "is_active": True
        }
    }
    
    return tokens


def generate_database_insert_sql(tokens: Dict[str, Any]) -> str:
    """Generate SQL INSERT statements for the tokens"""
    sql_statements = []
    
    sql_statements.append("-- API Tokens for NeonBlue Experimentation Platform")
    sql_statements.append("-- Generated on: " + datetime.utcnow().isoformat())
    sql_statements.append("")
    sql_statements.append("-- Insert API tokens")
    
    for token_type, config in tokens.items():
        expires_at = datetime.utcnow() + timedelta(days=config['expires_days'])
        
        scopes_json = json.dumps(config['scopes'])
        
        sql = f"""
INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    '{config['token']}',
    '{config['name']}',
    '{config['description']}',
    '{scopes_json}',
    {config['rate_limit']},
    '{expires_at.isoformat()}',
    {str(config['is_active']).lower()},
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();
"""
        sql_statements.append(sql.strip())
    
    return "\n\n".join(sql_statements)


def generate_env_config(tokens: Dict[str, Any]) -> str:
    """Generate environment configuration for the tokens"""
    env_lines = []
    
    env_lines.append("# API Tokens Configuration")
    env_lines.append("# Generated on: " + datetime.utcnow().isoformat())
    env_lines.append("")
    
    # Bearer tokens for static configuration (development)
    bearer_tokens = [config['token'] for config in tokens.values()]
    env_lines.append(f'BEARER_TOKENS={json.dumps(bearer_tokens)}')
    env_lines.append("")
    
    # Individual token environment variables for easy reference
    env_lines.append("# Individual token references")
    for token_type, config in tokens.items():
        var_name = f"API_TOKEN_{token_type.upper()}"
        env_lines.append(f'{var_name}={config["token"]}')
    
    return "\n".join(env_lines)


def main():
    """Main function to generate and save tokens"""
    print("🔐 Generating API Tokens for NeonBlue Experimentation Platform...")
    
    # Generate tokens
    tokens = generate_api_tokens()
    
    # Save tokens to JSON file
    tokens_file = "generated_api_tokens.json"
    with open(tokens_file, 'w') as f:
        json.dump(tokens, f, indent=2, default=str)
    
    # Generate SQL file
    sql_content = generate_database_insert_sql(tokens)
    sql_file = "api_tokens.sql"
    with open(sql_file, 'w') as f:
        f.write(sql_content)
    
    # Generate .env configuration
    env_content = generate_env_config(tokens)
    env_file = "api_tokens.env"
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Generated {len(tokens)} API tokens")
    print(f"📄 Token details saved to: {tokens_file}")
    print(f"🗄️  SQL commands saved to: {sql_file}")
    print(f"⚙️  Environment config saved to: {env_file}")
    print()
    
    # Display summary
    print("🔑 Generated Token Summary:")
    print("=" * 80)
    
    for token_type, config in tokens.items():
        print(f"Token Type: {token_type.upper()}")
        print(f"  Name: {config['name']}")
        print(f"  Token: {config['token']}")
        print(f"  Scopes: {', '.join(config['scopes'])}")
        print(f"  Rate Limit: {config['rate_limit']} req/min")
        print(f"  Expires: {config['expires_days']} days")
        print()
    
    print("🚀 Quick Test Commands:")
    print("-" * 40)
    for token_type, config in tokens.items():
        if token_type in ['admin', 'readonly', 'demo']:
            print(f"# Test {token_type} token:")
            print(f"curl -H 'Authorization: Bearer {config['token']}' \\")
            print(f"     http://localhost:8000/api/v1/experiments/")
            print()
    
    print("💡 Next Steps:")
    print("1. Update your database: psql -d experiments -f api_tokens.sql")
    print("2. Update .env file with new tokens")
    print("3. Restart your API service")
    print("4. Test tokens with the curl commands above")


if __name__ == "__main__":
    main()

