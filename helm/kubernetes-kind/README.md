# Crawler Mind Helm Charts

Kubernetes에서 Crawler Mind 시스템을 배포하기 위한 Helm 차트들입니다.

## 빠른 시작

### 1. 민감 정보 설정

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

### 2. 네임스페이스 생성
```bash
kubectl create namespace crawler-mind
```

### 3. 서비스 배포 (순서대로)

```bash
# 1. PostgreSQL
helm install postgres ./postgres-chart -f ./postgres-chart/values-secrets.yaml -n crawler-mind

# 2. Qdrant (Vector DB)  
helm install qdrant ./qdrant-chart -n crawler-mind

# 3. OpenSearch
helm install opensearch ./opensearch-chart -n crawler-mind

# 4. MCP Server
helm install mcp-server ./mcp-server-chart -n crawler-mind

# 5. MCP Client (API)
helm install mcp-client ./mcp-client-chart -f ./mcp-client-chart/values-secrets.yaml -n crawler-mind

# 6. Frontend
helm install frontend ./frontend-chart -n crawler-mind
```

### 4. 포트포워딩 (외부 접근용)

```bash
# Frontend
kubectl port-forward --address 0.0.0.0 -n crawler-mind svc/frontend 3001:3000 &

# API
kubectl port-forward --address 0.0.0.0 -n crawler-mind svc/mcp-client 8001:8000 &
```

## 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend | 3000 | Next.js 웹 인터페이스 |
| MCP-Client | 8000 | FastAPI 백엔드 |
| MCP-Server | 4200 | FastMCP 서버 |
| PostgreSQL | 5432 | 메인 데이터베이스 |
| OpenSearch | 9200 | 검색 엔진 |
| Qdrant | 6333 | 벡터 데이터베이스 |

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

```
Browser → Cloudflare Tunnel → Kubernetes Cluster
├─ Frontend (Next.js) → MCP-Client (FastAPI)
└─ MCP-Client → MCP-Server → External APIs
    ├─ PostgreSQL (메타데이터)
    ├─ OpenSearch (검색)
    └─ Qdrant (벡터 DB)
```
