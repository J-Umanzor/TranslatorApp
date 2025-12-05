#!/bin/bash

# Build and Push Docker Images Script
# This script builds the Docker images and pushes them to Docker Hub
# Usage: ./build-and-push.sh [your-dockerhub-username]

set -e

DOCKER_USERNAME=${1:-"translatorapp"}

if [ -z "$1" ]; then
    echo "⚠️  No Docker Hub username provided. Using default: $DOCKER_USERNAME"
    echo "   Usage: ./build-and-push.sh your-username"
    echo ""
fi

echo "🔨 Building Docker images..."
echo ""

# Build backend image
echo "📦 Building backend image..."
docker build -t $DOCKER_USERNAME/translator-backend:latest ./backend
docker tag $DOCKER_USERNAME/translator-backend:latest $DOCKER_USERNAME/translator-backend:latest

# Build frontend image
echo "📦 Building frontend image..."
docker build -t $DOCKER_USERNAME/translator-frontend:latest ./frontend
docker tag $DOCKER_USERNAME/translator-frontend:latest $DOCKER_USERNAME/translator-frontend:latest

echo ""
echo "✅ Images built successfully!"
echo ""
echo "📤 Pushing images to Docker Hub..."
echo "   Make sure you're logged in: docker login"
echo ""

read -p "Do you want to push the images now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker push $DOCKER_USERNAME/translator-backend:latest
    docker push $DOCKER_USERNAME/translator-frontend:latest
    
    echo ""
    echo "✅ Images pushed successfully!"
    echo ""
    echo "📝 Update docker-compose.prod.yml with your image names:"
    echo "   BACKEND_IMAGE=$DOCKER_USERNAME/translator-backend:latest"
    echo "   FRONTEND_IMAGE=$DOCKER_USERNAME/translator-frontend:latest"
    echo ""
    echo "   Or set environment variables:"
    echo "   export BACKEND_IMAGE=$DOCKER_USERNAME/translator-backend:latest"
    echo "   export FRONTEND_IMAGE=$DOCKER_USERNAME/translator-frontend:latest"
else
    echo "⏭️  Skipping push. You can push manually later with:"
    echo "   docker push $DOCKER_USERNAME/translator-backend:latest"
    echo "   docker push $DOCKER_USERNAME/translator-frontend:latest"
fi

