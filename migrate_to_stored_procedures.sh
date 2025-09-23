#!/bin/bash

echo "=========================================="
echo "Migrating to Stored Procedures"
echo "=========================================="

# Check if we're in Docker or local
if [ -f /.dockerenv ]; then
    echo "Running in Docker container..."
    DB_HOST="postgres"
else
    echo "Running locally..."
    DB_HOST="localhost"
fi

# Database connection details
DB_USER="${DB_USER:-experiments}"
DB_PASS="${DB_PASS:-password}"
DB_NAME="${DB_NAME:-experiments}"

echo ""
echo "1. Creating stored procedures..."

# Execute stored procedures SQL
PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f /workspace/init/postgres/02_stored_procedures.sql

if [ $? -eq 0 ]; then
    echo "✅ Stored procedures created successfully"
else
    echo "❌ Failed to create stored procedures"
    exit 1
fi

echo ""
echo "2. Running Alembic migration..."

# Run Alembic migration
cd /workspace
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Migration to Stored Procedures Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Update your code to use the new services:"
echo "   - app.services.assignment_v2"
echo "   - app.services.events_v2"
echo "   - app.services.analytics_v2"
echo ""
echo "2. Or use stored_procedure_dao directly:"
echo "   from app.core.stored_procedures import stored_procedure_dao"
echo ""
echo "3. Test with the demo script:"
echo "   python examples/demo_stored_procedures.py"
echo ""
echo "Benefits you now have:"
echo "  ⚡ Better performance"
echo "  🔒 Enhanced security"
echo "  🎯 Atomic operations"
echo "  📊 Centralized logic"
echo "  🔄 Reduced network traffic"
echo "=========================================="