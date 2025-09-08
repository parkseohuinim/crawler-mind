# 한글 폰트 폴더

이 폴더는 JSON 비교 도구에서 한글이 포함된 PDF 리포트를 생성할 때 사용하는 폰트들을 저장합니다.

## 자동 폰트 다운로드

프로그램을 실행하면 다음 순서로 한글 폰트를 찾고 설정합니다:

1. **로컬 폰트 확인**: 이 폴더에 저장된 폰트 파일들을 먼저 확인
2. **시스템 폰트 확인**: 운영체제별 시스템 폰트 확인
3. **자동 다운로드**: 위 단계에서 폰트를 찾지 못한 경우 Noto Sans CJK 폰트를 자동 다운로드

## 지원되는 폰트 파일

- `NotoSansCJK-Regular.ttc` - Google Noto Sans CJK (자동 다운로드)
- `malgun.ttf` - 맑은 고딕 (Windows에서 복사 가능)

## 수동 폰트 추가 방법

더 나은 한글 표시를 위해 수동으로 폰트를 추가할 수 있습니다:

### Windows 사용자
```bash
# 맑은 고딕 폰트 복사 (관리자 권한 필요)
copy "C:\Windows\Fonts\malgun.ttf" fonts/
```

### macOS 사용자
```bash
# 시스템에서 한글 폰트 복사
cp "/System/Library/Fonts/AppleGothic.ttf" fonts/ 2>/dev/null || echo "폰트 파일을 찾을 수 없습니다"
```

## 문제 해결

### 한글이 깨져서 나오는 경우
1. 인터넷 연결을 확인하고 프로그램을 다시 실행하세요 (자동 다운로드)
2. 수동으로 한글 폰트를 이 폴더에 복사하세요
3. 폰트 파일명이 정확한지 확인하세요

### 지원되는 폰트 형식
- `.ttf` (TrueType Font)
- `.ttc` (TrueType Collection)
- `.otf` (OpenType Font)

## 라이선스 정보

- **Noto Sans CJK**: SIL Open Font License 1.1
- **맑은 고딕**: Microsoft 폰트 (Windows 시스템에서만 사용 가능)
- **AppleGothic**: Apple 폰트 (macOS 시스템에서만 사용 가능)

## 폰트 크기 정보

- Noto Sans CJK: 약 17MB (한중일 모든 문자 포함)
- 맑은 고딕: 약 9MB (한글 + 영문)
- AppleGothic: 약 3MB (한글 + 영문)