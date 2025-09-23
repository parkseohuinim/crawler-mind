# Crawler Mind Helm Charts

Kubernetes에서 Crawler Mind 시스템을 배포하기 위한 Helm 차트들입니다.

## 요구사항

- Docker & Kind
- Helm 3.x
- kubectl
- Tailscale (선택사항, PostgreSQL 외부 접근)
- Cloudflare Tunnel (선택사항, 도메인 접근)

## 빠른 시작

### 1. Kind 클러스터 생성 (모든 포트 포함)

```bash
# 기존 클러스터 삭제 (있다면)
kind delete cluster --name kind

# PostgreSQL 포트를 포함한 새 클러스터 생성
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  # Nginx Ingress Controller HTTP
  - containerPort: 30760
    hostPort: 30760
    protocol: TCP
  # Nginx Ingress Controller HTTPS  
  - containerPort: 31784
    hostPort: 31784
    protocol: TCP
  # PostgreSQL
  - containerPort: 30542
    hostPort: 30542
    protocol: TCP
EOF
```

### 2. Nginx Ingress Controller 설치

```bash
# nginx ingress controller 설치
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=NodePort \
  --set controller.service.nodePorts.http=30760 \
  --set controller.service.nodePorts.https=31784
```

### 3. 민감 정보 설정

각 차트 디렉토리에서 `values-secrets.yaml` 파일을 생성하고 실제 값을 입력하세요:

**mcp-client-chart/values-secrets.yaml:**
```yaml
env:
  OPENAI_API_KEY: "your-actual-openai-api-key"
  DATABASE_URL: "postgresql+asyncpg://admin:your-password@postgres:5432/crawler_mind"
```

**postgres-chart/values-secrets.yaml:**
```yaml
postgres:
  password: "your-postgres-password"
```

### 4. 네임스페이스 생성
```bash
kubectl create namespace crawler-mind
```

### 5. 서비스 배포 (순서대로)

```bash
# 1. PostgreSQL
helm install postgres ./postgres-chart -f ./postgres-chart/values-secrets.yaml -n crawler-mind
echo "PostgreSQL 배포 완료, 30초 대기..."
sleep 30

# 2. Qdrant (Vector DB)  
helm install qdrant ./qdrant-chart -n crawler-mind

# 3. OpenSearch
helm install opensearch ./opensearch-chart -n crawler-mind

# 4. MCP Server
helm install mcp-server ./mcp-server-chart -n crawler-mind

# 5. MCP Client (API) - PostgreSQL 준비 후 배포
helm install mcp-client ./mcp-client-chart -f ./mcp-client-chart/values-secrets.yaml -n crawler-mind

# 6. Frontend
helm install frontend ./frontend-chart -n crawler-mind

echo "모든 서비스 배포 완료. 2-3분 후 접속 가능합니다."
```

### 6. Cloudflare Tunnel 설정

```yaml
# /etc/cloudflared/config.yml
tunnel: your-tunnel-id
credentials-file: /home/username/.cloudflared/your-tunnel-id.json
ingress:
  - hostname: crawler.yourdomain.com
    service: http://localhost:30760  # nginx ingress controller
  - hostname: api.yourdomain.com
    service: http://localhost:30760  # nginx ingress controller
  - hostname: qdrant.yourdomain.com
    service: http://localhost:30760  # nginx ingress controller
  - hostname: opensearch.yourdomain.com
    service: http://localhost:30760  # nginx ingress controller
  - service: http_status:404
```

### 7. Tailscale 외부 접근 설정 (선택사항)

```bash
# Tailscale 설정 (PostgreSQL 외부 접근)
sudo tailscale serve --bg --tcp=5432 localhost:30542

# 상태 확인
tailscale status
tailscale serve status

# 외부에서 접근
psql -h {tailscale-hostname} -p 5432 -U postgres
```

## 서비스 구성

### 내부 서비스 (ClusterIP)
| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 3000 | Next.js 웹 인터페이스 |
| MCP-Client | 8000 | FastAPI 백엔드 |
| MCP-Server | 4200 | FastMCP 서버 |
| PostgreSQL | 5432 | 메인 데이터베이스 |
| OpenSearch | 9200 | 검색 엔진 |
| Qdrant | 6333 | 벡터 데이터베이스 |

### 외부 접근
| 서비스 | 접근 방법 | 주소 | 설명 |
|--------|-----------|------|------|
| 웹 서비스 | Cloudflare Tunnel | https://yourdomain.com | Ingress를 통한 모든 웹 서비스 |
| PostgreSQL | Tailscale | {tailscale-hostname}:5432 | 데이터베이스 직접 연결 |
| 로컬 개발 | 직접 접근 | localhost:30760 (웹), localhost:30542 (DB) | Kind 클러스터 직접 접근 |

### 도메인 기반 라우팅 (Ingress)
| 도메인 | 서비스 | 설명 |
|--------|--------|------|
| crawler.yourdomain.com | Frontend | 웹 인터페이스 |
| api.yourdomain.com | MCP-Client | API 서버 |
| qdrant.yourdomain.com | Qdrant | 벡터 DB API |
| opensearch.yourdomain.com | OpenSearch | 검색 엔진 API |

## 개발 환경 설정

### 환경변수 템플릿

**필수 환경변수:**
- `OPENAI_API_KEY`: OpenAI API 키
- `DATABASE_URL`: PostgreSQL 연결 문자열  
- `POSTGRES_PASSWORD`: PostgreSQL 비밀번호

### Cloudflare Tunnel 연동

외부 도메인 접근을 위한 설정:
```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: your-domain.com
    service: http://localhost:3001  # Frontend
  - hostname: api.your-domain.com
    service: http://localhost:8001  # API
  - service: http_status:404
```

## 트러블슈팅

### 공통 문제들

1. **PostgreSQL 데이터 손실 방지**
   - Helm uninstall/install 시 데이터가 사라지는 문제 해결됨
   - PVC에 `helm.sh/resource-policy: keep` 어노테이션 적용
   - 기존 PVC 사용: `values.yaml`에서 `persistence.existingClaim` 설정

2. **PostgreSQL 연결 실패**
   - initContainer가 DB 준비를 기다립니다
   - `kubectl logs -n crawler-mind deployment/mcp-client` 확인

3. **이미지 Pull 실패**
   - 이미지 태그 확인: `seohuipark/crawler-mind-*:dev`
   - Docker Hub에서 이미지 존재 여부 확인

4. **Ingress 충돌**
   - 동일한 hostname 사용 시 발생
   - `kubectl get ingress -n crawler-mind` 확인

5. **503 에러 (서비스 배포 직후)**
   - 새 서비스 배포 후 2-3분 정도 기다려야 함
   - Readiness Probe와 Ingress Controller 동기화 시간 필요
   - `kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx` 확인

6. **Tailscale 연결 문제**
   - WSL에서 라우팅 테이블 확인: `ip route | grep tailscale`
   - 필요시 라우트 추가: `sudo ip route add 100.64.0.0/10 dev tailscale0`
   - Tailscale 재시작: `sudo tailscale down && sudo tailscale up --accept-routes`

### 데이터 영구 보존 (PostgreSQL, Qdrant, OpenSearch)

**방법 1: 자동 PVC 보존 (현재 적용됨)**
```bash
# 모든 데이터베이스 서비스 - 데이터 보존됨
helm uninstall postgres -n crawler-mind
helm uninstall qdrant -n crawler-mind
helm uninstall opensearch -n crawler-mind

helm install postgres ./postgres-chart -f ./postgres-chart/values-secrets.yaml -n crawler-mind
helm install qdrant ./qdrant-chart -n crawler-mind
helm install opensearch ./opensearch-chart -n crawler-mind
```

**방법 2: 기존 PVC 재사용**
```bash
# 1. 기존 PVC 이름 확인
kubectl get pvc -n crawler-mind

# 2. values.yaml 수정 (각 서비스별)
# PostgreSQL
persistence:
  existingClaim: "postgres-pvc"

# Qdrant  
persistence:
  existingClaim: "qdrant-qdrant-pvc"

# OpenSearch
persistence:
  existingClaim: "opensearch-pvc"

# 3. 재배포
helm upgrade postgres ./postgres-chart -f ./postgres-chart/values-secrets.yaml -n crawler-mind
helm upgrade qdrant ./qdrant-chart -n crawler-mind
helm upgrade opensearch ./opensearch-chart -n crawler-mind
```

**데이터 손실 위험 없는 서비스:**
- ✅ PostgreSQL (메타데이터) - 보존됨
- ✅ Qdrant (벡터 데이터) - 보존됨  
- ✅ OpenSearch (인덱스 데이터) - 보존됨
- ⚠️ MCP-Client/Server (Stateless) - 데이터 없음
- ⚠️ Frontend (Stateless) - 데이터 없음

### 로그 확인

```bash
# 전체 파드 상태
kubectl get pods -n crawler-mind

# 특정 서비스 로그
kubectl logs -n crawler-mind deployment/mcp-client
kubectl logs -n crawler-mind deployment/frontend
```

## 아키텍처

### 전체 아키텍처
```
Internet → Cloudflare Tunnel → WSL2 Host → Kind Cluster
├─ Nginx Ingress Controller (30760/31784)
│  ├─ Frontend (Next.js) → MCP-Client (FastAPI)
│  ├─ Qdrant API (벡터 DB)
│  └─ OpenSearch API (검색 엔진)
├─ PostgreSQL (30542) - 직접 접근
└─ MCP-Client → MCP-Server → External APIs
```

### Ingress 기반 라우팅
```
Browser → Cloudflare Tunnel → localhost:30760
├─ crawler.yourdomain.com → Frontend Service
├─ api.yourdomain.com → MCP-Client Service  
├─ qdrant.yourdomain.com → Qdrant Service
└─ opensearch.yourdomain.com → OpenSearch Service
```

### 데이터 흐름
```
Frontend → MCP-Client → MCP-Server → External APIs
    ↓
PostgreSQL (메타데이터)
    ↓
Qdrant (벡터 검색) + OpenSearch (텍스트 검색)
```
