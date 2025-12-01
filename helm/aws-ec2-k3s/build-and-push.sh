#!/bin/bash

# AWS EC2 K3s 배포용 Docker 이미지 빌드 및 푸시 스크립트
# Mac M1/M2에서 amd64 이미지를 빌드하여 Docker Hub에 푸시합니다.
# Usage: ./build-and-push.sh [DOCKER_HUB_USERNAME] [DOMAIN]

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 프로젝트 루트로 이동
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PROJECT_ROOT="${SCRIPT_DIR}/../.."
cd "${PROJECT_ROOT}"

echo -e "${BLUE}🚀 AWS EC2 K3s 배포용 Docker 이미지 빌드 시작...${NC}"
echo ""

# 인자 확인
if [ -z "$1" ]; then
    echo -e "${RED}❌ Docker Hub 사용자명이 필요합니다.${NC}"
    echo ""
    echo "Usage: ./build-and-push.sh [DOCKER_HUB_USERNAME] [DOMAIN]"
    echo "Example: ./build-and-push.sh seohuipark alvinpark.xyz"
    echo ""
    exit 1
fi

if [ -z "$2" ]; then
    echo -e "${RED}❌ 도메인이 필요합니다.${NC}"
    echo ""
    echo "Usage: ./build-and-push.sh [DOCKER_HUB_USERNAME] [DOMAIN]"
    echo "Example: ./build-and-push.sh seohuipark alvinpark.xyz"
    echo ""
    exit 1
fi

DOCKER_HUB_USERNAME=$1
DOMAIN=$2
# 타임스탬프 기반 태그 생성 (예: dev-20251201-123045)
TAG="dev-$(date +%Y%m%d-%H%M%S)"
# 또는 git commit hash 사용 (git이 있는 경우)
# TAG="dev-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d-%H%M%S)"

# 빌드 캐시 레지스트리 설정
CACHE_REGISTRY="${DOCKER_HUB_USERNAME}"

echo -e "${GREEN}📦 Docker Hub 사용자: ${DOCKER_HUB_USERNAME}${NC}"
echo -e "${GREEN}🌐 도메인: ${DOMAIN}${NC}"
echo -e "${GREEN}🏷️  태그: ${TAG}${NC}"
echo ""

# Docker Hub 로그인 확인
echo -e "${YELLOW}🔐 Docker Hub 로그인 확인 중...${NC}"
if ! docker info 2>/dev/null | grep -q "Username: ${DOCKER_HUB_USERNAME}"; then
    echo -e "${YELLOW}🔑 Docker Hub 로그인이 필요합니다.${NC}"
    docker login -u ${DOCKER_HUB_USERNAME}
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Docker Hub 로그인 실패${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Docker Hub 로그인 확인됨${NC}"
fi
echo ""

# Docker buildx 설정
echo -e "${YELLOW}📦 Docker buildx 설정 확인...${NC}"
if ! docker buildx ls | grep -q "crawler-mind-builder"; then
    echo -e "${YELLOW}🔧 buildx builder 생성 중...${NC}"
    docker buildx create --name crawler-mind-builder --use --bootstrap
    echo -e "${GREEN}✅ buildx builder 생성 완료${NC}"
else
    echo -e "${GREEN}✅ buildx builder 이미 존재${NC}"
    docker buildx use crawler-mind-builder
fi
echo ""

# 이미지 태그 설정
FRONTEND_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-frontend:${TAG}"
CLIENT_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:${TAG}"
SERVER_IMAGE="${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:${TAG}"
OPENSEARCH_IMAGE="${DOCKER_HUB_USERNAME}/opensearch-with-nori:2.13.0"

# API URL 설정
API_URL="https://api.${DOMAIN}/api"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📦 빌드할 이미지 목록${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "1. ${FRONTEND_IMAGE}"
echo -e "2. ${CLIENT_IMAGE}"
echo -e "3. ${SERVER_IMAGE}"
echo -e "4. ${OPENSEARCH_IMAGE}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. Frontend 빌드
echo -e "${YELLOW}🏗️  [1/4] Frontend 이미지 빌드 및 푸시 중...${NC}"
echo -e "   - Image: ${FRONTEND_IMAGE}"
echo -e "   - API URL: ${API_URL}"
echo -e "   - 🚀 빌드 캐시 활성화"
docker buildx build \
    --platform linux/amd64 \
    -t ${FRONTEND_IMAGE} \
    -f ./frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_API_BASE_URL="${API_URL}" \
    --cache-from type=registry,ref=${CACHE_REGISTRY}/crawler-mind-frontend:buildcache \
    --cache-to type=registry,ref=${CACHE_REGISTRY}/crawler-mind-frontend:buildcache,mode=max \
    ./frontend \
    --push

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend 이미지 푸시 완료${NC}"
else
    echo -e "${RED}❌ Frontend 이미지 빌드 실패${NC}"
    exit 1
fi
echo ""

# 2. MCP Client 빌드
echo -e "${YELLOW}🏗️  [2/4] MCP Client 이미지 빌드 및 푸시 중...${NC}"
echo -e "   - Image: ${CLIENT_IMAGE}"
echo -e "   - 🚀 빌드 캐시 활성화"
docker buildx build \
    --platform linux/amd64 \
    -t ${CLIENT_IMAGE} \
    -f ./mcp-client/Dockerfile \
    --cache-from type=registry,ref=${CACHE_REGISTRY}/crawler-mind-mcp-client:buildcache \
    --cache-to type=registry,ref=${CACHE_REGISTRY}/crawler-mind-mcp-client:buildcache,mode=max \
    . \
    --push

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ MCP Client 이미지 푸시 완료${NC}"
else
    echo -e "${RED}❌ MCP Client 이미지 빌드 실패${NC}"
    exit 1
fi
echo ""

# 3. MCP Server 빌드
echo -e "${YELLOW}🏗️  [3/4] MCP Server 이미지 빌드 및 푸시 중...${NC}"
echo -e "   - Image: ${SERVER_IMAGE}"
echo -e "   - 🚀 빌드 캐시 활성화"
docker buildx build \
    --platform linux/amd64 \
    -t ${SERVER_IMAGE} \
    -f ./mcp-server/Dockerfile \
    --cache-from type=registry,ref=${CACHE_REGISTRY}/crawler-mind-mcp-server:buildcache \
    --cache-to type=registry,ref=${CACHE_REGISTRY}/crawler-mind-mcp-server:buildcache,mode=max \
    . \
    --push

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ MCP Server 이미지 푸시 완료${NC}"
else
    echo -e "${RED}❌ MCP Server 이미지 빌드 실패${NC}"
    exit 1
fi
echo ""

# 4. OpenSearch with Nori 빌드
echo -e "${YELLOW}🏗️  [4/4] OpenSearch with Nori 이미지 빌드 및 푸시 중...${NC}"
echo -e "   - Image: ${OPENSEARCH_IMAGE}"
docker buildx build \
    --platform linux/amd64 \
    -t ${OPENSEARCH_IMAGE} \
    -f ./opensearch/Dockerfile \
    ./opensearch \
    --push

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ OpenSearch 이미지 푸시 완료${NC}"
else
    echo -e "${RED}❌ OpenSearch 이미지 빌드 실패${NC}"
    exit 1
fi
echo ""

# 완료 메시지
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 모든 이미지 빌드 및 푸시 완료!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${GREEN}📋 푸시된 이미지 목록:${NC}"
echo -e "   ✅ ${FRONTEND_IMAGE}"
echo -e "   ✅ ${CLIENT_IMAGE}"
echo -e "   ✅ ${SERVER_IMAGE}"
echo -e "   ✅ ${OPENSEARCH_IMAGE}"
echo ""

# Docker Hub 확인 링크
echo -e "${BLUE}🔗 Docker Hub에서 확인:${NC}"
echo -e "   https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/crawler-mind-frontend/tags"
echo -e "   https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client/tags"
echo -e "   https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server/tags"
echo -e "   https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/opensearch-with-nori/tags"
echo ""

# 다음 단계 안내
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}🚀 다음 단계:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "1. ${YELLOW}이미지 태그 업데이트${NC}"
echo -e "   # 각 values.yaml에서 tag를 ${TAG}로 변경"
echo -e "   sed -i 's/tag: dev.*/tag: ${TAG}/' mcp-client-chart/values.yaml"
echo -e "   sed -i 's/tag: dev.*/tag: ${TAG}/' mcp-server-chart/values.yaml"
echo -e "   sed -i 's/tag: dev.*/tag: ${TAG}/' frontend-chart/values.yaml"
echo ""
echo -e "2. ${YELLOW}EC2로 파일 전송${NC}"
echo -e "   cd helm"
echo -e "   scp -i your-key.pem -r aws-ec2-k3s ubuntu@YOUR_EC2_IP:~/"
echo ""
echo -e "3. ${YELLOW}EC2에서 배포${NC}"
echo -e "   ssh -i your-key.pem ubuntu@YOUR_EC2_IP"
echo -e "   cd ~/aws-ec2-k3s"
echo -e "   ./deploy.sh"
echo ""
echo -e "4. ${YELLOW}오래된 이미지 정리 (선택사항)${NC}"
echo -e "   sudo k3s crictl rmi --prune"
echo ""

# 자동 태그 업데이트
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}📝 values.yaml 태그 자동 업데이트...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cd "${SCRIPT_DIR}"
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" mcp-client-chart/values.yaml
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" mcp-server-chart/values.yaml
sed -i.bak "s/tag: dev.*/tag: ${TAG}/" frontend-chart/values.yaml
rm -f mcp-client-chart/values.yaml.bak mcp-server-chart/values.yaml.bak frontend-chart/values.yaml.bak
echo -e "${GREEN}✅ 태그 업데이트 완료: ${TAG}${NC}"
echo ""
echo -e "${GREEN}✨ 행운을 빕니다!${NC}"
echo ""

