#!/bin/bash

echo "🧪 Setting up Experiments Platform Dashboard"
echo "============================================="

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first:"
    echo "   https://nodejs.org/"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

echo "✅ Node.js and npm are installed"

# Navigate to dashboard directory
cd simple-dashboard

# Install dependencies
echo "📦 Installing dependencies..."
npm install

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
    echo ""
    echo "🚀 To start the dashboard:"
    echo "   cd simple-dashboard"
    echo "   npm start"
    echo ""
    echo "🌐 The dashboard will be available at: http://localhost:3000"
    echo ""
    echo "📊 Make sure your API is running at: http://localhost:8000"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
