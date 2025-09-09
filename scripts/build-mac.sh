#!/bin/bash

# Mac M1에서 Docker Hub로 amd64 이미지 빌드 및 푸시 스크립트
# Usage: ./scripts/build-mac.sh [DOCKER_HUB_USERNAME] [NEXT_PUBLIC_API_BASE_URL]

set -e

# 항상 프로젝트 루트 기준으로 실행되도록 경로 변경
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT="${SCRIPT_DIR}/.."
cd "${PROJECT_ROOT}"

# Docker Hub 사용자명 확인
if [ -z "$1" ]; then
    echo "❌ Docker Hub 사용자명이 필요합니다."
    echo "Usage: ./scripts/build-mac.sh [DOCKER_HUB_USERNAME] [NEXT_PUBLIC_API_BASE_URL]"
    echo "Example: ./scripts/build-mac.sh seohuipark https://crawler.alvinpark.xyz/api"
    exit 1
fi

DOCKER_HUB_USERNAME=$1
# 두 번째 인자 또는 환경변수에서 NEXT_PUBLIC_API_BASE_URL 설정
NEXT_PUBLIC_API_BASE_URL_INPUT=${2:-${NEXT_PUBLIC_API_BASE_URL}}
if [ -z "${NEXT_PUBLIC_API_BASE_URL_INPUT}" ]; then
    echo "❌ NEXT_PUBLIC_API_BASE_URL 값이 필요합니다. 두 번째 인자로 전달하거나 환경변수로 설정하세요."
    echo "예: ./scripts/build-mac.sh seohuipark https://crawler.alvinpark.xyz/api"
    exit 1
fi

TAG_SUFFIX="dev"

echo "🚀 Mac M1에서 Docker Hub로 amd64 이미지 빌드 및 푸시 시작..."
echo "📦 Docker Hub 사용자: ${DOCKER_HUB_USERNAME}"
echo "🌐 NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL_INPUT}"

# Docker Hub 로그인 확인
echo "🔐 Docker Hub 로그인 확인 중..."
if ! docker info | grep -q "Username: ${DOCKER_HUB_USERNAME}"; then
    echo "🔑 Docker Hub 로그인이 필요합니다."
    docker login -u ${DOCKER_HUB_USERNAME}
fi

# Docker buildx 설정 (최초 1회만 실행)
echo "📦 Docker buildx 설정 확인..."
if ! docker buildx ls | grep -q "crawler-mind-builder"; then
    echo "🔧 buildx builder 생성 중..."
    docker buildx create --name crawler-mind-builder --use
else
    echo "✅ buildx builder 이미 존재"
    docker buildx use crawler-mind-builder
fi

# 이미지 태그 설정
FRONTEND_TAG="${DOCKER_HUB_USERNAME}/crawler-mind-frontend:${TAG_SUFFIX}"
CLIENT_TAG="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:${TAG_SUFFIX}"
SERVER_TAG="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:${TAG_SUFFIX}"

echo "🏗️  Frontend 이미지 빌드 및 푸시 중..."
docker buildx build \
    --platform linux/amd64 \
    -t ${FRONTEND_TAG} \
    -f ./frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL_INPUT}" \
    ./frontend \
    --push

echo "🏗️  MCP Client 이미지 빌드 및 푸시 중..."
docker buildx build \
    --platform linux/amd64 \
    -t ${CLIENT_TAG} \
    -f ./mcp-client/Dockerfile \
    . \
    --push

echo "🏗️  MCP Server 이미지 빌드 및 푸시 중..."
docker buildx build \
    --platform linux/amd64 \
    -t ${SERVER_TAG} \
    -f ./mcp-server/Dockerfile \
    . \
    --push

echo "✅ 모든 이미지 빌드 및 푸시 완료!"
echo ""
echo "📋 푸시된 이미지 목록:"
echo "   - ${FRONTEND_TAG}"
echo "   - ${CLIENT_TAG}"
echo "   - ${SERVER_TAG}"

echo ""
echo "🎉 Docker Hub 푸시 완료!"
echo ""
echo "🚀 다음 단계:"
echo "1. WSL 서버에서 ./scripts/deploy-wsl.sh ${DOCKER_HUB_USERNAME} 실행"
echo "2. 또는 docker-compose up -d 실행"
