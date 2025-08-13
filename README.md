# Crawler Mind

AI 기반 웹 크롤링 시스템입니다. MCP(Model Context Protocol) 서버와 FastAPI 백엔드, Next.js 프론트엔드로 구성되어 있습니다.

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

# 선택적 설정
OPENAI_MODEL=gpt-4o
LOG_LEVEL=warning
DEBUG=false
```

### 3. 백엔드 실행

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

### 4. 프론트엔드 실행 (터미널 3)

```bash
cd frontend
npm install
npm run dev
```

## 접속

- **프론트엔드**: http://localhost:3000
- **FastAPI 백엔드**: http://localhost:8000
- **MCP 서버**: http://127.0.0.1:4200/my-custom-path

## 주요 기능

- 웹페이지 크롤링 및 데이터 추출
- AI 기반 콘텐츠 분석
- 실시간 스트리밍 결과
- 스크린샷 촬영
- 링크 추출 및 분석

## 요구사항

- **Python**: 3.8+
- **uv**: Python 패키지 매니저 ([설치 가이드](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js**: 16+
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

## 프로젝트 구조

```
crawler-mind/
├── frontend/          # Next.js 프론트엔드
├── mcp-client/        # FastAPI 백엔드
│   └── .env          # 환경변수 (생성 필요)
├── mcp-server/        # MCP 크롤링 서버
└── requirements.txt   # Python 의존성
```
