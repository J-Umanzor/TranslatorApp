# Build and Push Docker Images Script (PowerShell)
# This script builds the Docker images and pushes them to Docker Hub
# Usage: .\build-and-push.ps1 [your-dockerhub-username]

param(
    [string]$DockerUsername = "translatorapp"
)

if (-Not $args[0]) {
    Write-Host "⚠️  No Docker Hub username provided. Using default: $DockerUsername" -ForegroundColor Yellow
    Write-Host "   Usage: .\build-and-push.ps1 your-username" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "🔨 Building Docker images..." -ForegroundColor Cyan
Write-Host ""

# Build backend image
Write-Host "📦 Building backend image..." -ForegroundColor Yellow
docker build -t "$DockerUsername/translator-backend:latest" ./backend
docker tag "$DockerUsername/translator-backend:latest" "$DockerUsername/translator-backend:latest"

# Build frontend image
Write-Host "📦 Building frontend image..." -ForegroundColor Yellow
docker build -t "$DockerUsername/translator-frontend:latest" ./frontend
docker tag "$DockerUsername/translator-frontend:latest" "$DockerUsername/translator-frontend:latest"

Write-Host ""
Write-Host "✅ Images built successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📤 Pushing images to Docker Hub..." -ForegroundColor Cyan
Write-Host "   Make sure you're logged in: docker login" -ForegroundColor Yellow
Write-Host ""

$response = Read-Host "Do you want to push the images now? (y/n)"
if ($response -eq 'y' -or $response -eq 'Y') {
    docker push "$DockerUsername/translator-backend:latest"
    docker push "$DockerUsername/translator-frontend:latest"
    
    Write-Host ""
    Write-Host "✅ Images pushed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Update docker-compose.prod.yml with your image names:" -ForegroundColor Yellow
    Write-Host "   BACKEND_IMAGE=$DockerUsername/translator-backend:latest"
    Write-Host "   FRONTEND_IMAGE=$DockerUsername/translator-frontend:latest"
    Write-Host ""
    Write-Host "   Or set environment variables:" -ForegroundColor Yellow
    Write-Host "   `$env:BACKEND_IMAGE='$DockerUsername/translator-backend:latest'"
    Write-Host "   `$env:FRONTEND_IMAGE='$DockerUsername/translator-frontend:latest'"
} else {
    Write-Host "⏭️  Skipping push. You can push manually later with:" -ForegroundColor Yellow
    Write-Host "   docker push $DockerUsername/translator-backend:latest"
    Write-Host "   docker push $DockerUsername/translator-frontend:latest"
}

