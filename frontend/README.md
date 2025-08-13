# Crawler Mind - Frontend

AI 기반 웹 크롤링 시스템의 Next.js 프론트엔드입니다. MCP(Model Context Protocol) 서버와 FastAPI 백엔드와 연동하여 웹사이트 분석 및 크롤링 기능을 제공합니다.

## 주요 기능

- **AI 기반 웹 분석**: OpenAI GPT 모델을 활용한 지능형 웹 콘텐츠 분석
- **웹페이지 크롤링**: Playwright를 이용한 동적 웹페이지 크롤링
- **실시간 스트리밍**: SSE를 통한 크롤링 진행상황 실시간 업데이트
- **스크린샷 촬영**: 웹페이지 전체 화면 캡처
- **링크 추출**: 페이지 내 모든 링크 분석 및 분류
- **텍스트 요약**: AI 기반 콘텐츠 요약

## 기술 스택

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: CSS Modules
- **Real-time**: Server-Sent Events (SSE)
- **Backend**: FastAPI + MCP Server

## 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev

# 프로덕션 빌드
npm run build
npm start
```

## 환경 설정

`.env.local` 파일을 생성하고 다음 환경변수를 설정하세요:

```env
# FastAPI 백엔드 서버 URL
MCP_CLIENT_URL=http://localhost:8000
```

## 전체 시스템 실행 순서

프론트엔드만 실행하기 전에 백엔드 서비스들이 먼저 실행되어야 합니다:

1. **MCP 서버 실행** (포트 4200)
2. **FastAPI 서버 실행** (포트 8000) 
3. **Frontend 서버 실행** (포트 3000)

자세한 실행 방법은 프로젝트 루트의 README.md를 참고하세요.

## 프로젝트 구조

```
frontend/
├── app/
│   ├── api/                 # Next.js API 라우트
│   │   ├── process-url/     # URL 처리 시작
│   │   ├── stream/[taskId]/ # SSE 스트림
│   │   └── result/[taskId]/ # 결과 조회
│   ├── components/          # React 컴포넌트
│   │   ├── ChatMessage.tsx  # 채팅 메시지
│   │   ├── ChatInput.tsx    # URL 입력 폼
│   │   ├── ProgressDisplay.tsx # 진행상황 표시
│   │   └── ResultDisplay.tsx   # 결과 표시
│   ├── hooks/               # Custom Hooks
│   │   ├── useSSE.ts        # SSE 연결 관리
│   │   └── useCrawler.ts    # 크롤링 상태 관리
│   ├── types/               # TypeScript 타입 정의
│   ├── globals.css          # 글로벌 스타일
│   ├── layout.tsx           # 루트 레이아웃
│   └── page.tsx             # 메인 페이지
├── package.json
├── tsconfig.json
└── next.config.js
```

## API 엔드포인트

### POST /api/process-url
웹페이지 크롤링 작업을 시작합니다.

**Request Body:**
```json
{
  "url": "https://example.com",
  "prompt": "이 웹페이지를 분석해주세요"
}
```

**Response:**
```json
{
  "taskId": "task_123"
}
```

### GET /api/stream/[taskId]
크롤링 작업 진행상황을 SSE로 실시간 스트리밍합니다.

**SSE Events:**
- `progress`: 진행 상태 업데이트
- `tool_call`: MCP 도구 호출 알림
- `result`: 부분 결과 데이터
- `complete`: 작업 완료
- `error`: 오류 발생

### GET /api/result/[taskId]
작업 완료 후 최종 크롤링 결과를 조회합니다.

**Response:**
```json
{
  "status": "completed",
  "result": {
    "url": "https://example.com",
    "title": "페이지 제목",
    "content": "추출된 텍스트 내용",
    "links": ["https://...", "..."],
    "summary": "AI 생성 요약",
    "screenshot": "base64_encoded_image",
    "metadata": {
      "contentLength": 1234,
      "linkCount": 25,
      "processingTime": "2.5s"
    }
  }
}
```

## 사용 방법

1. 백엔드 서비스들이 실행되고 있는지 확인 (MCP 서버, FastAPI 서버)
2. 웹사이트에서 URL 입력 필드에 분석할 웹사이트 주소 입력
3. 분석 요청 메시지 입력 (예: "이 웹페이지를 분석해주세요")
4. "전송" 버튼 클릭
5. 실시간으로 크롤링 진행상황 확인
6. 완료 후 다음 결과 확인:
   - 페이지 제목 및 메타 정보
   - 추출된 텍스트 내용
   - 발견된 링크 목록
   - AI 생성 요약
   - 페이지 스크린샷

## 개발 참고사항

- **상태 관리**: React hooks 기반의 로컬 상태 관리
- **스타일링**: CSS Modules 사용
- **타입 안정성**: TypeScript로 모든 컴포넌트와 훅 타입 정의
- **실시간 통신**: Server-Sent Events (SSE) 사용
- **에러 처리**: 네트워크 오류, 타임아웃, 백엔드 연결 실패 등 처리
- **MCP 통신**: FastAPI를 통해 MCP 서버와 통신
- **AI 통합**: OpenAI GPT 모델을 활용한 콘텐츠 분석

## 요구사항

- Node.js 16+
- 실행 중인 FastAPI 백엔드 (포트 8000)
- 실행 중인 MCP 서버 (포트 4200)
