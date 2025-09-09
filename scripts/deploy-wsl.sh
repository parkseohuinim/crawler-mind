#!/bin/bash
set -e

echo "🚀 WSL 서버에서 Docker Hub에서 서비스 배포 시작..."

if [ -z "$1" ]; then
    echo "❌ Docker Hub 사용자명이 필요합니다."
    echo "Usage: ./deploy-wsl.sh [DOCKER_HUB_USERNAME]"
    exit 1
fi

DOCKER_HUB_USERNAME=$1
TAG_SUFFIX="dev"

# 스크립트 위치 기준으로 docker-compose.yml 경로 설정
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

echo "📦 Docker Hub 사용자: ${DOCKER_HUB_USERNAME}"

# Docker Hub 로그인 확인
echo "🔐 Docker Hub 로그인 확인 중..."
if ! docker info | grep -q "Username: ${DOCKER_HUB_USERNAME}"; then
    echo "🔑 Docker Hub 로그인이 필요합니다."
    docker login -u ${DOCKER_HUB_USERNAME}
fi

# 기존 컨테이너 정리
echo "🧹 기존 컨테이너 정리 중..."
docker-compose -f $COMPOSE_FILE down 2>/dev/null || true

# 이미지 풀
echo "📦 Docker Hub에서 이미지 풀 중..."
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-frontend:${TAG_SUFFIX}
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:${TAG_SUFFIX}
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:${TAG_SUFFIX}

# 태그 latest로 변경
docker tag ${DOCKER_HUB_USERNAME}/crawler-mind-frontend:${TAG_SUFFIX} crawler-mind-frontend:latest
docker tag ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:${TAG_SUFFIX} crawler-mind-mcp-client:latest
docker tag ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:${TAG_SUFFIX} crawler-mind-mcp-server:latest

# 서비스 시작
echo "🚀 서비스 시작 중..."
docker-compose -f $COMPOSE_FILE up -d

# 상태 확인
echo "📊 서비스 상태 확인 중..."
sleep 10
docker-compose -f $COMPOSE_FILE ps

echo "🎉 배포 완료!"
echo "   - Frontend: http://localhost:3000"
echo "   - MCP Client: http://localhost:8000/docs"
echo "   - MCP Server: http://localhost:4200"
