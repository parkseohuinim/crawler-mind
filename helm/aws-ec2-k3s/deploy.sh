#!/bin/bash

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🚀 Crawler Mind AWS EC2 K3s 배포 시작...${NC}"
echo ""

# 현재 디렉토리 확인
if [ ! -f "deploy.sh" ]; then
    echo -e "${RED}❌ 잘못된 디렉토리입니다. aws-ec2-k3s 디렉토리에서 실행하세요.${NC}"
    exit 1
fi

# kubectl 확인
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl이 설치되지 않았습니다.${NC}"
    exit 1
fi

# Helm 확인
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm이 설치되지 않았습니다.${NC}"
    exit 1
fi

# Namespace 생성
echo -e "${YELLOW}📦 Namespace 생성...${NC}"
kubectl create namespace crawler-mind --dry-run=client -o yaml | kubectl apply -f -
echo -e "${GREEN}✅ Namespace 생성 완료${NC}"
echo ""

# 오래된 이미지 자동 정리
echo -e "${YELLOW}🧹 오래된 이미지 정리 중...${NC}"
sudo k3s crictl rmi --prune 2>/dev/null || true
echo -e "${GREEN}✅ 이미지 정리 완료${NC}"
echo ""

# 1. Qdrant 배포
echo -e "${YELLOW}📊 Qdrant 배포 중...${NC}"
helm upgrade --install qdrant ./qdrant-chart -n crawler-mind
echo -e "${GREEN}✅ Qdrant 배포 완료${NC}"
echo "⏳ Qdrant 초기화 대기 (15초)..."
sleep 15
echo ""

# 2. OpenSearch 배포
echo -e "${YELLOW}🔍 OpenSearch 배포 중...${NC}"
helm upgrade --install opensearch ./opensearch-chart -n crawler-mind
echo -e "${GREEN}✅ OpenSearch 배포 완료${NC}"
echo "⏳ OpenSearch 초기화 대기 (45초)..."
sleep 45
echo ""

# 3. MCP Server 배포
echo -e "${YELLOW}🤖 MCP Server 배포 중...${NC}"
helm upgrade --install mcp-server ./mcp-server-chart -n crawler-mind
echo -e "${GREEN}✅ MCP Server 배포 완료${NC}"
echo "⏳ MCP Server 초기화 대기 (15초)..."
sleep 15
echo ""

# 4. MCP Client 배포
echo -e "${YELLOW}⚡ MCP Client 배포 중...${NC}"
helm upgrade --install mcp-client ./mcp-client-chart \
  -f ./mcp-client-chart/values-secrets.yaml \
  -n crawler-mind
echo -e "${GREEN}✅ MCP Client 배포 완료${NC}"
echo "⏳ MCP Client 초기화 대기 (20초)..."
sleep 20
echo ""

# 5. Frontend 배포
echo -e "${YELLOW}🌐 Frontend 배포 중...${NC}"
helm upgrade --install frontend ./frontend-chart -n crawler-mind
echo -e "${GREEN}✅ Frontend 배포 완료${NC}"
echo "⏳ Frontend 초기화 대기 (15초)..."
sleep 15
echo ""

# 6. Ingress 배포
echo -e "${YELLOW}🌐 Ingress 설정 중...${NC}"
if [ -f "ingress.yaml" ]; then
    kubectl apply -f ingress.yaml
    echo -e "${GREEN}✅ Ingress 설정 완료${NC}"
else
    echo -e "${YELLOW}⚠️  ingress.yaml 파일이 없습니다. 수동으로 설정하세요.${NC}"
fi
echo ""

# 배포 상태 확인
echo -e "${YELLOW}📋 배포 상태 확인${NC}"
echo ""
kubectl get pods -n crawler-mind
echo ""
kubectl get svc -n crawler-mind
echo ""

echo -e "${GREEN}✅ 배포 완료!${NC}"
echo ""

# 실패한 Pod 자동 정리
echo -e "${YELLOW}🧹 실패한 Pod 정리 중...${NC}"
kubectl delete pods --field-selector=status.phase=Failed -n crawler-mind 2>/dev/null || true
echo -e "${GREEN}✅ 정리 완료${NC}"
echo ""

echo "다음 명령어로 상태를 확인하세요:"
echo "  kubectl get pods -n crawler-mind"
echo "  kubectl logs -f -n crawler-mind deployment/mcp-client"
echo "  kubectl top pods -n crawler-mind"
echo ""
echo "모든 Pod가 Running 상태가 될 때까지 2-3분 정도 소요될 수 있습니다."

