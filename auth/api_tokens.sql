-- API Tokens for NeonBlue Experimentation Platform

-- Generated on: 2025-09-30T05:52:08.212501



-- Insert API tokens

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-',
    'Admin Token',
    'Full administrative access to all resources',
    '["*"]',
    1000,
    '2026-09-30T05:52:08.212905',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq',
    'Read-Only Token',
    'Read-only access to experiments, assignments, and analytics',
    '["experiments:read", "assignments:read", "users:read", "analytics:read", "events:read"]',
    500,
    '2026-03-29T05:52:08.212927',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'write_EEpGsvCx9QnPgnMOfarQmOW1mcqwj7g6',
    'Write Access Token',
    'Create and update experiments, assignments, and events',
    '["experiments:read", "experiments:write", "assignments:read", "assignments:write", "users:read", "users:write", "events:read", "events:write", "analytics:read"]',
    300,
    '2026-03-29T05:52:08.212938',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp',
    'Analytics Token',
    'Access to analytics data and reporting endpoints',
    '["analytics:read", "analytics:write", "experiments:read", "events:read", "results:read"]',
    200,
    '2025-12-29T05:52:08.212946',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'service_2fIsuvS3OkelYHBCch3GaS_8cY2ijp10eEG7o36l',
    'Service Token',
    'Inter-service communication and automated processes',
    '["experiments:read", "experiments:write", "assignments:read", "assignments:write", "events:read", "events:write", "users:read", "users:write"]',
    2000,
    '2026-09-30T05:52:08.212952',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'demo_OErxSXNX_a5MKMXOtfm86xfc',
    'Demo Token',
    'Limited access for demonstrations and testing',
    '["experiments:read", "assignments:read", "analytics:read", "events:read"]',
    100,
    '2025-10-30T05:52:08.212961',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'ext_v5hu0oqO476IaHcmdrNTGZhkp2yCMk5ZALqP',
    'External API Token',
    'External partner/integration access',
    '["experiments:read", "assignments:read", "events:write", "results:read"]',
    150,
    '2025-12-29T05:52:08.212966',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();

INSERT INTO api_tokens (
    token, name, description, scopes, rate_limit, 
    expires_at, is_active, created_at, updated_at
) VALUES (
    'monitor_0lQ8u2SyEaDKtQWGW5eZDBobeZg1',
    'Monitoring Token',
    'Health checks and monitoring endpoints',
    '["health:read", "metrics:read", "status:read"]',
    1000,
    '2026-09-30T05:52:08.212971',
    true,
    NOW(),
    NOW()
) ON CONFLICT (token) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    scopes = EXCLUDED.scopes,
    rate_limit = EXCLUDED.rate_limit,
    updated_at = NOW();