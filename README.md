# Crawler Mind

AI 기반 웹 크롤링 시스템과 메뉴 링크 관리 시스템입니다. MCP(Model Context Protocol) 서버와 FastAPI 백엔드, Next.js 프론트엔드로 구성되어 있습니다.

## 빠른 시작

### 1. 저장소 클론
```bash
git clone <repository-url>
cd crawler-mind
```

### 2. 환경 설정

#### 환경변수 파일 생성
```bash
# mcp-client 디렉토리에 .env 파일 생성
cd mcp-client
touch .env
```

#### .env 파일에 필수 설정 추가
```env
# OpenAI API 키 (필수)
OPENAI_API_KEY=your_openai_api_key_here

# 데이터베이스 설정 (메뉴 링크 관리용)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/crawler_mind

# 선택적 설정
OPENAI_MODEL=gpt-4o
LOG_LEVEL=warning
DEBUG=false
```

### 3. 데이터베이스 설정 (메뉴 링크 관리용)

PostgreSQL을 설치하고 데이터베이스를 생성합니다:

```bash
# PostgreSQL 설치 (macOS)
brew install postgresql
brew services start postgresql

# 데이터베이스 생성
createdb crawler_mind

# 또는 psql로 생성
psql -U postgres
CREATE DATABASE crawler_mind;
\q
```

테이블은 애플리케이션 시작 시 자동으로 생성됩니다.

### 4. 백엔드 실행

#### Python 의존성 설치 (uv 사용)
```bash
# uv로 가상환경 생성 및 의존성 설치
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

#### Playwright 브라우저 설치
```bash
playwright install chromium
```

#### MCP 서버 실행 (터미널 1)
```bash
cd mcp-server
uv run python server.py
```

#### FastAPI 서버 실행 (터미널 2)
```bash
cd mcp-client
# 가상환경이 활성화되어 있는지 확인
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv run python main.py
```

### 5. 프론트엔드 실행 (터미널 3)

```bash
cd frontend
npm install
# 환경변수 설정 (선택사항)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## 접속

- **프론트엔드**: http://localhost:3000
- **FastAPI 백엔드**: http://localhost:8000
- **MCP 서버**: http://127.0.0.1:4200/my-custom-path

## 주요 기능

### 웹 크롤링 기능
- 웹페이지 크롤링 및 데이터 추출
- AI 기반 콘텐츠 분석
- 실시간 스트리밍 결과
- 스크린샷 촬영
- 링크 추출 및 분석

### 메뉴 링크 관리 기능
- 메뉴 경로별 PC/모바일 URL 관리
- CRUD 작업 (생성, 읽기, 수정, 삭제)
- 검색 및 페이지네이션
- 모던한 웹 인터페이스
- 반응형 디자인

## 요구사항

- **Python**: 3.8+
- **uv**: Python 패키지 매니저 ([설치 가이드](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js**: 16+
- **PostgreSQL**: 12+ (메뉴 링크 관리용)
- **OpenAI API 키**: 필수

## 문제 해결

### Playwright 설치 오류
```bash
# uv 환경에서 Playwright 설치
uv run playwright install chromium

# 권한 문제 시
sudo uv run playwright install chromium

# 또는 환경변수 설정
export PLAYWRIGHT_BROWSERS_PATH=~/.cache/ms-playwright
```

### 포트 충돌
각 서비스의 포트를 변경하려면:
- MCP 서버: `mcp-server/server.py` 파일의 `port=4200` 수정
- FastAPI: `mcp-client/app/config.py` 파일의 `port: int = 8000` 수정
- Next.js: `npm run dev -- -p 3001`

### 데이터베이스 연결 오류
```bash
# PostgreSQL 서비스 상태 확인
brew services list | grep postgresql

# PostgreSQL 시작
brew services start postgresql

# 연결 테스트
psql -U postgres -d crawler_mind -c "SELECT 1;"
```

### API 연결 오류
프론트엔드에서 API 호출 오류 시:
1. FastAPI 서버가 실행 중인지 확인 (http://localhost:8000)
2. CORS 설정 확인
3. 브라우저 개발자 도구에서 네트워크 탭 확인

## 프로젝트 구조

```
crawler-mind/
├── frontend/                    # Next.js 프론트엔드
│   ├── app/
│   │   ├── components/         # React 컴포넌트
│   │   ├── hooks/             # 커스텀 훅
│   │   ├── api/               # API 함수들
│   │   ├── types/             # TypeScript 타입 정의
│   │   ├── menu-links/        # 메뉴 링크 관리 페이지
│   │   └── globals.css        # 전역 스타일
│   └── .env.local             # 프론트엔드 환경변수 (생성 필요)
├── mcp-client/                 # FastAPI 백엔드
│   ├── app/
│   │   ├── routers/           # API 라우터
│   │   ├── services/          # 비즈니스 로직
│   │   ├── models.py          # Pydantic 모델
│   │   ├── database.py        # 데이터베이스 설정
│   │   └── config.py          # 설정 관리
│   ├── main.py                # FastAPI 애플리케이션
│   └── .env                   # 백엔드 환경변수 (생성 필요)
├── mcp-server/                 # MCP 크롤링 서버
│   └── server.py              # MCP 서버
└── requirements.txt            # Python 의존성
```

## API 엔드포인트

### 메뉴 링크 관리 API
- `GET /api/menu-links` - 메뉴 링크 목록 조회 (페이지네이션, 검색 지원)
- `GET /api/menu-links/{id}` - 특정 메뉴 링크 조회
- `POST /api/menu-links` - 새 메뉴 링크 생성
- `PUT /api/menu-links/{id}` - 메뉴 링크 수정
- `DELETE /api/menu-links/{id}` - 메뉴 링크 삭제

### 크롤링 API
- `POST /api/process-url` - URL 크롤링 작업 시작
- `GET /api/stream/{taskId}` - 크롤링 진행 상황 스트리밍
- `GET /api/result/{taskId}` - 크롤링 결과 조회

## 데이터베이스 스키마

### menu_links 테이블
```sql
CREATE TABLE crawler_mind.menu_links (
    id bigserial NOT NULL,
    menu_path text NOT NULL,           -- 메뉴 경로 (예: "고객지원^공지이용안내^서비스안내")
    pc_url text NULL,                  -- PC URL
    mobile_url text NULL,              -- 모바일 URL
    created_by varchar(100) NULL,      -- 생성자
    created_at timestamp DEFAULT now() NULL,
    updated_by varchar(100) NULL,      -- 수정자
    updated_at timestamp DEFAULT now() NULL,
    CONSTRAINT menu_links_pkey PRIMARY KEY (id)
);
```
