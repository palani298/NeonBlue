#!/bin/bash
# Quick script to update API tokens in your running environment

echo "🔐 Updating API Tokens..."

# Set the new tokens as environment variables
export BEARER_TOKENS='["admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-", "readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq", "write_EEpGsvCx9QnPgnMOfarQmOW1mcqwj7g6", "analytics_zF6mbjnVkLX16wa3tpKZoQukIvNZDICp", "service_2fIsuvS3OkelYHBCch3GaS_8cY2ijp10eEG7o36l", "demo_OErxSXNX_a5MKMXOtfm86xfc", "ext_v5hu0oqO476IaHcmdrNTGZhkp2yCMk5ZALqP", "monitor_0lQ8u2SyEaDKtQWGW5eZDBobeZg1", "test-token-1", "test-token-2"]'

echo "✅ Environment updated with new tokens"
echo ""
echo "🚀 Test your tokens:"
echo ""
echo "# Admin token (full access):"
echo "curl -H 'Authorization: Bearer admin_FYvh0whTsAXiWDzyq-lJ3alUPlH2j5vnN5V9mdL-' \\"
echo "     'http://localhost:8000/api/v1/experiments/?limit=5'"
echo ""
echo "# Read-only token:"
echo "curl -H 'Authorization: Bearer readonly_yI9Kf1N1CHDnMNOyvYc_Ll1VVRbldTMq' \\"
echo "     'http://localhost:8000/api/v1/experiments/?limit=5'"
echo ""
echo "# Demo token:"
echo "curl -H 'Authorization: Bearer demo_OErxSXNX_a5MKMXOtfm86xfc' \\"
echo "     'http://localhost:8000/api/v1/experiments/?limit=5'"
echo ""
echo "⚠️  To make these tokens persistent, restart your API service:"
echo "docker-compose -f config/docker-compose.yml restart api"
