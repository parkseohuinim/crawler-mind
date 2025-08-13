# 크롤링 AI 어시스턴트 - 프론트엔드

웹사이트 크롤링 및 분석을 위한 Next.js 기반 채팅 인터페이스입니다.

## 주요 기능

- 🤖 **AI 자동 분석**: LLM이 적절한 크롤링 도구를 자동으로 선택
- 🔧 **기본 크롤링**: 단순 크롤링 및 데이터 추출
- 📡 **실시간 업데이트**: SSE를 통한 진행상황 실시간 표시
- 💬 **채팅 인터페이스**: 직관적인 대화형 UI

## 기술 스택

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Pure CSS (Tailwind CSS 미사용)
- **Real-time**: Server-Sent Events (SSE)

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
MCP_CLIENT_URL=http://localhost:8000
```

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
URL 처리 작업을 시작합니다.

**Request Body:**
```json
{
  "url": "https://example.com",
  "mode": "auto" | "basic"
}
```

**Response:**
```json
{
  "taskId": "task_123"
}
```

### GET /api/stream/[taskId]
작업 진행상황을 SSE로 스트리밍합니다.

**SSE Events:**
- `status`: 진행 상태 업데이트
- `tool_call`: 도구 호출 알림
- `partial`: 부분 결과
- `final`: 최종 결과
- `error`: 오류 발생

### GET /api/result/[taskId]
작업 완료 후 최종 결과를 조회합니다.

**Response:**
```json
{
  "title": "페이지 제목",
  "textLength": 1234,
  "linkCount": 25,
  "links": ["https://...", "..."],
  "summary": "페이지 요약",
  "screenshot": "base64_image"
}
```

## 사용 방법

1. 웹사이트에서 URL 입력 필드에 분석할 웹사이트 주소 입력
2. 분석 모드 선택:
   - **AI 자동 분석**: LLM이 상황에 맞는 도구들을 자동으로 선택
   - **기본 크롤링**: 단순 크롤링 및 데이터 추출만 수행
3. "분석 시작" 버튼 클릭
4. 실시간으로 진행상황 확인
5. 완료 후 크롤링 결과 확인

## 개발 참고사항

- **상태 관리**: React hooks 기반의 로컬 상태 관리
- **스타일링**: CSS 모듈이나 styled-components 대신 순수 CSS 사용
- **타입 안정성**: TypeScript로 모든 컴포넌트와 훅 타입 정의
- **실시간 통신**: WebSocket 대신 SSE 사용으로 단순화
- **에러 처리**: 네트워크 오류, 타임아웃 등 다양한 에러 상황 처리
