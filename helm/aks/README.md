# Crawler Mind - AKS 배포 가이드

AI 기반 웹 크롤링 시스템을 Azure Kubernetes Service (AKS)에 배포하는 Helm Chart입니다.

Docker Hub에서 미리 빌드된 이미지를 자동으로 받아와서 AKS 클러스터에 배포합니다.

## 빠른 시작

### 사전 요구사항
- **AKS 클러스터** 준비 완료
- **kubectl** 명령어로 AKS 연결 확인
- **Helm 3.x** 설치 완료
- **OpenAI API 키** 준비

### 1. 민감 정보 설정
먼저 `values-secrets.yaml` 파일을 생성하고 실제 값을 입력하세요:

```bash
# values-secrets.yaml 파일 생성
cp values-secrets.yaml values-secrets.yaml.local
```

`values-secrets.yaml.local` 파일을 편집:
```yaml
mcpClient:
  envSecret:
    OPENAI_API_KEY: "sk-proj-your-actual-openai-api-key"
    DATABASE_URL: "postgresql+asyncpg://admin:your-password@postgres:5432/crawler-mind"

postgresql:
  auth:
    password: "your-password"
```

### 2. 기본 배포
```bash
helm install crawler-mind . \
    --namespace crawler-mind \
    --create-namespace \
    -f values-secrets.yaml.local
```

완료! 시스템이 자동으로:
- Docker Hub에서 이미지 다운로드
- 모든 서비스 배포 (Frontend, MCP Client/Server, PostgreSQL, Qdrant, OpenSearch)
- NGINX Ingress Controller 설정
- LoadBalancer IP 할당

## 접속 방법

### 외부 IP 확인
```bash
kubectl get service -n ingress-nginx ingress-nginx-controller
```

### 접속 주소
- **웹 인터페이스**: `http://[외부IP주소]`
- **API 문서**: `http://[외부IP주소]/api/docs`

## 배포 시나리오

### 1. IP로 바로 접속 (개발용)
```bash
helm install crawler-mind . \
    --namespace crawler-mind \
    --create-namespace \
    --set mcpClient.envSecret.OPENAI_API_KEY="sk-proj-abc123..."
```
접속: `http://[LoadBalancer-IP]`

### 2. 도메인 + SSL 인증서 (운영용)
```bash
helm install crawler-mind . \
    --namespace crawler-mind \
    --create-namespace \
    --set ingress.domain="crawler.mycompany.com" \
    --set ingress.tls.enabled=true \
    --set mcpClient.envSecret.OPENAI_API_KEY="sk-proj-abc123..."
```
접속: `https://crawler.mycompany.com`

### 3. 리소스 최적화 (작은 클러스터)
```bash
helm install crawler-mind . \
    --namespace crawler-mind \
    --create-namespace \
    --set frontend.replicaCount=1 \
    --set mcpClient.replicaCount=1 \
    --set mcpServer.replicaCount=1 \
    --set mcpClient.envSecret.OPENAI_API_KEY="sk-proj-abc123..."
```

## 주요 설정

### 필수 설정
```yaml
mcpClient:
  envSecret:
    OPENAI_API_KEY: "sk-your-openai-api-key"  # 필수!
```

### 자주 사용하는 설정
```yaml
# Docker Hub 계정 변경 (필요시)
image:
  repository: "your-dockerhub-username"  # 기본값: seohuipark

# 도메인 설정
ingress:
  domain: "crawler.mycompany.com"
  tls:
    enabled: true  # HTTPS 사용

# 보안 설정
postgresql:
  auth:
    postgresPassword: "안전한비밀번호123!"

# 서버 개수
frontend:
  replicaCount: 3
mcpClient:
  replicaCount: 3
```

## 리소스 요구사항

### 최소 요구사항
- **노드**: 2개 x Standard_D2s_v3 (2 CPU, 8GB RAM)
- **스토리지**: 40GB Premium SSD

### 권장 사양 (실서비스)
- **노드**: 3개 x Standard_D4s_v3 (4 CPU, 16GB RAM)
- **스토리지**: 100GB Premium SSD

### 배포되는 서비스들
- **프론트엔드**: 2개 Pod (이미지: `seohuipark/crawler-mind-frontend:dev`)
- **API 서버**: 2개 Pod (이미지: `seohuipark/crawler-mind-mcp-client:dev`)
- **MCP 서버**: 2개 Pod (이미지: `seohuipark/crawler-mind-mcp-server:dev`)
- **PostgreSQL**: 1개 Pod + 20GB 저장소 (공식 `postgres:15` 이미지)
- **Qdrant**: 1개 Pod + 20GB 저장소 (공식 `qdrant/qdrant:latest` 이미지)
- **OpenSearch Dashboards**: 1개 Pod (공식 이미지)
- **NGINX Ingress**: 자동 설치 + 외부 IP

## 상태 확인

### 배포 상태 확인
```bash
kubectl get pods -n crawler-mind

# 예상 결과:
# NAME                                    READY   STATUS
# crawler-mind-frontend-xxx               1/1     Running
# crawler-mind-mcp-client-xxx             1/1     Running
# crawler-mind-mcp-server-xxx             1/1     Running
# crawler-mind-postgresql-0               1/1     Running
# crawler-mind-qdrant-0                   1/1     Running
```

### 로그 확인
```bash
# 프론트엔드 로그
kubectl logs -f deployment/crawler-mind-frontend -n crawler-mind

# API 로그
kubectl logs -f deployment/crawler-mind-mcp-client -n crawler-mind
```

### 리소스 사용량
```bash
# Pod별 CPU/메모리 사용량
kubectl top pods -n crawler-mind

# 자동 확장 상태
kubectl get hpa -n crawler-mind
```

## 업데이트

### 새 버전 업데이트
```bash
helm upgrade crawler-mind . \
    --namespace crawler-mind \
    --set image.tag="v1.1.0"
```

### 설정 변경
```bash
# SSL 활성화
helm upgrade crawler-mind . \
    --namespace crawler-mind \
    --set ingress.tls.enabled=true \
    --set ingress.domain="crawler.mycompany.com"
```

## 문제 해결

### 자주 발생하는 문제들

#### 1. Pod가 시작되지 않음
```bash
kubectl describe pod <pod이름> -n crawler-mind

# 주요 원인:
# - 노드 리소스 부족
# - 잘못된 OpenAI API 키
# - Docker Hub 이미지 다운로드 실패 (인터넷 연결 확인)
# - ImagePullBackOff: Docker Hub 접근 제한 (잠시 후 재시도)
```

#### 2. 접속이 안됨
```bash
kubectl get service -n ingress-nginx ingress-nginx-controller

# EXTERNAL-IP가 <pending>이면:
# - 5-10분 더 기다리기
# - AKS LoadBalancer 기능 확인
```

#### 3. SSL 인증서 문제
```bash
# 인증서 상태 확인
kubectl get certificate -n crawler-mind

# cert-manager 로그 확인
kubectl logs -f deployment/cert-manager -n cert-manager
```

## 삭제

### 애플리케이션 삭제
```bash
helm uninstall crawler-mind -n crawler-mind
kubectl delete namespace crawler-mind
```

### 전체 삭제 (Ingress 포함)
```bash
helm uninstall crawler-mind -n crawler-mind
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace crawler-mind
kubectl delete namespace ingress-nginx
```

## 예상 비용 (한국 중부 기준)

### 일반적인 월 비용
- **2x Standard_D4s_v3 노드**: 약 28만원/월
- **Premium SSD 100GB**: 약 2만원/월
- **Standard Load Balancer**: 약 2.5만원/월
- **총합**: 약 32.5만원/월

### 비용 절약 팁
- **Standard_D2s_v3** 노드 사용: 약 14만원/월
- **Standard SSD** 사용: 약 8천원/월
- 사용하지 않을 때 replica 줄이기

---