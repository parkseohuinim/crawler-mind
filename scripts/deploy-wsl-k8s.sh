#!/bin/bash
set -e

echo "🚀 WSL K3s에서 Crawler Mind 배포 시작..."

# 변수 설정
DOCKER_HUB_USERNAME=${1:-"seohuipark"}
NAMESPACE="crawler-mind"
HELM_RELEASE="crawler-mind"
ENVIRONMENT=${2:-"wsl-dev"}
ENABLE_INGRESS=${3:-"false"}

if [ -z "$1" ]; then
    echo "⚠️  Docker Hub 사용자명이 지정되지 않았습니다. 기본값 '${DOCKER_HUB_USERNAME}' 사용"
fi

echo "Usage: ./deploy-wsl-k8s.sh [DOCKER_HUB_USERNAME] [ENVIRONMENT] [ENABLE_INGRESS]"
echo "  ENVIRONMENT: wsl-dev (default), aks-dev (AKS 검증용)"
echo "  ENABLE_INGRESS: false (default), true (Ingress 테스트용)"
echo ""
echo "📦 Docker Hub 사용자: ${DOCKER_HUB_USERNAME}"
echo "🌍 환경: ${ENVIRONMENT}"
echo "🌐 Ingress 활성화: ${ENABLE_INGRESS}"

# 스크립트 위치 기준으로 helm 차트 경로 설정
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELM_CHART_DIR="${SCRIPT_DIR}/../helm/crawler-mind"

# K3s 클러스터 확인
echo "🔗 K3s 클러스터 연결 확인 중..."
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Kubernetes 클러스터에 연결할 수 없습니다."
    echo "K3s를 설치하세요:"
    echo "curl -sfL https://get.k3s.io | sh -"
    echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
    exit 1
fi

# NGINX Ingress Controller 설치 (AKS 검증용)
if [ "${ENABLE_INGRESS}" = "true" ]; then
    echo "🌐 NGINX Ingress Controller 확인 중..."
    if ! kubectl get ingressclass nginx &> /dev/null; then
        echo "📥 NGINX Ingress Controller 설치 중..."
        helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
        helm repo update
        helm install ingress-nginx ingress-nginx/ingress-nginx \
            --namespace ingress-nginx \
            --create-namespace \
            --set controller.service.type=LoadBalancer
        
        echo "⏳ Ingress Controller 준비 대기 중..."
        kubectl wait --namespace ingress-nginx \
            --for=condition=ready pod \
            --selector=app.kubernetes.io/component=controller \
            --timeout=300s
    fi
fi

# 네임스페이스 생성
echo "📁 네임스페이스 생성 중..."
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# Docker Hub 로그인 확인
echo "🔐 Docker Hub 로그인 확인 중..."
if ! docker info | grep -q "Username: ${DOCKER_HUB_USERNAME}"; then
    echo "🔑 Docker Hub 로그인이 필요합니다."
    docker login -u ${DOCKER_HUB_USERNAME}
fi

# 이미지 풀
echo "📦 Docker Hub에서 이미지 풀 중..."
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-frontend:dev
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-client:dev
docker pull ${DOCKER_HUB_USERNAME}/crawler-mind-mcp-server:dev

# Helm 차트 배포
echo "🚀 Helm 차트로 서비스 배포 중..."
helm upgrade --install ${HELM_RELEASE} ${HELM_CHART_DIR} \
  --namespace ${NAMESPACE} \
  --set environment=${ENVIRONMENT} \
  --set image.repository=${DOCKER_HUB_USERNAME} \
  --set image.tag=dev \
  --wait \
  --timeout=10m

# 배포 상태 확인
echo "📊 배포 상태 확인 중..."
kubectl get pods -n ${NAMESPACE}
kubectl get svc -n ${NAMESPACE}

# 접속 정보 출력
echo ""
echo "🎉 배포 완료!"

if [ "${ENABLE_INGRESS}" = "true" ]; then
    # Ingress 모드
    echo "🌐 Ingress 모드로 배포됨 (AKS 검증용)"
    kubectl get ingress ${HELM_RELEASE} -n ${NAMESPACE} 2>/dev/null || echo "   Ingress 정보를 확인 중..."
    
    # LoadBalancer IP 확인
    EXTERNAL_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    if [ "$EXTERNAL_IP" != "pending" ] && [ -n "$EXTERNAL_IP" ]; then
        echo "   - 외부 IP: ${EXTERNAL_IP}"
        echo "   - 웹 접근: http://${EXTERNAL_IP}"
        echo "   - API 문서: http://${EXTERNAL_IP}/api/docs"
    else
        echo "   - LoadBalancer IP 할당 대기 중..."
        echo "   - 확인: kubectl get svc ingress-nginx-controller -n ingress-nginx"
    fi
else
    # NodePort 모드 (기본)
    FRONTEND_NODEPORT=$(kubectl get svc ${HELM_RELEASE}-frontend -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30000")
    echo "🔌 NodePort 모드로 배포됨"
    echo "   - Frontend NodePort: ${FRONTEND_NODEPORT}"
    echo "   - 로컬 접근: http://localhost:${FRONTEND_NODEPORT}"
    echo ""
    echo "📋 Cloudflare Tunnel 연결 (별도 터미널에서 실행):"
    echo "   cloudflared tunnel --url http://localhost:${FRONTEND_NODEPORT}"
fi
echo ""
echo "🔧 유용한 명령어:"
echo "   - 로그 확인: kubectl logs -f deployment/${HELM_RELEASE}-frontend -n ${NAMESPACE}"
echo "   - 서비스 상태: kubectl get all -n ${NAMESPACE}"
echo "   - 포트 포워딩: kubectl port-forward svc/${HELM_RELEASE}-frontend 3000:3000 -n ${NAMESPACE}"
echo "   - 배포 삭제: helm uninstall ${HELM_RELEASE} -n ${NAMESPACE}"
