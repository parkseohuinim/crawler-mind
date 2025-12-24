# Crawler Mind - AWS EC2 K3s 배포 가이드

AI 기반 웹 크롤링 시스템을 AWS EC2 K3s 클러스터에 배포하는 가이드입니다.

---

## 📋 목차

1. [시스템 구성](#-시스템-구성)
2. [사전 준비](#-사전-준비)
3. [배포 전 설정](#-배포-전-설정)
4. [Docker 이미지 빌드](#-docker-이미지-빌드)
5. [배포 실행](#-배포-실행)
6. [배포 확인](#-배포-확인)
7. [문제 해결](#-문제-해결)

---

## 🏗 시스템 구성

### 배포되는 컴포넌트

```
┌─────────────────────────────────────────────┐
│           Cloudflare Tunnel                 │
│         (https://your-domain.com)           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              K3s Ingress                    │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼─────┐  ┌────▼────┐
│Frontend│  │MCP Client │  │MCP Server│
│(Next.js)│  │(FastAPI) │  │(Python) │
└────────┘  └─────┬─────┘  └─────────┘
                  │
       ┌──────────┼──────────┐
       │          │          │
   ┌───▼───┐  ┌──▼───┐  ┌──▼──┐
   │Qdrant │  │OpenS.│  │ RDS │
   │(Pod)  │  │(Pod) │  │(AWS)│
   └───────┘  └──────┘  └─────┘
```

### 주요 특징
- ✅ **RDS PostgreSQL**: AWS RDS 사용 (고가용성)
- ✅ **Qdrant**: 벡터 DB (클러스터 내 Pod)
- ✅ **OpenSearch**: 검색 엔진 (클러스터 내 Pod)
- ✅ **순차 배포**: MCP Server → MCP Client 순서 보장
- ✅ **자동 대기**: initContainer로 의존성 체크

---

## 🎯 사전 준비

### 1. 필요한 정보 수집

배포 전에 다음 정보를 준비하세요:

| 항목 | 설명 | 예시 |
|------|------|------|
| Docker Hub Username | Docker Hub 사용자명 | `seohuipark` |
| Cloudflare Domain | 도메인 주소 | `crawler.alvinpark.xyz` |
| RDS Endpoint | RDS 엔드포인트 | `crawler-mind-db.xxxxx.ap-northeast-2.rds.amazonaws.com` |
| RDS Password | RDS 비밀번호 | `MySecurePass123` |
| OpenAI API Key | OpenAI API 키 | `sk-proj-xxxxx...` |

### 2. 로컬 환경 요구사항

- Docker Desktop 설치
- kubectl 설치
- Helm 설치
- AWS CLI 설치 (선택사항)

### 3. EC2 인스턴스 요구사항

- **인스턴스 타입**: t3.large 이상 권장
- **OS**: Ubuntu 22.04 LTS
- **K3s**: 설치 완료
- **스토리지**: 최소 30GB

---

## ⚙️ 배포 전 설정

### 1단계: 설정 파일 확인

수정이 필요한 항목 찾기:

```bash
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind/helm/aws-ec2-k3s
grep -r "YOUR_" . --include="*.yaml"
```

### 2단계: 필수 설정 변경

#### 📁 `mcp-client-chart/values-secrets.yaml` (⚠️ 가장 중요!)

```yaml
env:
  OPENAI_API_KEY: "sk-proj-xxxxx..."  # 실제 OpenAI API 키
  DATABASE_URL: "postgresql+asyncpg://postgres:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/crawler_mind?ssl=require"
```

**⚠️ 주의**: 
- 비밀번호에 특수문자가 있으면 URL 인코딩 필요
- 예: `!` → `%21`, `@` → `%40`, `#` → `%23`

#### 📁 `mcp-client-chart/values.yaml`

```yaml
image:
  repository: YOUR_DOCKERHUB_USERNAME/crawler-mind-mcp-client
  tag: latest

env:
  DATABASE_URL: "postgresql+asyncpg://postgres:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/crawler_mind"
  OPENSEARCH_HOST: "http://opensearch:9200"  # 클러스터 내부 서비스
  QDRANT_HOST: "http://qdrant:6333"          # 클러스터 내부 서비스
```

#### 📁 `frontend-chart/values.yaml`

```yaml
image:
  repository: YOUR_DOCKERHUB_USERNAME/crawler-mind-frontend
  tag: latest

env:
  NEXT_PUBLIC_API_BASE_URL: "https://YOUR_DOMAIN/api"
```

#### 📁 `mcp-server-chart/values.yaml`

```yaml
image:
  repository: YOUR_DOCKERHUB_USERNAME/crawler-mind-mcp-server
  tag: latest
```

#### 📁 `ingress.yaml`

```yaml
spec:
  rules:
  - host: YOUR_DOMAIN  # 예: crawler.alvinpark.xyz
```

### 3단계: 보안 설정

**⚠️ 중요**: `values-secrets.yaml` 파일 보호

```bash
# Git에서 제외
echo "helm/aws-ec2-k3s/**/values-secrets.yaml" >> .gitignore

# 파일 권한 설정
chmod 600 mcp-client-chart/values-secrets.yaml
```

---

## 🐳 Docker 이미지 빌드

### 자동 빌드 스크립트 사용

```bash
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind/helm/aws-ec2-k3s

# Docker Hub 로그인
docker login

# 빌드 및 푸시 스크립트 실행
./build-and-push.sh
```

### 수동 빌드 (선택사항)

```bash
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind

export DOCKER_USERNAME="your-dockerhub-username"
export DOMAIN="crawler.yourdomain.com"

# Frontend
docker build -t $DOCKER_USERNAME/crawler-mind-frontend:latest \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://$DOMAIN/api \
  ./frontend
docker push $DOCKER_USERNAME/crawler-mind-frontend:latest

# MCP Client
docker build -t $DOCKER_USERNAME/crawler-mind-mcp-client:latest \
  -f mcp-client/Dockerfile .
docker push $DOCKER_USERNAME/crawler-mind-mcp-client:latest

# MCP Server
docker build -t $DOCKER_USERNAME/crawler-mind-mcp-server:latest \
  ./mcp-server
docker push $DOCKER_USERNAME/crawler-mind-mcp-server:latest
```

---

## 🚀 배포 실행

### 1단계: EC2로 파일 전송

```bash
# 로컬에서 실행
cd /Users/seohuipark/Desktop/Workspace/rag/crawler-mind/helm
scp -i your-key.pem -r aws-ec2-k3s ubuntu@YOUR_EC2_IP:~/

# 전송 확인
ssh -i your-key.pem ubuntu@YOUR_EC2_IP "ls -la ~/aws-ec2-k3s"
```

### 2단계: EC2에서 배포

```bash
# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 배포 디렉토리로 이동
cd ~/aws-ec2-k3s

# 배포 실행
./deploy.sh
```

### 배포 순서 (자동)

스크립트가 다음 순서로 자동 배포합니다:

```
1. Namespace 생성 (crawler-mind)
   ↓
2. Qdrant 배포 및 Ready 대기
   ↓
3. OpenSearch 배포 및 Ready 대기
   ↓
4. MCP Server 배포 및 Ready 대기
   ↓
5. MCP Client 배포 및 Ready 대기
   (initContainer가 MCP Server 연결 확인)
   ↓
6. Frontend 배포 및 Ready 대기
   ↓
7. Ingress 설정
```

**예상 소요 시간**: 약 10-15분

---

## ✅ 배포 확인

### 1. Pod 상태 확인

```bash
kubectl get pods -n crawler-mind

# 예상 출력 (모두 Running이어야 함):
# NAME                          READY   STATUS    RESTARTS   AGE
# frontend-xxx                  1/1     Running   0          2m
# mcp-client-xxx                1/1     Running   0          3m
# mcp-server-xxx                1/1     Running   0          5m
# opensearch-xxx                1/1     Running   0          8m
# qdrant-xxx                    1/1     Running   0          10m
```

### 2. 서비스 확인

```bash
kubectl get svc -n crawler-mind

# 예상 출력:
# NAME         TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)
# frontend     ClusterIP   10.43.x.x       <none>        3000/TCP
# mcp-client   ClusterIP   10.43.x.x       <none>        8000/TCP
# mcp-server   ClusterIP   10.43.x.x       <none>        4200/TCP
# opensearch   ClusterIP   10.43.x.x       <none>        9200/TCP
# qdrant       ClusterIP   10.43.x.x       <none>        6333/TCP
```

### 3. Ingress 확인

```bash
kubectl get ingress -n crawler-mind

# Ingress가 정상적으로 생성되었는지 확인
```

### 4. 로그 확인

```bash
# MCP Client 로그 (가장 중요)
kubectl logs -f deployment/mcp-client -n crawler-mind

# MCP Server 로그
kubectl logs -f deployment/mcp-server -n crawler-mind

# Frontend 로그
kubectl logs -f deployment/frontend -n crawler-mind

# OpenSearch 로그
kubectl logs -f deployment/opensearch -n crawler-mind

# Qdrant 로그
kubectl logs -f deployment/qdrant -n crawler-mind
```

### 5. 리소스 사용량 확인

```bash
kubectl top pods -n crawler-mind
kubectl top nodes
```

### 6. RDS 연결 테스트

```bash
# MCP Client Pod에서 RDS 연결 확인
kubectl exec -it deployment/mcp-client -n crawler-mind -- \
  python -c "import asyncio; from app.shared.database.connection import get_db; asyncio.run(get_db().__anext__())"
```

### 7. 웹 접속 테스트

브라우저에서 접속:
```
https://YOUR_DOMAIN
```

---

## 🔧 문제 해결

### Pod가 Pending 상태

```bash
# Pod 상세 정보 확인
kubectl describe pod POD_NAME -n crawler-mind

# 주요 원인:
# 1. 리소스 부족 → 노드 스케일업 또는 리소스 제한 조정
# 2. PVC 바인딩 실패 → StorageClass 확인
```

### OpenSearch 시작 실패

```bash
# vm.max_map_count 확인
sysctl vm.max_map_count

# 262144 미만이면 설정
sudo sysctl -w vm.max_map_count=262144

# 영구 적용
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### MCP Client가 MCP Server 연결 실패

```bash
# MCP Server가 Ready 상태인지 확인
kubectl get pods -n crawler-mind -l app=mcp-server

# MCP Server 로그 확인
kubectl logs deployment/mcp-server -n crawler-mind

# MCP Client initContainer 로그 확인
kubectl logs POD_NAME -n crawler-mind -c wait-for-mcp-server
```

### RDS 연결 실패

**1. Security Group 확인**
```bash
# EC2 인스턴스의 보안 그룹이 RDS 보안 그룹에 허용되어 있는지 확인
aws ec2 describe-security-groups --group-ids YOUR_RDS_SG_ID
```

**2. DATABASE_URL 형식 확인**
```yaml
# 올바른 형식:
DATABASE_URL: "postgresql+asyncpg://USER:PASSWORD@ENDPOINT:5432/DB_NAME?ssl=require"

# 특수문자 URL 인코딩:
! → %21
@ → %40
# → %23
$ → %24
% → %25
```

**3. RDS 엔드포인트 연결 테스트**
```bash
# EC2에서 직접 테스트
nc -zv YOUR_RDS_ENDPOINT 5432
```

### Qdrant 또는 OpenSearch 연결 실패

```bash
# 서비스 DNS 확인
kubectl exec -it deployment/mcp-client -n crawler-mind -- \
  nslookup qdrant

kubectl exec -it deployment/mcp-client -n crawler-mind -- \
  nslookup opensearch

# 직접 연결 테스트
kubectl exec -it deployment/mcp-client -n crawler-mind -- \
  curl http://qdrant:6333/health

kubectl exec -it deployment/mcp-client -n crawler-mind -- \
  curl http://opensearch:9200/_cluster/health
```

### 이미지 Pull 실패

```bash
# Docker Hub 로그인 확인
docker login

# 이미지가 실제로 푸시되었는지 확인
docker pull YOUR_DOCKERHUB_USERNAME/crawler-mind-mcp-client:latest

# imagePullPolicy 확인
kubectl describe pod POD_NAME -n crawler-mind | grep -i pull
```

### 메모리 부족 (OOMKilled)

```bash
# Pod 이벤트 확인
kubectl describe pod POD_NAME -n crawler-mind

# 리소스 제한 증가 (values.yaml)
resources:
  limits:
    memory: 4Gi  # 기존보다 증가
```

### Cloudflare Tunnel 연결 실패

```bash
# Cloudflared 상태 확인
sudo systemctl status cloudflared

# 로그 확인
sudo journalctl -u cloudflared -f

# 재시작
sudo systemctl restart cloudflared
```

---

## 🔄 업데이트 및 재배포

### 코드 변경 후 재배포

```bash
# 1. 새 이미지 빌드 및 푸시
./build-and-push.sh

# 2. 특정 컴포넌트만 재배포
helm upgrade mcp-client ./mcp-client-chart \
  -n crawler-mind \
  -f ./mcp-client-chart/values-secrets.yaml

# 3. 전체 재배포
./deploy.sh
```

### 설정 변경 후 재배포

```bash
# values.yaml 수정 후
helm upgrade mcp-client ./mcp-client-chart \
  -n crawler-mind \
  -f ./mcp-client-chart/values-secrets.yaml
```

### 롤백

```bash
# 이전 버전으로 롤백
helm rollback mcp-client -n crawler-mind

# 특정 리비전으로 롤백
helm rollback mcp-client 2 -n crawler-mind

# 히스토리 확인
helm history mcp-client -n crawler-mind
```

---

## 🗑 삭제

### 전체 삭제

```bash
# 모든 Helm 릴리스 삭제
helm uninstall frontend -n crawler-mind
helm uninstall mcp-client -n crawler-mind
helm uninstall mcp-server -n crawler-mind
helm uninstall opensearch -n crawler-mind
helm uninstall qdrant -n crawler-mind

# Namespace 삭제 (PVC도 함께 삭제됨)
kubectl delete namespace crawler-mind
```

### 특정 컴포넌트만 삭제

```bash
helm uninstall mcp-client -n crawler-mind
```

---

## 📊 모니터링

### 리소스 모니터링

```bash
# 실시간 리소스 사용량
watch kubectl top pods -n crawler-mind

# 노드 리소스
kubectl top nodes
```

### 로그 모니터링

```bash
# 전체 로그 스트리밍
kubectl logs -f -n crawler-mind --all-containers=true

# 특정 Pod 로그
kubectl logs -f deployment/mcp-client -n crawler-mind --tail=100
```

### 이벤트 모니터링

```bash
# 최근 이벤트 확인
kubectl get events -n crawler-mind --sort-by='.lastTimestamp'

# 실시간 이벤트 모니터링
kubectl get events -n crawler-mind --watch
```

---

## 📚 추가 정보

### 주요 파일 구조

```
aws-ec2-k3s/
├── deploy.sh                    # 통합 배포 스크립트
├── build-and-push.sh           # Docker 이미지 빌드 스크립트
├── ingress.yaml                # Ingress 설정
├── frontend-chart/             # Frontend Helm Chart
├── mcp-client-chart/           # MCP Client Helm Chart
│   ├── values.yaml            # 기본 설정
│   └── values-secrets.yaml    # 민감 정보 (Git 제외)
├── mcp-server-chart/           # MCP Server Helm Chart
├── opensearch-chart/           # OpenSearch Helm Chart
└── qdrant-chart/               # Qdrant Helm Chart
```

### 환경별 설정

**개발 환경**:
- `values.yaml`에서 `replicaCount: 1`
- 리소스 제한 낮게 설정

**프로덕션 환경**:
- `replicaCount: 2` 이상
- HPA(Horizontal Pod Autoscaler) 활성화
- 리소스 제한 적절히 설정
- Kubernetes Secrets 사용 (values-secrets.yaml 대신)

---

## 🆘 지원

문제가 발생하면:

1. **로그 확인**: `kubectl logs -f deployment/POD_NAME -n crawler-mind`
2. **이벤트 확인**: `kubectl get events -n crawler-mind --sort-by='.lastTimestamp'`
3. **리소스 확인**: `kubectl top pods -n crawler-mind`
4. **Pod 상세 정보**: `kubectl describe pod POD_NAME -n crawler-mind`

---

## 📝 체크리스트

배포 전 확인:

- [ ] Docker Hub 사용자명 변경 (3개 chart)
- [ ] Cloudflare 도메인 변경 (frontend, mcp-client, ingress)
- [ ] RDS 엔드포인트 변경 (mcp-client)
- [ ] RDS 비밀번호 변경 (mcp-client)
- [ ] OpenAI API 키 변경 (mcp-client)
- [ ] Docker 이미지 빌드 및 푸시 완료
- [ ] EC2에 파일 전송 완료
- [ ] K3s 클러스터 정상 동작 확인

배포 후 확인:

- [ ] 모든 Pod가 Running 상태
- [ ] 서비스가 정상적으로 생성됨
- [ ] Ingress가 정상적으로 생성됨
- [ ] 웹 브라우저에서 접속 가능
- [ ] RDS 연결 정상
- [ ] Qdrant, OpenSearch 연결 정상
