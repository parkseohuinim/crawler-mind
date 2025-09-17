# WSL Kubernetes 개발 환경 가이드

AKS 배포 전에 WSL 환경에서 Kubernetes로 예행 연습하는 가이드입니다.

기존 Cloudflare Tunnel을 그대로 사용하여 `https://crawler.alvinpark.xyz`로 접근할 수 있습니다.

## 🎯 목적
- AKS 배포 전 로컬에서 Helm Chart 테스트
- 기존 Cloudflare 도메인으로 실제 환경과 동일한 테스트
- 리소스 사용량 최적화 (메모리 ~6GB)

## 🚀 빠른 시작

### 1. 사전 준비
```bash
# K3s 설치 (추천 - AKS와 가장 유사)
curl -sfL https://get.k3s.io | sh -

# kubectl 설정
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc

# Cloudflared 설치
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Helm 설치 (없다면)
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### 2. 클러스터 확인
```bash
# K3s 클러스터 상태 확인
kubectl cluster-info
kubectl get nodes
kubectl get pods -A
```

### 3. 배포 모드 선택

#### 🧪 **개발 모드 (NodePort + Cloudflare)**
```bash
# 기본 배포 (NodePort 30000)
./deploy-wsl-k8s.sh seohuipark

# 별도 터미널에서 Cloudflare Tunnel 실행
cloudflared tunnel --url http://localhost:30000
```
접속: `https://crawler.alvinpark.xyz`

#### 🔍 **AKS 검증 모드 (Ingress + LoadBalancer)**
```bash
# AKS 환경과 동일하게 테스트
./deploy-wsl-k8s.sh seohuipark aks-dev true

# LoadBalancer IP 확인
kubectl get svc ingress-nginx-controller -n ingress-nginx
```
접속: `http://[LoadBalancer-IP]`

## 🔧 환경 설정

### WSL 환경 최적화
이 설정은 자동으로 적용됩니다 (`environment: wsl-dev`):

```yaml
# 리소스 사용량 50% 절약
frontend:
  replicaCount: 1
  resources:
    requests: { cpu: 250m, memory: 256Mi }
    limits: { cpu: 500m, memory: 512Mi }

mcpClient:
  replicaCount: 1
  resources:
    requests: { cpu: 500m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 1Gi }

# NodePort 고정
frontend:
  service:
    type: NodePort
    nodePort: 30000

# Ingress 비활성화 (NodePort 직접 사용)
ingress:
  enabled: false
```

## 🐛 트러블슈팅

### 메모리 부족 시
```bash
# 더 적은 리소스로 재배포
helm upgrade crawler-mind ../helm/crawler-mind \
  --set frontend.resources.limits.memory=256Mi \
  --set mcpClient.resources.limits.memory=512Mi \
  --set mcpServer.resources.limits.memory=512Mi
```

### NodePort 접근 안될 때
```bash
# 포트 포워딩 사용
kubectl port-forward svc/crawler-mind-frontend 3000:3000 -n crawler-mind

# 로컬 접근: http://localhost:3000
```

### Docker Hub 이미지 풀 실패
```bash
# Docker Hub 로그인 확인
docker login -u seohuipark

# 수동으로 이미지 풀
docker pull seohuipark/crawler-mind-frontend:dev
docker pull seohuipark/crawler-mind-mcp-client:dev
docker pull seohuipark/crawler-mind-mcp-server:dev
```

## 📊 리소스 사용량

### 예상 메모리 사용량
- Frontend: ~512MB
- MCP Client: ~1GB
- MCP Server: ~1GB
- PostgreSQL: ~1GB
- Qdrant: ~2GB
- OpenSearch: ~1GB
- **총합**: ~6GB

### 권장 시스템 사양
- **RAM**: 16GB 이상
- **CPU**: 8코어 이상
- **디스크**: 20GB 이상

## 🔄 배포 관리

### 업데이트
```bash
# 새 이미지로 업데이트
helm upgrade crawler-mind ../helm/crawler-mind \
  --set image.tag=latest

# 설정 변경
helm upgrade crawler-mind ../helm/crawler-mind \
  --set frontend.replicaCount=2
```

### 로그 확인
```bash
# Frontend 로그
kubectl logs -f deployment/crawler-mind-frontend -n crawler-mind

# MCP Client 로그
kubectl logs -f deployment/crawler-mind-mcp-client -n crawler-mind

# 모든 Pod 상태
kubectl get pods -n crawler-mind
```

### 완전 삭제
```bash
# Helm 릴리스 삭제
helm uninstall crawler-mind -n crawler-mind

# 네임스페이스 삭제
kubectl delete namespace crawler-mind

# Kind 클러스터 삭제
kind delete cluster --name crawler-mind
```

## 💡 팁

1. **메모리 절약**: OpenSearch 대신 외부 서비스 사용 고려
2. **네트워크**: WSL2의 경우 localhost 포트 포워딩 자동 설정
3. **개발**: 코드 변경 시 이미지 빌드 후 helm upgrade 실행
4. **디버깅**: kubectl describe로 상세 정보 확인

이제 WSL에서 완벽한 예행 연습을 한 후 AKS로 배포하세요! 🚀
