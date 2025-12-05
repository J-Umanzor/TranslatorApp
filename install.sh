#!/bin/bash

# One-Command Install Script for AI PDF Translator
# This script downloads docker-compose.prod.yml and starts the application

set -e

echo "🚀 AI PDF Translator - One-Command Install"
echo "==========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop first:"
    echo "   https://www.docker.com/products/docker-desktop/"
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

# Download docker-compose.prod.yml
echo "📥 Downloading docker-compose configuration..."
curl -fsSL https://raw.githubusercontent.com/J-Umanzor/TranslatorApp/docker/docker-compose.prod.yml -o docker-compose.prod.yml

if [ ! -f docker-compose.prod.yml ]; then
    echo "❌ Failed to download docker-compose.prod.yml"
    exit 1
fi

echo "✅ Configuration downloaded"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file template..."
    cat > .env << 'EOF'
# Azure Translator Configuration (Optional - only needed if using Azure Translator)
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_ENDPOINT=
AZURE_TRANSLATOR_REGION=

# Ollama Configuration
# The Docker setup uses host.docker.internal to connect to Ollama on your host machine
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL=llama3.1:8b
EOF
    echo "✅ Created .env file template"
    echo ""
    echo "💡 To use Azure Translator, edit the .env file and add your credentials:"
    echo "   - AZURE_TRANSLATOR_KEY=your_key_here"
    echo "   - AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com"
    echo "   - AZURE_TRANSLATOR_REGION=your_region_here"
    echo ""
    read -p "Press Enter to continue (or Ctrl+C to edit .env first)..."
    echo ""
fi

# Pull and start containers
echo "🐳 Pulling Docker images and starting services..."
echo ""

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

