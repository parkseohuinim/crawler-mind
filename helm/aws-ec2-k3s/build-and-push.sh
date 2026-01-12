#!/bin/bash

# AWS EC2 K3s 배포용 Docker 이미지 병렬 빌드 및 푸시 스크립트 (최적화 버전)
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT="${SCRIPT_DIR}/../.."
cd "${PROJECT_ROOT}"

# 인자 확인
if [ -z "$1" ] || [ -z "$2" ]; then
    echo -e "${RED}❌ 사용법: ./build-and-push.sh [DOCKER_HUB_USERNAME] [DOMAIN]${NC}"
    exit 1
fi

DOCKER_HUB_USERNAME=$1
DOMAIN=$2
TAG="dev-$(date +%Y%m%d-%H%M%S)"
CACHE_DIR="${PROJECT_ROOT}/.buildcache"
mkdir -p "${CACHE_DIR}"

echo -e "${BLUE}🚀 병렬 빌드 및 푸시를 시작합니다... (Tag: ${TAG})${NC}"

# Docker buildx 설정
docker buildx use crawler-mind-builder 2>/dev/null || docker buildx create --name crawler-mind-builder --use --bootstrap

# 이미지 이름 정의
FRONTEND_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-frontend:${TAG}"
CLIENT_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:${TAG}"
SERVER_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:${TAG}"
OPENSEARCH_IMAGE="${DOCKER_HUB_USERNAME}/opensearch-with-nori:2.13.0"
API_URL="https://api.${DOMAIN}/api"

# 🚀 공통 빌드 함수
build_func() {
    local NAME=$1
    local IMAGE=$2
    local FILE=$3
    local CONTEXT=$4
    local ARGS=$5
    local SERVICE_CACHE="${CACHE_DIR}/${NAME// /-}"
    
    # Frontend인 경우 추가 빌드 인자(Feature Flag) 주입
    local EXTRA_ARGS=""
    if [ "$NAME" == "Frontend" ]; then
        EXTRA_ARGS="--build-arg NEXT_PUBLIC_ENABLE_DAILY_CRAWLING=false"
    fi
    
    echo -e "${YELLOW}🏗️  ${NAME} 빌드 시작...${NC}"
    
    # 로컬 캐시 사용 및 푸시
    if docker buildx build \
        --platform linux/amd64 \
        -t "${IMAGE}" \
        -f "${FILE}" \
        ${ARGS} ${EXTRA_ARGS} \
        --cache-from "type=local,src=${SERVICE_CACHE}" \
        --cache-to "type=local,dest=${SERVICE_CACHE},mode=max" \
        "${CONTEXT}" \
        --push > /tmp/build_${NAME// /-}.log 2>&1; then
        echo -e "${GREEN}✅ ${NAME} 완료!${NC}"
    else
        echo -e "${RED}❌ ${NAME} 실패! 로그 확인: /tmp/build_${NAME// /-}.log${NC}"
        exit 1
    fi
}

# 🚀 4개의 이미지를 병렬 실행
build_func "Frontend" "${FRONTEND_IMAGE}" "./frontend/Dockerfile" "./frontend" "--build-arg NEXT_PUBLIC_API_BASE_URL=${API_URL}" &
PID1=$!

build_func "MCP Client" "${CLIENT_IMAGE}" "./mcp-client/Dockerfile" "." "" &
PID2=$!

build_func "MCP Server" "${SERVER_IMAGE}" "./mcp-server/Dockerfile" "." "" &
PID3=$!

build_func "OpenSearch" "${OPENSEARCH_IMAGE}" "./opensearch/Dockerfile" "./opensearch" "" &
PID4=$!

echo -e "${YELLOW}⏳ 모든 이미지를 병렬로 빌드 중입니다...${NC}"
wait $PID1 $PID2 $PID3 $PID4

# values.yaml 태그 자동 업데이트
echo -e "${YELLOW}📝 values.yaml 태그 자동 업데이트...${NC}"
cd "${SCRIPT_DIR}"
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" mcp-client-chart/values.yaml
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" mcp-server-chart/values.yaml
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" frontend-chart/values.yaml
rm -f mcp-client-chart/values.yaml.bak mcp-server-chart/values.yaml.bak frontend-chart/values.yaml.bak

echo -e "${GREEN}🎉 모든 작업이 완료되었습니다! (Tag: ${TAG})${NC}"
