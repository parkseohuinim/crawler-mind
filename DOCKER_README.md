# 단일 배포 가이드 (Mac → WSL)

## 0. 준비
- Docker Desktop (Mac), Docker & Docker Compose (WSL)
- Docker Hub 계정 로그인 가능
- .env 파일(선택): 외부 DB/키 등 필요 시 프로젝트 루트에 배치
- .gitignore에 민감정보(.env), build-output/, *.tar 포함

## 1) Mac에서 빌드 및 푸시
```bash
# Docker Hub 로그인 (최초 1회)
docker login -u <DOCKER_HUB_USERNAME>

# 프런트 브라우저용 API 경로(Cloudflare) 포함 빌드/푸시
./scripts/build-mac.sh <DOCKER_HUB_USERNAME> https://crawler.alvinpark.xyz/api
```
- NEXT_PUBLIC_API_BASE_URL: 브라우저가 호출할 외부 경로
- 내부 호출은 서버에서 API_BASE_URL(env 또는 docker-compose)로 자동 처리

## 2) WSL(개발 서버)에서 배포
```bash
# Docker Hub 로그인
docker login -u <DOCKER_HUB_USERNAME>

# (선택) 환경 변수 설정
cp env.example .env   # 필요시 편집

# 배포 (이미지 pull + compose up)
./scripts/deploy-wsl.sh <DOCKER_HUB_USERNAME>
```

## 3) 구성 요약
- docker-compose.yml
  - frontend: 
    - NEXT_PUBLIC_API_BASE_URL=https://crawler.alvinpark.xyz/api
    - API_BASE_URL=http://mcp-client:8000 (SSR 내부 호출)
  - mcp-client: CORS_ORIGINS에 프런트 도메인 지정
- env.example: 외부 DB/키 필요 시 사용

## 4) 확인
- Frontend: http://localhost:3000
- MCP Client API(swagger): http://localhost:8000/docs (로컬 개발 시)

## 5) 유틸 명령어
```bash
# 상태
docker-compose ps
# 로그
docker-compose logs -f frontend
# 중지
docker-compose down
```

완료. 위 2단계(빌드/배포)만 반복하면 최신 버전이 반영됩니다.
