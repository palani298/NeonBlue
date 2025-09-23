#!/bin/bash

# Run tests with coverage report

echo "Running Experimentation Platform Tests"
echo "======================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run tests with coverage
echo "Running tests with coverage..."
pytest tests/ \
    -v \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --tb=short \
    -x

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo "Coverage report generated in htmlcov/index.html"
else
    echo ""
    echo "❌ Some tests failed. Please check the output above."
fi
