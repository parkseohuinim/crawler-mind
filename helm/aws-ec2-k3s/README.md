# AWS EC2 K3s 배포 가이드

Crawler Mind를 AWS EC2 단일 노드 K3s 환경에 배포하는 완전 가이드입니다.

## 📋 사전 준비

- **EC2**: t3.large (2 vCPU, 8GB RAM), Ubuntu 24.04, 100GB EBS
- **RDS**: PostgreSQL 15
- **Docker Hub** 계정
- **Cloudflare** 도메인
- **OpenAI** API Key

---

## 🚀 배포 단계

### 1️⃣ 설정 파일 수정 (5분)

다음 값들을 실제 값으로 변경하세요:

```bash
# 수정이 필요한 모든 항목 확인
grep -r "YOUR_" . --include="*.yaml"
```

| 파일 | 변경 항목 | 예시 |
|------|----------|------|
| `frontend-chart/values.yaml` | `YOUR_DOCKERHUB_USERNAME` | `seohuipark` |
| `frontend-chart/values.yaml` | `YOUR_DOMAIN` | `alvinpark.xyz` |
| `mcp-client-chart/values.yaml` | `YOUR_DOCKERHUB_USERNAME` | `seohuipark` |
| `mcp-client-chart/values.yaml` | `YOUR_RDS_ENDPOINT` | `xxx.rds.amazonaws.com` |
| `mcp-client-chart/values.yaml` | `YOUR_RDS_PASSWORD` | RDS 비밀번호 |
| `mcp-client-chart/values.yaml` | `YOUR_OPENAI_API_KEY` | `sk-proj-xxx` |
| `mcp-client-chart/values-secrets.yaml` | 위와 동일 | 위와 동일 |
| `mcp-server-chart/values.yaml` | `YOUR_DOCKERHUB_USERNAME` | `seohuipark` |
| `ingress.yaml` | `YOUR_DOMAIN` (4곳) | `alvinpark.xyz` |

---

### 2️⃣ Docker 이미지 빌드 (30분)

```bash
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind

# Docker Hub 로그인
docker login

# 환경변수 설정
export DOCKER_USERNAME="your-dockerhub-username"
export DOMAIN="your-domain.com"

# Frontend 빌드 (Next.js)
docker build -t $DOCKER_USERNAME/crawler-mind-frontend:dev \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.$DOMAIN/api \
  ./frontend
docker push $DOCKER_USERNAME/crawler-mind-frontend:dev

# MCP Client 빌드 (FastAPI)
docker build -t $DOCKER_USERNAME/crawler-mind-mcp-client:dev \
  -f mcp-client/Dockerfile .
docker push $DOCKER_USERNAME/crawler-mind-mcp-client:dev

# MCP Server 빌드 (FastMCP)
docker build -t $DOCKER_USERNAME/crawler-mind-mcp-server:dev \
  ./mcp-server
docker push $DOCKER_USERNAME/crawler-mind-mcp-server:dev

# OpenSearch with Nori (한글 형태소 분석기)
cd opensearch
docker buildx build --platform linux/amd64 \
  -t $DOCKER_USERNAME/opensearch-with-nori:2.13.0 .
docker push $DOCKER_USERNAME/opensearch-with-nori:2.13.0
```

---

### 3️⃣ EC2 초기 설정 (10분)

```bash
# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# K3s 설치
curl -sfL https://get.k3s.io | sh -s - \
  --write-kubeconfig-mode 644 \
  --node-name crawler-mind-node

# kubectl 설정
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
export KUBECONFIG=~/.kube/config

# Helm 설치
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# 확인
kubectl get nodes
helm version
```

---

### 4️⃣ 파일 전송 및 배포 (10분)

```bash
# 로컬에서 EC2로 파일 전송
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind/helm
scp -i your-key.pem -r aws-ec2-k3s ubuntu@YOUR_EC2_IP:~/

# EC2에서 배포
cd ~/aws-ec2-k3s
chmod +x deploy.sh
./deploy.sh

# 배포 확인
kubectl get pods -n crawler-mind -w
```

**배포 순서** (자동):
1. Namespace 생성
2. Qdrant (Vector DB)
3. OpenSearch (검색 엔진)
4. MCP Server (크롤링 도구)
5. MCP Client (API 서버)
6. Frontend (Next.js)
7. Ingress (Traefik)

---

### 5️⃣ Cloudflare Tunnel 설정 (15분)

```bash
# Cloudflared 설치
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Cloudflare 로그인 (브라우저 인증)
cloudflared tunnel login

# Tunnel 생성
cloudflared tunnel create crawler-mind-k3s

# Tunnel ID 확인
TUNNEL_ID=$(cloudflared tunnel list | grep crawler-mind-k3s | awk '{print $1}')
echo "Tunnel ID: $TUNNEL_ID"

# 설정 파일 생성
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: /home/ubuntu/.cloudflared/${TUNNEL_ID}.json

ingress:
  - hostname: crawler.YOUR_DOMAIN
    service: http://127.0.0.1:32559
  
  - hostname: api.YOUR_DOMAIN
    service: http://127.0.0.1:32559
  
  - hostname: qdrant.YOUR_DOMAIN
    service: http://127.0.0.1:32559
  
  - hostname: opensearch.YOUR_DOMAIN
    service: http://127.0.0.1:32559
  
  - service: http_status:404
EOF

# DNS 레코드 생성 (또는 Cloudflare Dashboard에서 수동 설정)
cloudflared tunnel route dns ${TUNNEL_ID} crawler.YOUR_DOMAIN
cloudflared tunnel route dns ${TUNNEL_ID} api.YOUR_DOMAIN
cloudflared tunnel route dns ${TUNNEL_ID} qdrant.YOUR_DOMAIN
cloudflared tunnel route dns ${TUNNEL_ID} opensearch.YOUR_DOMAIN

# 서비스 등록 및 시작
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# 상태 확인
sudo systemctl status cloudflared
```

**중요**: Cloudflare Dashboard에서 DNS 레코드의 Tunnel ID가 새로 생성한 Tunnel ID와 일치하는지 확인하세요!

---

### 6️⃣ 접속 테스트 (5분)

```bash
# 로컬 테스트 (EC2에서)
curl -H "Host: api.YOUR_DOMAIN" http://127.0.0.1:32559/health

# 외부 접속 테스트
curl https://api.YOUR_DOMAIN/health
curl https://qdrant.YOUR_DOMAIN
curl https://opensearch.YOUR_DOMAIN

# 브라우저 접속
# https://crawler.YOUR_DOMAIN
# https://api.YOUR_DOMAIN/docs
```

---

## 🎉 완료!

모든 서비스가 정상 작동합니다!

### 접속 URL
- **Frontend**: https://crawler.YOUR_DOMAIN
- **API Docs**: https://api.YOUR_DOMAIN/docs
- **Qdrant**: https://qdrant.YOUR_DOMAIN/dashboard
- **OpenSearch**: https://opensearch.YOUR_DOMAIN

---

## 🛠️ 관리 명령어

### 기본 명령어

```bash
# Pod 상태 확인
kubectl get pods -n crawler-mind

# 로그 확인
kubectl logs -f -n crawler-mind deployment/mcp-client
kubectl logs -f -n crawler-mind deployment/frontend

# 재시작
kubectl rollout restart deployment/mcp-client -n crawler-mind

# 리소스 사용량
kubectl top pods -n crawler-mind
kubectl top nodes

# 전체 삭제
kubectl delete namespace crawler-mind
```

### MCP Client 재기동

```bash
# 가장 간단한 방법 (권장)
kubectl rollout restart deployment/mcp-client -n crawler-mind

# 또는 Pod 삭제 (자동으로 재생성됨)
kubectl delete pod -l app=mcp-client -n crawler-mind

# 재시작 상태 확인
kubectl rollout status deployment/mcp-client -n crawler-mind
kubectl get pods -n crawler-mind
```

**MCP Server 재기동 시**:
- MCP Client에 자동 재연결 로직이 추가되어 있어 Server 재시작 후에도 자동으로 재연결됩니다
- Init Container가 Server 준비를 기다리므로 안전하게 동시에 재시작 가능합니다

---

## 💡 트러블슈팅

### Pod가 Pending 상태
```bash
kubectl describe pod POD_NAME -n crawler-mind
# 원인: 디스크 부족, 리소스 부족
# 해결: EBS 볼륨 확장 또는 리소스 조정
```

### Disk Pressure 에러
```bash
# EBS 볼륨 확장 (AWS Console)
# 파일시스템 확장
sudo growpart /dev/nvme0n1 1
sudo resize2fs /dev/nvme0n1p1

# Taint 제거
kubectl taint nodes crawler-mind-node node.kubernetes.io/disk-pressure:NoSchedule-
```

### OpenSearch 시작 실패
```bash
# vm.max_map_count 확인 및 설정
sysctl vm.max_map_count
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### RDS 연결 실패
```bash
# Security Group 확인
# RDS SG Inbound: PostgreSQL (5432) from EC2 Private IP

# 연결 테스트
psql -h YOUR_RDS_ENDPOINT -U postgres -d crawler_mind -c "SELECT 1;"
```

### Cloudflare Tunnel 530 에러
```bash
# 1. Tunnel 상태 확인
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -f

# 2. DNS 레코드 확인 (Cloudflare Dashboard)
# CNAME이 올바른 Tunnel ID를 가리키는지 확인

# 3. Traefik NodePort 확인
kubectl get svc -n kube-system traefik
# 80:32559/TCP 확인

# 4. 로컬 테스트
curl -H "Host: api.YOUR_DOMAIN" http://127.0.0.1:32559/health
```

### 이미지 아키텍처 불일치 (exec format error)
```bash
# Mac에서 빌드 시 반드시 --platform 지정
docker buildx build --platform linux/amd64 -t IMAGE_NAME .
```

---

## 📊 리소스 할당 (t3.large 기준)

| 서비스 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|--------|-------------|-----------|----------------|--------------|
| Frontend | 250m | 500m | 512Mi | 1Gi |
| MCP Client | 250m | 1000m | 1Gi | 3Gi |
| MCP Server | 250m | 500m | 256Mi | 512Mi |
| OpenSearch | - | - | - | - |
| Qdrant | - | - | - | - |
| **총계** | **~1 CPU** | **~2.5 CPU** | **~2GB** | **~5GB** |

---

## 🔐 보안 주의사항

⚠️ **민감 정보 관리**:
- `values-secrets.yaml`을 Git에 커밋하지 마세요
- `.gitignore`에 추가하세요
- 프로덕션에서는 AWS Secrets Manager 사용 권장

```bash
# .gitignore에 추가
echo "helm/aws-ec2-k3s/**/values-secrets.yaml" >> .gitignore
```

---

## 📁 디렉토리 구조

```
aws-ec2-k3s/
├── README.md                    # 이 파일
├── deploy.sh                    # 자동 배포 스크립트
├── ingress.yaml                 # Traefik Ingress 설정
├── frontend-chart/              # Next.js Frontend
├── mcp-client-chart/            # FastAPI Backend
├── mcp-server-chart/            # FastMCP Server
├── qdrant-chart/                # Vector Database
└── opensearch-chart/            # Search Engine
```

---

## 🔄 코드 수정 후 업데이트 방법

### 방법 1: 코드 변경 시 (이미지 재빌드 필요)

```bash
# 1. 로컬에서 이미지 재빌드 및 푸시
cd helm/aws-ec2-k3s
./build-and-push.sh seohuipark alvinpark.xyz

# 2. EC2에서 이미지 업데이트 및 재배포
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 특정 서비스만 업데이트
kubectl set image deployment/mcp-client mcp-client=seohuipark/crawler-mind-mcp-client:dev -n crawler-mind
kubectl set image deployment/frontend frontend=seohuipark/crawler-mind-frontend:dev -n crawler-mind
kubectl set image deployment/mcp-server mcp-server=seohuipark/crawler-mind-mcp-server:dev -n crawler-mind

# 또는 전체 재배포
cd ~/aws-ec2-k3s
helm upgrade mcp-client ./mcp-client-chart -f ./mcp-client-chart/values-secrets.yaml -n crawler-mind
helm upgrade frontend ./frontend-chart -n crawler-mind
helm upgrade mcp-server ./mcp-server-chart -n crawler-mind

# Pod 재시작 확인
kubectl get pods -n crawler-mind -w
```

### 방법 2: 설정 파일만 변경 시 (이미지 재빌드 불필요)

```bash
# 1. 로컬에서 설정 파일 수정 후 전송
cd helm
scp -i your-key.pem -r aws-ec2-k3s ubuntu@YOUR_EC2_IP:~/

# 2. EC2에서 Helm 업그레이드
cd ~/aws-ec2-k3s
helm upgrade mcp-client ./mcp-client-chart -f ./mcp-client-chart/values-secrets.yaml -n crawler-mind
kubectl rollout restart deployment/mcp-client -n crawler-mind
```

### 빠른 재시작 (이미지는 그대로, Pod만 재시작)

```bash
# EC2에서
kubectl rollout restart deployment/mcp-client -n crawler-mind
kubectl rollout restart deployment/frontend -n crawler-mind
kubectl rollout restart deployment/mcp-server -n crawler-mind

# 또는 전체 재시작
kubectl rollout restart deployment -n crawler-mind
```

### 이미지 캐시 문제 해결

```bash
# EC2에서 - 이미지를 강제로 다시 pull
kubectl delete pod -n crawler-mind -l app=mcp-client

# 또는 imagePullPolicy 확인
kubectl get deployment mcp-client -n crawler-mind -o yaml | grep imagePullPolicy
# Always로 설정되어 있으면 항상 최신 이미지를 pull합니다
```

---

## 📞 지원

문제 발생 시:
1. Pod 로그 확인: `kubectl logs -f -n crawler-mind deployment/POD_NAME`
2. 이벤트 확인: `kubectl get events -n crawler-mind --sort-by='.lastTimestamp'`
3. 리소스 확인: `kubectl top pods -n crawler-mind`
4. Cloudflare Tunnel 로그: `sudo journalctl -u cloudflared -f`
