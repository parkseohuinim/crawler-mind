#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Crawler Mind 배포 스크립트${NC}"
echo -e "${BLUE}========================================${NC}"

# 네임스페이스 확인
NAMESPACE="crawler-mind"
echo -e "\n${YELLOW}[1/6] 네임스페이스 확인...${NC}"
kubectl get namespace $NAMESPACE &> /dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}네임스페이스 생성 중...${NC}"
    kubectl create namespace $NAMESPACE
fi
echo -e "${GREEN}✅ 네임스페이스 준비 완료${NC}"

# Qdrant 배포
echo -e "\n${YELLOW}[2/6] Qdrant 배포 중...${NC}"
helm upgrade --install qdrant ./qdrant-chart \
    --namespace $NAMESPACE \
    --wait \
    --timeout 5m
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Qdrant 배포 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Qdrant 배포 완료${NC}"

# Qdrant가 완전히 준비될 때까지 대기
echo -e "\n${YELLOW}Qdrant가 준비될 때까지 대기 중...${NC}"
kubectl wait --for=condition=ready pod \
    -l app=qdrant \
    -n $NAMESPACE \
    --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Qdrant 준비 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Qdrant 준비 완료${NC}"

# OpenSearch 배포
echo -e "\n${YELLOW}[3/6] OpenSearch 배포 중...${NC}"
helm upgrade --install opensearch ./opensearch-chart \
    --namespace $NAMESPACE \
    --wait \
    --timeout 10m
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ OpenSearch 배포 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ OpenSearch 배포 완료${NC}"

# OpenSearch가 완전히 준비될 때까지 대기
echo -e "\n${YELLOW}OpenSearch가 준비될 때까지 대기 중...${NC}"
kubectl wait --for=condition=ready pod \
    -l app=opensearch \
    -n $NAMESPACE \
    --timeout=600s
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ OpenSearch 준비 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ OpenSearch 준비 완료${NC}"

# MCP Server 배포
echo -e "\n${YELLOW}[4/6] MCP Server 배포 중...${NC}"
helm upgrade --install mcp-server ./mcp-server-chart \
    --namespace $NAMESPACE \
    --wait \
    --timeout 5m
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MCP Server 배포 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MCP Server 배포 완료${NC}"

# MCP Server가 완전히 준비될 때까지 대기
echo -e "\n${YELLOW}MCP Server가 준비될 때까지 대기 중...${NC}"
kubectl wait --for=condition=ready pod \
    -l app=mcp-server \
    -n $NAMESPACE \
    --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MCP Server 준비 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MCP Server 준비 완료${NC}"

# MCP Client 배포
echo -e "\n${YELLOW}[5/6] MCP Client 배포 중...${NC}"
helm upgrade --install mcp-client ./mcp-client-chart \
    --namespace $NAMESPACE \
    -f ./mcp-client-chart/values-secrets.yaml \
    --wait \
    --timeout 10m
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MCP Client 배포 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MCP Client 배포 완료${NC}"

# MCP Client가 완전히 준비될 때까지 대기
echo -e "\n${YELLOW}MCP Client가 준비될 때까지 대기 중...${NC}"
kubectl wait --for=condition=ready pod \
    -l app=mcp-client \
    -n $NAMESPACE \
    --timeout=600s
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MCP Client 준비 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MCP Client 준비 완료${NC}"

# Frontend 배포
echo -e "\n${YELLOW}[6/6] Frontend 배포 중...${NC}"
helm upgrade --install frontend ./frontend-chart \
    --namespace $NAMESPACE \
    --wait \
    --timeout 5m
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend 배포 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend 배포 완료${NC}"

# Frontend가 완전히 준비될 때까지 대기
echo -e "\n${YELLOW}Frontend가 준비될 때까지 대기 중...${NC}"
kubectl wait --for=condition=ready pod \
    -l app=frontend \
    -n $NAMESPACE \
    --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Frontend 준비 실패${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend 준비 완료${NC}"

# Ingress 배포
echo -e "\n${YELLOW}Ingress 설정 중...${NC}"
if [ -f "ingress.yaml" ]; then
    kubectl apply -f ingress.yaml -n $NAMESPACE
    echo -e "${GREEN}✅ Ingress 설정 완료${NC}"
else
    echo -e "${YELLOW}⚠️  ingress.yaml 파일이 없습니다.${NC}"
fi

# 전체 상태 확인
echo -e "\n${YELLOW}전체 Pod 상태 확인...${NC}"
kubectl get pods -n $NAMESPACE

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  배포 완료!${NC}"
echo -e "${GREEN}========================================${NC}"

# 서비스 확인
echo -e "\n${BLUE}서비스 목록:${NC}"
kubectl get svc -n $NAMESPACE

# 로그 확인 안내
echo -e "\n${BLUE}로그 확인 명령어:${NC}"
echo -e "  Qdrant:     ${YELLOW}kubectl logs -f deployment/qdrant -n $NAMESPACE${NC}"
echo -e "  OpenSearch: ${YELLOW}kubectl logs -f deployment/opensearch -n $NAMESPACE${NC}"
echo -e "  MCP Server: ${YELLOW}kubectl logs -f deployment/mcp-server -n $NAMESPACE${NC}"
echo -e "  MCP Client: ${YELLOW}kubectl logs -f deployment/mcp-client -n $NAMESPACE${NC}"
echo -e "  Frontend:   ${YELLOW}kubectl logs -f deployment/frontend -n $NAMESPACE${NC}"

echo -e "\n${BLUE}RDS 연결 정보:${NC}"
echo -e "  - RDS 엔드포인트와 비밀번호는 ${YELLOW}mcp-client-chart/values-secrets.yaml${NC}에서 관리됩니다."
echo -e "  - DATABASE_URL 형식: postgresql+asyncpg://USER:PASSWORD@ENDPOINT:5432/DB_NAME"
