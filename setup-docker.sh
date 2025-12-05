#!/bin/bash

# AI PDF Translator - Docker Setup Script
# This script helps you set up and run the Translator App using Docker

set -e

echo "🚀 AI PDF Translator - Docker Setup"
echo "===================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Determine docker-compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

echo "✅ Docker is installed"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cat > .env << EOF
# Azure Translator Configuration (Optional - only needed if using Azure Translator)
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_ENDPOINT=
AZURE_TRANSLATOR_REGION=

# Ollama Configuration
# The Docker setup uses host.docker.internal to connect to Ollama on your host machine
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL=llama3.1:8b
EOF
    echo "✅ Created .env file. You can edit it to add your Azure Translator credentials."
    echo ""
fi

echo "🐳 Starting Docker containers..."
echo ""

# Pull and start containers
$DOCKER_COMPOSE -f docker-compose.prod.yml pull
$DOCKER_COMPOSE -f docker-compose.prod.yml up -d

echo ""
echo "✅ Application is starting!"
echo ""
echo "📍 Access the application at: http://localhost:3000"
echo "📍 Backend API at: http://localhost:8000"
echo "📍 LibreTranslate at: http://localhost:5000"
echo ""
echo "📋 Useful commands:"
echo "   - View logs: $DOCKER_COMPOSE -f docker-compose.prod.yml logs -f"
echo "   - Stop: $DOCKER_COMPOSE -f docker-compose.prod.yml down"
echo "   - Restart: $DOCKER_COMPOSE -f docker-compose.prod.yml restart"
echo ""
echo "⚠️  Note: Make sure Ollama is running on your host machine for the chatbot feature."
echo "   Run: ollama pull llama3.1:8b (if you haven't already)"
echo ""

