"""
Preprocessor - 마크다운 전처리 통합 모듈

preprocess_info.py와 preprocess_notice.py의 핵심 로직을 통합하여
크롤링된 마크다운 콘텐츠를 정제합니다.
"""
import logging
import re
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# 공지사항 판별 함수
# =============================================================================

def is_notice_content(text: str) -> bool:
    """
    텍스트 내용이 공지사항인지 판별
    
    Args:
        text: 마크다운 텍스트
        
    Returns:
        공지사항 여부
    """
    notice_patterns = [
        r'# 통신사기주의보',
        r'### 통신서비스 중단/작업 공지',
        r'### 공지사항',
    ]
    return any(re.search(pattern, text) for pattern in notice_patterns)


def is_notice_path(file_path: str) -> bool:
    """
    경로가 공지사항 데이터인지 판별
    
    Args:
        file_path: 파일 경로 또는 menu_path
        
    Returns:
        공지사항 경로 여부
    """
    notice_path_keywords = [
        '공지사항',
        '통신서비스중단작업공지',
        '통신사기주의보',
        '공연예매메인/공지사항',
        '공지/이용안내',
    ]
    
    path_str = str(file_path)
    for keyword in notice_path_keywords:
        if keyword in path_str:
            return True
    
    return False


# =============================================================================
# 공지사항 전처리
# =============================================================================

def clean_markdown_notice(text: str) -> str:
    """
    공지사항 마크다운 정제
    
    Args:
        text: 원본 마크다운 텍스트
        
    Returns:
        정제된 마크다운 텍스트
    """
    # CSS 스타일 제거
    text = re.sub(r'\.[\w-]+ {[^}]+}', '', text)
    text = re.sub(r'#[\w-]+ \.[\w-]+ {[^}]+}', '', text)
    text = re.sub(r'\.[\w-]+ [\w-]+ {[^}]+}', '', text)
    text = re.sub(r'\.[\w-]+ li {[^}]+}', '', text)
    
    # 표 데이터 추출 및 보존
    table_data = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
            table_lines = []
            header_line = lines[i].strip()
            table_lines.append(header_line)
            i += 1
            
            if i < len(lines) and lines[i].strip().startswith('|') and all(c in '|-' for c in lines[i].strip('|')):
                separator_line = lines[i].strip()
                table_lines.append(separator_line)
                i += 1
                table_start_idx = i - 2
                
                while i < len(lines):
                    current_line = lines[i].strip()
                    if current_line.startswith('|') and current_line.endswith('|'):
                        current_line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', current_line)
                        table_lines.append(current_line)
                        i += 1
                    else:
                        break
                
                if len(table_lines) >= 3:
                    clean_table = '\n'.join(table_lines)
                    table_data.append(clean_table)
                    table_end_idx = i
                    original_table_text = '\n'.join(lines[table_start_idx:table_end_idx])
                    text = text.replace(original_table_text, '[TABLE]')
                    continue
        i += 1
    
    # 네비게이션 제거
    text = re.sub(r'(?:\[HOME\]|HOME).*?\n', '', text, flags=re.DOTALL)
    text = re.sub(r'\[(?:이전글|다음글)\\\\.*?\]\(.*?\)|\[목록\]\(.*?\)', '', text, flags=re.DOTALL)
    text = re.sub(r'- (?:이전글|다음글) \[.*?\]\(.*?\)', '', text, flags=re.DOTALL)
    
    # HTML 태그 처리
    text = re.sub(r'<br\s*/?>|<BR\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 특수문자 처리
    text = re.sub(r'\\\[(.*?)\\\]', r'[\1]', text)
    text = re.sub(r'\\\*', '*', text)
    text = re.sub(r'\\{2,}', '', text)
    
    # 이미지 처리
    def image_replacer(match):
        alt = match.group(1)
        url = match.group(2)
        if alt.strip():
            return f'![{alt}]({url})'
        return ''
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', image_replacer, text)
    
    # 링크 처리
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 네비게이션 요소 제거
    nav_patterns = [
        r'\[목록\].*?#\)',
        r'^목록$',
        r'\[상세보기.*?\].*?".*?"\)',
        r'\[상세보기.*?\].*?\)',
        r'\[.*?바로가기.*?\].*?".*?"\)',
        r'\[.*?바로가기.*?\].*?\)',
        r'- \[가이드 전체\].*?\n',
        r'- \[.*?\]\(.*?"현재탭"\).*?\n',
        r'^\s*-\s*\[.*?\]\(.*?\)\s*$\n*',
        r'\[이전 탭.*?\].*?\n',
        r'\[다음 탭.*?\].*?\n',
        r'^\s*-\s*\[.*?\].*?\n',
        r'^\s*\[.*?\].*?"현재탭"\).*?\n',
        r'\[\s*이전글\\*.*?\]\(.*?\)',
        r'\[\s*다음글\\*.*?\]\(.*?\)',
        r'\[\s*목록\s*\]\(.*?\)',
        r'-\s*이전글\s*\[.*?\]\(.*?\)',
        r'-\s*다음글\s*\[.*?\]\(.*?\)',
        r'이전글\s*이전글이\s*없습니다\.*\s*\n*',
        r'다음글\s*다음글이\s*없습니다\.*\s*\n*',
    ]
    
    for pattern in nav_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    
    # 공백 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +$', '', text, flags=re.MULTILINE)
    
    # 표 데이터 복원
    if table_data:
        for table in table_data:
            if '[TABLE]' in text:
                text = text.replace('[TABLE]', table, 1)
            else:
                if not text.endswith('\n\n'):
                    text = text.rstrip() + '\n\n'
                text = text + table
    
    # 최종 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


# =============================================================================
# 일반 정보 전처리 (간소화 버전)
# =============================================================================

def clean_markdown_info(text: str, html_content: Optional[str] = None) -> str:
    """
    일반 정보 마크다운 정제 (간소화 버전)
    
    Args:
        text: 원본 마크다운 텍스트
        html_content: 원본 HTML (테이블 처리용, 선택적)
        
    Returns:
        정제된 마크다운 텍스트
    """
    if not text:
        return ""
    
    # 1. 백슬래시 처리
    text = re.sub(r'(\\\\|\\)+', '', text)
    
    # 2. 이미지 처리 - alt 텍스트만 유지
    def image_replacer(match):
        alt = match.group(1)
        if alt.strip():
            return alt
        return ''
    
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', image_replacer, text)
    
    # 3. 링크 처리 - 텍스트만 유지
    # JavaScript 링크
    text = re.sub(r'\[([^\]]*)\]\(javascript:[^)]*\)', r'\1', text)
    # 일반 링크
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # 빈 링크
    text = re.sub(r'\[\]\(\)', '', text)
    
    # 4. HTML 태그 제거
    text = re.sub(r'<(?:br\s*/?|p\s*/?|/p|div[^>]*|/div|span[^>]*|/span|strong|/strong|em|/em|[^>]+)>', '', text)
    
    # 5. 특수 텍스트 제거
    special_patterns = [
        (r'자막\s*열기\s*자막\s*접기', '', re.MULTILINE),
        (r'^\s*[=-]{3,}\s*$', '', re.MULTILINE),
        (r'^(?:_?닫기_?|주문하기|이전\s*다음|확인|동의|검색|레이어\s*닫기)$', '', re.MULTILINE | re.IGNORECASE),
    ]
    
    for pattern_tuple in special_patterns:
        if len(pattern_tuple) == 3:
            pattern, replacement, flags = pattern_tuple
        else:
            pattern, replacement = pattern_tuple
            flags = 0
        text = re.sub(pattern, replacement, text, flags=flags)
    
    # 6. 정리 및 포맷팅
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*-\s*', '- ', text, flags=re.MULTILINE)
    
    # 7. 용어 통일
    text = re.sub(r'피해\s*사례', '피해사례', text)
    text = re.sub(r'주의\s*사항', '주의사항', text)
    text = re.sub(r'대응\s*방안', '대응방안', text)
    
    text = text.strip()
    
    return text


# =============================================================================
# 통합 전처리 함수
# =============================================================================

def preprocess_content(
    markdown_text: str,
    menu_path: Optional[str] = None,
    html_content: Optional[str] = None
) -> Tuple[str, str]:
    """
    마크다운 콘텐츠 전처리 통합 진입점
    
    Args:
        markdown_text: 원본 마크다운 텍스트
        menu_path: 메뉴 경로 (공지사항 판별용)
        html_content: 원본 HTML (테이블 처리용, 선택적)
        
    Returns:
        Tuple[str, str]: (전처리된 텍스트, 처리 타입)
        - 처리 타입: 'notice' 또는 'info'
    """
    if not markdown_text:
        return "", "info"
    
    # 공지사항 여부 판별
    is_notice = False
    
    if menu_path and is_notice_path(menu_path):
        is_notice = True
    elif is_notice_content(markdown_text):
        is_notice = True
    
    # 처리 타입에 따른 전처리 실행
    if is_notice:
        processed = clean_markdown_notice(markdown_text)
        process_type = 'notice'
    else:
        processed = clean_markdown_info(markdown_text, html_content)
        process_type = 'info'
    
    logger.debug(f"전처리 완료: type={process_type}, length={len(processed)}")
    
    return processed, process_type


