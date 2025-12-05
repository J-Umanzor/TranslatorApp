# AI PDF Translator - Docker Setup Script (PowerShell)
# This script helps you set up and run the Translator App using Docker

Write-Host "🚀 AI PDF Translator - Docker Setup" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "✅ Docker is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker first:" -ForegroundColor Red
    Write-Host "   https://docs.docker.com/get-docker/" -ForegroundColor Yellow
    exit 1
}

# Check if Docker Compose is installed
$dockerCompose = "docker compose"
try {
    docker compose version | Out-Null
} catch {
    try {
        docker-compose --version | Out-Null
        $dockerCompose = "docker-compose"
    } catch {
        Write-Host "❌ Docker Compose is not installed. Please install Docker Compose first." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Check if .env file exists
if (-Not (Test-Path .env)) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
    @"
# Azure Translator Configuration (Optional - only needed if using Azure Translator)
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_ENDPOINT=
AZURE_TRANSLATOR_REGION=

# Ollama Configuration
# The Docker setup uses host.docker.internal to connect to Ollama on your host machine
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL=llama3.1:8b
"@ | Out-File -FilePath .env -Encoding utf8
    Write-Host "✅ Created .env file. You can edit it to add your Azure Translator credentials." -ForegroundColor Green
    Write-Host ""
}

Write-Host "🐳 Starting Docker containers..." -ForegroundColor Cyan
Write-Host ""

# Pull and start containers
& $dockerCompose.Split(' ') -f docker-compose.prod.yml pull
& $dockerCompose.Split(' ') -f docker-compose.prod.yml up -d

Write-Host ""
Write-Host "✅ Application is starting!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Access the application at: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📍 Backend API at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📍 LibreTranslate at: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Yellow
Write-Host "   - View logs: $dockerCompose -f docker-compose.prod.yml logs -f"
Write-Host "   - Stop: $dockerCompose -f docker-compose.prod.yml down"
Write-Host "   - Restart: $dockerCompose -f docker-compose.prod.yml restart"
Write-Host ""
Write-Host "⚠️  Note: Make sure Ollama is running on your host machine for the chatbot feature." -ForegroundColor Yellow
Write-Host "   Run: ollama pull llama3.1:8b (if you haven't already)" -ForegroundColor Yellow
Write-Host ""

