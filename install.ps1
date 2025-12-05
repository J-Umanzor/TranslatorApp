# One-Command Install Script for AI PDF Translator (PowerShell)
# This script downloads docker-compose.prod.yml and starts the application

Write-Host "🚀 AI PDF Translator - One-Command Install" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "✅ Docker is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first:" -ForegroundColor Red
    Write-Host "   https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
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

# Download docker-compose.prod.yml
Write-Host "📥 Downloading docker-compose configuration..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/J-Umanzor/TranslatorApp/docker/docker-compose.prod.yml" -OutFile "docker-compose.prod.yml" -UseBasicParsing
    Write-Host "✅ Configuration downloaded" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to download docker-compose.prod.yml" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Pull and start containers
Write-Host "🐳 Pulling Docker images and starting services..." -ForegroundColor Cyan
Write-Host ""

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

