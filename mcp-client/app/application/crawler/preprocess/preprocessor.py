"""
Markdown Preprocessor Module

마크다운 콘텐츠의 전처리를 담당하는 모듈입니다.
크롤링된 웹 페이지의 마크다운을 정제하고, 테이블 구조를 보정합니다.

주요 기능:
    - 마크다운 테이블 구조 감지 및 보정
    - HTML 테이블을 마크다운으로 변환 (rowspan/colspan 처리)
    - 공지사항/일반 정보에 따른 차별화된 전처리
    - 불필요한 요소(네비게이션, 링크, 스크립트 등) 제거
"""

import logging
import re
import regex
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# =============================================================================
# 테이블 처리 유틸리티 함수
# =============================================================================

def is_table_row(line: str) -> bool:
    """
    주어진 텍스트 라인이 마크다운 테이블 행인지 확인합니다.
    
    마크다운 테이블 행의 조건:
        1. 파이프(|) 문자 포함
        2. 구분선 형태 (|---|---|)
        3. 파이프로 시작하거나 끝남
        4. 2개 이상의 파이프를 포함하고 셀 내용이 있음
    
    Args:
        line: 검사할 텍스트 라인
    
    Returns:
        bool: 테이블 행이면 True, 아니면 False
    """
    line = line.strip()
    
    # --------------------------------------------------------
    # 빈 라인 또는 파이프가 없는 라인은 테이블 행이 아님
    # --------------------------------------------------------
    if not line:
        return False
    
    if '|' not in line:
        return False
    
    # --------------------------------------------------------
    # 구분선 확인: |---|---| 형태
    # 파이프를 제거한 후 대시와 공백만 남으면 구분선
    # --------------------------------------------------------
    content_without_pipes = line.replace('|', '')
    if all(c in '- ' for c in content_without_pipes):
        return True
    
    # --------------------------------------------------------
    # 파이프로 시작하거나 끝나면 테이블 행으로 판단
    # --------------------------------------------------------
    if line.startswith('|') or line.endswith('|'):
        return True
    
    # --------------------------------------------------------
    # 셀 내용 확인: 2개 이상의 파이프가 있고 내용이 있으면 테이블 행
    # --------------------------------------------------------
    cells = line.split('|')
    has_content = any(cell.strip() for cell in cells)
    
    if has_content or line.count('|') >= 2:
        return True
    
    return False


def is_separator_row(line: str) -> bool:
    """
    라인이 마크다운 테이블 구분선(separator)인지 확인합니다.
    
    구분선 형태: |---|---|---| 또는 | --- | --- |
    헤더와 데이터 행을 구분하는 역할을 합니다.
    
    Args:
        line: 검사할 텍스트 라인
    
    Returns:
        bool: 구분선이면 True, 아니면 False
    """
    stripped = line.strip()
    
    if not stripped:
        return False
    
    if '|' not in stripped:
        return False
    
    # --------------------------------------------------------
    # 구분선은 반드시 파이프로 시작하거나 끝나야 함
    # --------------------------------------------------------
    if not (stripped.startswith('|') or stripped.endswith('|')):
        return False
    
    # --------------------------------------------------------
    # 파이프를 제거한 후 대시와 공백만 남아야 구분선
    # --------------------------------------------------------
    content = stripped.replace('|', '')
    return all(c in '- ' for c in content)


def find_table_boundaries(lines: List[str], start_idx: int) -> Tuple[int, int]:
    """
    마크다운 텍스트에서 테이블의 시작과 끝 인덱스를 찾습니다.
    
    주어진 인덱스를 기준으로 위아래로 탐색하여 테이블의 전체 범위를 결정합니다.
    불완전한 테이블 구조도 감지하며, 단일 행 테이블도 처리합니다.
    
    Args:
        lines: 전체 텍스트를 줄 단위로 분리한 리스트
        start_idx: 탐색을 시작할 라인 인덱스
    
    Returns:
        Tuple[int, int]: (시작 인덱스, 끝 인덱스)
                         테이블이 아니면 (-1, -1) 반환
    """
    # --------------------------------------------------------
    # 시작 위치가 테이블 행이 아니면 즉시 반환
    # --------------------------------------------------------
    if not is_table_row(lines[start_idx]):
        return -1, -1
    
    original_start_idx = start_idx
    consecutive_empty_lines = 0
    max_empty_lines = 1  # 테이블 내 허용되는 최대 연속 빈 줄 수
    
    # --------------------------------------------------------
    # 상향 탐색: 테이블 시작점 찾기
    # 테이블 행이 계속되거나, 빈 줄이 1개 이하인 동안 위로 이동
    # --------------------------------------------------------
    while start_idx > 0:
        prev_line = lines[start_idx - 1].strip()
        if is_table_row(lines[start_idx - 1]):
            start_idx -= 1
            consecutive_empty_lines = 0
        elif prev_line == '':
            consecutive_empty_lines += 1
            if consecutive_empty_lines <= max_empty_lines:
                start_idx -= 1
            else:
                break
        else:
            break
    
    # --------------------------------------------------------
    # 테이블 유효성 검사: 헤더와 구분선 존재 확인
    # 처음 5줄 내에서 구분선을 찾음
    # --------------------------------------------------------
    has_header = False
    has_separator = False
    
    for i in range(start_idx, min(start_idx + 5, len(lines))):
        if i >= len(lines):
            break
        if i > start_idx and '|' in lines[i]:
            has_header = True
        if is_separator_row(lines[i]):
            has_separator = True
            break
    
    # --------------------------------------------------------
    # 단일 행 테이블 감지
    # |셀1|셀2| 형태로 파이프로 시작하고 끝나는 경우
    # --------------------------------------------------------
    first_line = lines[start_idx].strip()
    is_single_row_table = (first_line.startswith('|') and first_line.endswith('|'))
    cell_count = first_line.count('|') - 1 if first_line.startswith('|') and first_line.endswith('|') else 0
    
    # 단일 행이고 셀이 1개 이상이면 단일 행 테이블로 반환
    if is_single_row_table and cell_count >= 1:
        return start_idx, start_idx
    
    # --------------------------------------------------------
    # 구분선이 없는 경우 추가 검증
    # 최소 2개의 유효한 테이블 행이 필요
    # --------------------------------------------------------
    if not has_separator:
        valid_rows = 0
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            if i < len(lines) and is_table_row(lines[i]):
                valid_rows += 1
        
        if valid_rows < 2:
            if is_single_row_table:
                return start_idx, start_idx
            return -1, -1
    
    # --------------------------------------------------------
    # 하향 탐색: 테이블 끝점 찾기
    # 테이블 행이 아닌 줄이 나올 때까지 또는 최대 200행까지
    # --------------------------------------------------------
    end_idx = start_idx
    consecutive_non_table = 0
    max_table_rows = 200  # 테이블 최대 행 수 제한 (무한 루프 방지)
    
    while end_idx < len(lines) and (end_idx - start_idx) < max_table_rows:
        is_table = is_table_row(lines[end_idx])
        is_empty = lines[end_idx].strip() == ''
        
        if is_table or is_empty:
            if is_table:
                consecutive_non_table = 0
            end_idx += 1
            continue
        
        consecutive_non_table += 1
        if consecutive_non_table >= 1:
            break
        end_idx += 1
    
    # --------------------------------------------------------
    # 끝에서 빈 줄 또는 비-테이블 행 제거
    # 실제 테이블 내용만 포함하도록 조정
    # --------------------------------------------------------
    while end_idx > start_idx and (not is_table_row(lines[end_idx - 1]) or lines[end_idx - 1].strip() == ''):
        end_idx -= 1
    
    if end_idx <= start_idx:
        return -1, -1
    
    # --------------------------------------------------------
    # 최종 유효성 검사
    # 구분선이 있거나, 2개 이상의 행이 있거나, 단일 행 테이블인 경우 유효
    # --------------------------------------------------------
    valid_table = False
    row_count = 0
    
    if is_single_row_table and start_idx == end_idx - 1:
        return start_idx, end_idx - 1
    
    for i in range(start_idx, end_idx):
        if is_table_row(lines[i]):
            row_count += 1
        if is_separator_row(lines[i]):
            valid_table = True
            break
    
    if valid_table or row_count >= 2 or (is_single_row_table and row_count >= 1):
        return start_idx, end_idx - 1
    else:
        return -1, -1


def process_markdown_table(lines: List[str], start_idx: int, end_idx: int) -> str:
    """
    불완전한 마크다운 테이블 구조를 보정합니다.
    
    마크다운 테이블은 다음 구조를 가져야 합니다:
        | 헤더1 | 헤더2 |
        | --- | --- |
        | 데이터1 | 데이터2 |
    
    이 함수는:
        - 파이프가 없는 시작/끝에 파이프 추가
        - 구분선이 없으면 자동 생성
        - 열 수가 일치하지 않으면 빈 셀 추가
    
    Args:
        lines: 전체 텍스트 라인 리스트
        start_idx: 테이블 시작 인덱스
        end_idx: 테이블 끝 인덱스
    
    Returns:
        str: 보정된 마크다운 테이블 문자열, 실패 시 None
    """
    # 최소 1줄 이상이어야 함
    if end_idx - start_idx < 1:
        return None
    
    table_lines = []
    has_separator = False
    max_columns = 0
    
    # --------------------------------------------------------
    # 1단계: 최대 열 수 계산
    # 모든 행을 순회하며 가장 많은 열을 가진 행 기준으로 정규화
    # --------------------------------------------------------
    for i in range(start_idx, end_idx + 1):
        line = lines[i].strip()
        if '|' in line:
            # |로 시작하고 끝나면 양쪽 파이프 제외
            if line.startswith('|') and line.endswith('|'):
                columns = line.count('|') - 1
            else:
                columns = line.count('|') + 1
            max_columns = max(max_columns, columns)
    
    # --------------------------------------------------------
    # 2단계: 헤더 행 처리
    # 파이프로 시작/끝나지 않으면 추가
    # --------------------------------------------------------
    header_row = lines[start_idx].strip()
    if not header_row.startswith('|'):
        header_row = '|' + header_row
    if not header_row.endswith('|'):
        header_row = header_row + '|'
    
    # 열 수 정규화: 부족한 열은 빈 셀로 채움
    header_cells = header_row.strip('|').split('|')
    while len(header_cells) < max_columns:
        header_cells.append('')
    header_row = '|' + '|'.join(header_cells) + '|'
    table_lines.append(header_row)
    
    # --------------------------------------------------------
    # 3단계: 구분선 처리
    # 기존 구분선이 있으면 사용, 없으면 생성
    # --------------------------------------------------------
    if start_idx + 1 <= end_idx:
        next_row = lines[start_idx + 1].strip()
        if is_separator_row(next_row):
            has_separator = True
            separator = '|' + '|'.join([' --- ' for _ in range(max_columns)]) + '|'
            table_lines.append(separator)
            start_idx += 1
    
    # 구분선이 없으면 자동 생성
    if not has_separator:
        separator = '|' + '|'.join([' --- ' for _ in range(max_columns)]) + '|'
        table_lines.append(separator)
    
    # --------------------------------------------------------
    # 4단계: 데이터 행 처리
    # 각 행의 열 수를 정규화
    # --------------------------------------------------------
    for i in range(start_idx + 1, end_idx + 1):
        if is_table_row(lines[i]):
            data_row = lines[i].strip()
            if not data_row.startswith('|'):
                data_row = '|' + data_row
            if not data_row.endswith('|'):
                data_row = data_row + '|'
            
            # 열 수 정규화
            data_cells = data_row.strip('|').split('|')
            while len(data_cells) < max_columns:
                data_cells.append('')
            data_row = '|' + '|'.join(data_cells) + '|'
            table_lines.append(data_row)
    
    # 최소 2줄(헤더 + 구분선) 이상이어야 유효한 테이블
    if len(table_lines) < 2:
        return None
    
    return '\n'.join(table_lines)


def process_single_row_table(line: str) -> str:
    """
    단일 행 테이블을 마크다운 표 형식으로 변환합니다.
    
    단일 행을 헤더로 사용하고 구분선을 추가하여 
    유효한 마크다운 테이블 형식을 만듭니다.
    
    Args:
        line: 테이블 행 문자열 (예: "셀1|셀2|셀3")
    
    Returns:
        str: 헤더 + 구분선 형태의 마크다운 테이블
    
    Example:
        >>> process_single_row_table("|A|B|C|")
        "|A|B|C|\\n| --- | --- | --- |"
    """
    # 파이프로 시작/끝나지 않으면 추가
    if not line.strip().startswith('|') or not line.strip().endswith('|'):
        line = '|' + line.strip() + '|'
    
    # 셀 분리 및 정리
    cells = [cell.strip() for cell in line.strip('|').split('|')]
    header_row = '|' + '|'.join(cells) + '|'
    separator = '|' + '|'.join([' --- ' for _ in range(len(cells))]) + '|'
    
    return header_row + '\n' + separator


def extract_table_from_html(html_content: str) -> List[str]:
    """
    HTML 콘텐츠에서 <table> 태그를 추출하여 마크다운 형식으로 변환합니다.
    
    HTML 테이블의 복잡한 구조를 정확히 처리합니다:
        - rowspan: 세로로 병합된 셀
        - colspan: 가로로 병합된 셀
        - thead/th: 헤더 구분
        - colgroup: 열 정의
    
    변환 과정:
        1. 열 수 계산 (colspan 고려)
        2. 2D 그리드 생성
        3. rowspan/colspan 확장하여 그리드 채우기
        4. 마크다운 테이블 문자열 생성
    
    Args:
        html_content: HTML 콘텐츠 문자열
        
    Returns:
        List[str]: 마크다운 테이블 문자열 리스트
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')
        
        if not tables:
            return []
        
        markdown_tables = []
        
        for table in tables:
            rows = table.find_all('tr')
            row_count = len(rows)
            
            if row_count == 0:
                continue
            
            # --------------------------------------------------------
            # 헤더 태그 존재 확인
            # <thead> 또는 첫 번째 행의 <th> 태그로 판단
            # --------------------------------------------------------
            has_header_tags = False
            thead = table.find('thead')
            if thead and thead.find_all('th'):
                has_header_tags = True
            elif rows[0].find_all('th'):
                has_header_tags = True
            
            # --------------------------------------------------------
            # 열 수 계산: colspan을 고려하여 최대 열 수 결정
            # --------------------------------------------------------
            header_row = rows[0]
            header_cells = header_row.find_all(['th', 'td'])
            header_col_count = sum(int(cell.get('colspan', 1)) for cell in header_cells)
            
            # 데이터 행에서 최대 열 수 계산
            max_data_col_count = 0
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                row_col_count = sum(int(cell.get('colspan', 1)) for cell in cells)
                max_data_col_count = max(max_data_col_count, row_col_count)
            
            col_count = max(header_col_count, max_data_col_count)
            
            # colgroup에서 열 수 확인 (더 정확할 수 있음)
            colgroup = table.find('colgroup')
            if colgroup:
                cols = colgroup.find_all('col')
                if cols and len(cols) > 0:
                    col_count = max(col_count, len(cols))
            
            # 최소 2열 보장
            col_count = max(2, col_count)
            
            # --------------------------------------------------------
            # 열 사용 빈도 분석
            # 5열 이상인 경우, 실제 사용되는 열만 추출하여 최적화
            # --------------------------------------------------------
            if col_count >= 5:
                data_distribution = [0] * col_count
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for idx, cell in enumerate(cells):
                        if idx < col_count and cell.get_text(strip=True):
                            span = int(cell.get('colspan', 1))
                            for s in range(span):
                                if idx + s < col_count:
                                    data_distribution[idx + s] += 1
                
                # 실제 데이터가 있는 열 수
                active_cols = sum(1 for count in data_distribution if count > 0)
                if active_cols <= 3 and col_count > 4:
                    col_count = min(col_count, active_cols + 1)
            
            # --------------------------------------------------------
            # 2D 그리드 생성
            # rowspan/colspan 확장을 위한 작업 공간
            # --------------------------------------------------------
            grid = [[None for _ in range(col_count)] for _ in range(row_count)]
            
            # --------------------------------------------------------
            # 병합 셀 처리 (rowspan, colspan)
            # 병합된 셀의 내용을 해당하는 모든 그리드 위치에 복사
            # --------------------------------------------------------
            for row_idx, row in enumerate(rows):
                col_idx = 0
                cells = row.find_all(['td', 'th'])
                
                for cell in cells:
                    # 이미 채워진 셀(이전 rowspan에 의해) 건너뛰기
                    while col_idx < col_count and grid[row_idx][col_idx] is not None:
                        col_idx += 1
                    
                    if col_idx >= col_count:
                        break
                    
                    # 병합 속성 추출
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    
                    # 셀 텍스트 추출 및 정리
                    content = cell.get_text(separator=' ', strip=True)
                    content = re.sub(r'\s+', ' ', content)
                    
                    # 병합된 영역 전체에 내용 채우기
                    for r in range(rowspan):
                        for c in range(colspan):
                            if row_idx + r < row_count and col_idx + c < col_count:
                                grid[row_idx + r][col_idx + c] = content
                    
                    col_idx += colspan
            
            # 빈 셀(None)을 빈 문자열로 변환
            grid = [['' if cell is None else cell for cell in row] for row in grid]
            
            # --------------------------------------------------------
            # 실제 사용 열 수 재계산
            # 뒤쪽의 빈 열 제거
            # --------------------------------------------------------
            actual_col_count = 0
            for col_idx in range(col_count):
                has_content = False
                for row_idx in range(row_count):
                    if grid[row_idx][col_idx]:
                        has_content = True
                        break
                if has_content:
                    actual_col_count = col_idx + 1
            
            if actual_col_count > 0 and actual_col_count < col_count:
                grid = [row[:actual_col_count] for row in grid]
                col_count = actual_col_count
            
            # --------------------------------------------------------
            # 마크다운 테이블 생성
            # --------------------------------------------------------
            if row_count == 1:
                # 단일 행 테이블: 헤더만 있는 테이블
                header_line = '|' + '|'.join(str(cell) for cell in grid[0]) + '|'
                markdown_table = process_single_row_table(header_line)
                markdown_tables.append('\n' + markdown_table + '\n')
            else:
                markdown_table_lines = []
                
                if has_header_tags:
                    # 헤더가 있는 경우: 첫 행을 헤더로 사용
                    header = '|' + '|'.join(str(cell) for cell in grid[0]) + '|'
                    markdown_table_lines.append(header)
                    separator = '|' + '|'.join(' --- ' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(separator)
                    
                    # 데이터 행 추가 (구분선 패턴만 있는 행 제외)
                    for row in grid[1:]:
                        if all(cell.strip().replace('-', '') == '' for cell in row):
                            continue
                        data_row = '|' + '|'.join(str(cell) for cell in row) + '|'
                        markdown_table_lines.append(data_row)
                else:
                    # 헤더가 없는 경우: 빈 헤더 생성
                    empty_header = '|' + '|'.join('' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(empty_header)
                    separator = '|' + '|'.join(' --- ' for _ in range(col_count)) + '|'
                    markdown_table_lines.append(separator)
                    
                    for row in grid:
                        if all(cell.strip().replace('-', '') == '' for cell in row):
                            continue
                        data_row = '|' + '|'.join(str(cell) for cell in row) + '|'
                        markdown_table_lines.append(data_row)
                
                markdown_tables.append('\n' + '\n'.join(markdown_table_lines) + '\n')
        
        return markdown_tables
            
    except Exception as e:
        logger.warning(f"[extract_table_from_html] Error: {e}")
        return []


def clean_js_patterns_in_table(table_content: str) -> str:
    """
    테이블 내부의 JavaScript 링크 패턴을 정리합니다.
    
    마크다운 변환 시 [텍스트](javascript:...) 형태의 링크가 
    테이블 셀에 포함될 수 있습니다. 이 함수는 JavaScript 링크를
    순수 텍스트로 변환합니다.
    
    처리하는 패턴 예시:
        - [텍스트](javascript:void(0))
        - [텍스트](javascript:someFunction())
        - [텍스트](javascript:kt_common.ktMenuLinkStat(...))
    
    Args:
        table_content: 테이블 마크다운 문자열
    
    Returns:
        str: JavaScript 링크가 제거된 테이블 문자열
    """
    if not table_content:
        return table_content
    
    # JavaScript 링크 패턴 목록 (우선순위 순)
    js_patterns = [
        # 완전한 javascript:void(0) 패턴
        (r'\[([^\]]*)\]\(javascript:void\(0\)(?:\s*;[^)]*)?(?:\s+"(?:[^"\\]|\\.)*")?\s*\)', r'\1'),
        # KT 전용 JavaScript 함수 패턴
        (r'\[([^\]]*)\]\(javascript:(?:kt_common\.ktMenuLinkStat|wDicProd\.lnkBtn|detailClickStatistics\.click)\([^)]*\)(?:\s*;[^)]*)*\)', r'\1'),
        # 일반 javascript: 패턴
        (r'\[([^\]]*)\]\(javascript:[^)]*\)', r'\1'),
        (r'\[([^\]]*)\]\([^)]*javascript[^)]*\)', r'\1'),
        # 불완전한 패턴 (닫는 괄호 없음)
        (r'([^\]]+)\]\(javascript:[^)]*\)', r'\1'),
        (r'([^\]]+)\]\(javascript:void\(0[^)]*', r'\1'),
        (r'([^\]]+)\]\([^)]*javascript[^)]*', r'\1'),
        (r'([^\]]+)\]\([^)]*;[^)]*$', r'\1'),
        # 잔여 괄호 정리
        (r'([^)]+)"\)$', r'\1'),
        (r'([^)]+)\)$', r'\1'),
    ]
    
    for pattern, replacement in js_patterns:
        table_content = regex.sub(pattern, replacement, table_content)
    
    return table_content


def postprocess_duplicate_table_headers(text: str) -> str:
    """
    중복된 테이블 헤더와 구분선 패턴을 제거합니다.
    
    HTML에서 마크다운으로 변환 시 헤더가 중복 생성되는 경우가 있습니다.
    예를 들어:
        |   |   |
        |---|---|
        |헤더1|헤더2|
        |---|---|
    
    이 함수는 이러한 중복을 감지하고 정리합니다.
    
    Args:
        text: 마크다운 텍스트
    
    Returns:
        str: 중복 헤더가 제거된 마크다운 텍스트
    """
    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        # --------------------------------------------------------
        # 연속된 구분선 처리: 첫 번째만 유지
        # --------------------------------------------------------
        if i < len(lines) and is_separator_row(lines[i]):
            if i + 1 < len(lines) and is_separator_row(lines[i + 1]):
                result_lines.append(lines[i])
                i += 2
                continue
        
        # --------------------------------------------------------
        # 중복 헤더 패턴 감지
        # 패턴: 헤더1 -> 구분선 -> 헤더2 -> 구분선
        # --------------------------------------------------------
        if i < len(lines) and is_table_row(lines[i]):
            first_header = lines[i]
            is_first_header_empty = all(cell.strip() == '' for cell in first_header.strip('|').split('|') if cell != '')
            
            if i + 1 < len(lines) and is_separator_row(lines[i + 1]):
                first_separator = lines[i + 1]
                
                if i + 2 < len(lines) and is_table_row(lines[i + 2]):
                    second_header = lines[i + 2]
                    is_second_header_empty = all(cell.strip() == '' for cell in second_header.strip('|').split('|') if cell != '')
                    
                    if i + 3 < len(lines) and is_separator_row(lines[i + 3]):
                        # 두 헤더 모두 비어있음: 첫 번째 사용
                        if is_first_header_empty and is_second_header_empty:
                            result_lines.append(first_header)
                            result_lines.append(first_separator)
                            i += 4
                            continue
                        # 첫 번째만 비어있음: 두 번째 헤더 사용
                        elif is_first_header_empty and not is_second_header_empty:
                            result_lines.append(second_header)
                            result_lines.append(first_separator)
                            i += 4
                            continue
        
        if i < len(lines):
            result_lines.append(lines[i])
        i += 1
    
    return '\n'.join(result_lines)


# =============================================================================
# 공지사항 판별 함수
# =============================================================================

def is_notice_content(text: str) -> bool:
    """
    마크다운 텍스트 내용을 분석하여 공지사항인지 판별합니다.
    
    특정 헤딩 패턴으로 공지사항 여부를 결정합니다.
    공지사항은 일반 정보와 다른 전처리 로직이 적용됩니다.
    
    판별 기준 (헤딩 패턴):
        - "# 통신사기주의보"
        - "### 통신서비스 중단/작업 공지"
        - "### 공지사항"
    
    Args:
        text: 검사할 마크다운 텍스트
        
    Returns:
        bool: 공지사항이면 True, 아니면 False
    """
    notice_patterns = [
        r'# 통신사기주의보',
        r'### 통신서비스 중단/작업 공지',
        r'### 공지사항',
    ]
    return any(re.search(pattern, text) for pattern in notice_patterns)


def is_notice_path(file_path: str) -> bool:
    """
    파일 경로 또는 메뉴 경로를 분석하여 공지사항인지 판별합니다.
    
    경로에 공지사항 관련 키워드가 포함되어 있으면 공지사항으로 판단합니다.
    
    판별 키워드:
        - "공지사항"
        - "통신서비스중단작업공지"
        - "통신사기주의보"
        - "공연예매메인/공지사항"
        - "공지/이용안내"
    
    Args:
        file_path: 파일 경로 또는 menu_path 문자열
        
    Returns:
        bool: 공지사항 경로이면 True, 아니면 False
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
    공지사항 마크다운을 정제합니다.
    
    공지사항은 일반 정보와 다른 특성을 가집니다:
        - 네비게이션 링크 (이전글/다음글/목록)
        - 날짜 정보
        - 간단한 테이블 구조
    
    처리 단계:
        1. CSS 스타일 블록 제거
        2. 테이블 추출 및 임시 마커로 대체
        3. 네비게이션 요소 제거
        4. HTML 태그 및 특수문자 정리
        5. 링크를 텍스트로 변환
        6. 테이블 복원
    
    Args:
        text: 원본 마크다운 텍스트
        
    Returns:
        str: 정제된 마크다운 텍스트
    """
    # ============================================================
    # 1단계: CSS 스타일 블록 제거
    # 마크다운 내에 포함된 CSS 정의 제거
    # ============================================================
    text = re.sub(r'\.[\w-]+ {[^}]+}', '', text)
    text = re.sub(r'#[\w-]+ \.[\w-]+ {[^}]+}', '', text)
    text = re.sub(r'\.[\w-]+ [\w-]+ {[^}]+}', '', text)
    text = re.sub(r'\.[\w-]+ li {[^}]+}', '', text)
    
    # ============================================================
    # 2단계: 테이블 추출 및 임시 마커로 대체
    # 테이블은 별도 처리 후 복원
    # ============================================================
    table_data = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        # 테이블 시작 감지: |로 시작하고 끝나는 행
        if lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
            table_lines = []
            header_line = lines[i].strip()
            table_lines.append(header_line)
            i += 1
            
            # 구분선 확인
            if i < len(lines) and lines[i].strip().startswith('|') and all(c in '|-' for c in lines[i].strip('|')):
                separator_line = lines[i].strip()
                table_lines.append(separator_line)
                i += 1
                table_start_idx = i - 2
                
                # 데이터 행 수집
                while i < len(lines):
                    current_line = lines[i].strip()
                    if current_line.startswith('|') and current_line.endswith('|'):
                        # 링크를 텍스트로 변환
                        current_line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', current_line)
                        table_lines.append(current_line)
                        i += 1
                    else:
                        break
                
                # 유효한 테이블 (최소 헤더 + 구분선 + 데이터 1행)
                if len(table_lines) >= 3:
                    clean_table = '\n'.join(table_lines)
                    table_data.append(clean_table)
                    table_end_idx = i
                    original_table_text = '\n'.join(lines[table_start_idx:table_end_idx])
                    text = text.replace(original_table_text, '[TABLE]')
                    continue
        i += 1
    
    # ============================================================
    # 3단계: 네비게이션 요소 제거
    # 공지사항 특유의 네비게이션 패턴 제거
    # ============================================================
    text = re.sub(r'(?:\[HOME\]|HOME).*?\n', '', text, flags=re.DOTALL)
    text = re.sub(r'\[(?:이전글|다음글)\\\\.*?\]\(.*?\)|\[목록\]\(.*?\)', '', text, flags=re.DOTALL)
    text = re.sub(r'- (?:이전글|다음글) \[.*?\]\(.*?\)', '', text, flags=re.DOTALL)
    
    # ============================================================
    # 4단계: HTML 태그 및 특수문자 정리
    # ============================================================
    # <br> 태그를 공백으로 변환
    text = re.sub(r'<br\s*/?>|<BR\s*/?>', ' ', text)
    # 기타 HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    
    # 이스케이프된 특수문자 정리
    text = re.sub(r'\\\[(.*?)\\\]', r'[\1]', text)  # \[...\] -> [...]
    text = re.sub(r'\\\*', '*', text)                # \* -> *
    text = re.sub(r'\\{2,}', '', text)               # 연속 백슬래시 제거
    
    # ============================================================
    # 5단계: 이미지 및 링크 처리
    # ============================================================
    # 이미지: alt 텍스트가 있으면 유지, 없으면 제거
    def image_replacer(match):
        alt = match.group(1)
        url = match.group(2)
        if alt.strip():
            return f'![{alt}]({url})'
        return ''
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', image_replacer, text)
    
    # 링크를 텍스트로 변환: [텍스트](URL) -> 텍스트
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # ============================================================
    # 6단계: 추가 네비게이션 패턴 제거
    # ============================================================
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
    
    # ============================================================
    # 7단계: 공백 정리
    # ============================================================
    text = re.sub(r'\n{3,}', '\n\n', text)  # 3개 이상 연속 줄바꿈 -> 2개
    text = re.sub(r' +$', '', text, flags=re.MULTILINE)  # 줄 끝 공백 제거
    
    # ============================================================
    # 8단계: 테이블 복원
    # ============================================================
    if table_data:
        for table in table_data:
            if '[TABLE]' in text:
                text = text.replace('[TABLE]', table, 1)
            else:
                # 마커가 제거된 경우 끝에 추가
                if not text.endswith('\n\n'):
                    text = text.rstrip() + '\n\n'
                text = text + table
    
    # 최종 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    return text


# =============================================================================
# 일반 정보 전처리 (HTML 테이블 처리 포함)
# =============================================================================

def clean_markdown_info(text: str, html_content: Optional[str] = None) -> str:
    """
    일반 정보 마크다운을 정제합니다. (HTML 테이블 병합 셀 처리 포함)
    
    가장 복잡한 전처리 함수로, 다양한 마크다운 요소를 처리합니다.
    특히 HTML 테이블의 rowspan/colspan을 정확히 변환합니다.
    
    처리 단계:
        1. 마크다운 테이블 위치 찾기 및 마커로 대체
        2. HTML에서 테이블 추출 (rowspan/colspan 처리)
        3. 텍스트 정리:
            - 백슬래시 제거
            - 이미지 처리 (alt 텍스트만 유지)
            - 링크 처리 (JavaScript 링크 제거)
            - HTML 태그 제거
            - 불필요한 UI 텍스트 제거
        4. 테이블 처리 및 복원
        5. 중복 테이블 헤더 제거
    
    Args:
        text: 원본 마크다운 텍스트
        html_content: 원본 HTML (테이블 처리용, 선택적)
                     제공 시 rowspan/colspan이 정확히 처리됨
        
    Returns:
        str: 정제된 마크다운 텍스트
    """
    if not text:
        return ""
    
    # ============================================================
    # 1단계: 테이블 위치 찾기 및 마커로 대체
    # 테이블을 마커로 대체하여 텍스트 처리 중 손상 방지
    # ============================================================
    table_data = []
    lines = text.split('\n')
    
    i = 0
    processed_ranges = []
    max_iterations = len(lines) * 2
    iteration_count = 0
    
    while i < len(lines):
        iteration_count += 1
        if iteration_count > max_iterations:
            break
        
        # 이미 처리된 범위 확인
        is_processed = False
        for start, end in processed_ranges:
            if start <= i <= end:
                is_processed = True
                i = end + 1
                break
        
        if is_processed:
            continue
        
        line = lines[i].strip()
        if '|' in line:
            start_idx, end_idx = find_table_boundaries(lines, i)
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                already_processed = False
                for start, end in processed_ranges:
                    if not (end_idx < start or start_idx > end):
                        already_processed = True
                        break
                
                if already_processed:
                    i += 1
                    continue
                
                original_table = '\n'.join(lines[start_idx:end_idx + 1])
                table_marker = f'<<__TABLE_MARKER_{len(table_data)}__>>'
                
                processed_ranges.append((start_idx, end_idx))
                
                orig_pos = text.find(original_table)
                
                # 컨텍스트 저장
                context_before = []
                context_after = []
                
                for j in range(start_idx - 5, start_idx):
                    if j >= 0 and j < len(lines):
                        context_before.append(lines[j])
                
                for j in range(end_idx + 1, end_idx + 6):
                    if j < len(lines):
                        context_after.append(lines[j])
                
                is_single_row = start_idx == end_idx and lines[start_idx].strip().startswith('|') and lines[start_idx].strip().endswith('|')
                
                table_data.append({
                    'marker': table_marker,
                    'original': original_table,
                    'processed': None,
                    'original_position': orig_pos,
                    'table_index': len(table_data),
                    'context_before': context_before,
                    'context_after': context_after,
                    'is_single_row': is_single_row
                })
                
                if orig_pos >= 0:
                    text = text[:orig_pos] + table_marker + text[orig_pos + len(original_table):]
                else:
                    text = text.replace(original_table, table_marker)
                i = end_idx + 1
                continue
        i += 1
    
    # ============================================================
    # HTML에서 테이블 추출
    # HTML 원본이 있으면 rowspan/colspan을 정확히 처리 가능
    # ============================================================
    html_tables = []
    if html_content:
        try:
            html_tables = extract_table_from_html(html_content)
        except Exception as e:
            logger.warning(f"[clean_markdown_info] HTML table extraction error: {e}")
    
    # 마커 보호 함수
    def protect_markers(text, table_data):
        markers_map = {}
        for i, table in enumerate(table_data):
            marker = table['marker']
            if marker in text:
                temp_key = f"___PROTECTED_MARKER_{i}___"
                markers_map[temp_key] = marker
                text = text.replace(marker, temp_key)
        return text, markers_map

    def restore_markers(text, markers_map):
        for temp_key, marker in markers_map.items():
            text = text.replace(temp_key, marker)
        return text

    def safe_regex_sub(pattern, repl, text, **kwargs):
        protected_text, markers_map = protect_markers(text, table_data)
        processed_text = regex.sub(pattern, repl, protected_text, **kwargs)
        restored_text = restore_markers(processed_text, markers_map)
        return restored_text
    
    # 2단계: 텍스트 정리
    # 2.1 백슬래시 처리
    text = safe_regex_sub(r'(\\\\|\\)+', '', text)
    
    # 2.2 이미지 처리
    def image_replacer(match):
        alt = match.group(1)
        if alt.strip():
            return alt
        return ''
    
    text = safe_regex_sub(r'!\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)', image_replacer, text)
    
    prev_text = ""
    iteration_count = 0
    max_iterations = 3
    while prev_text != text and iteration_count < max_iterations:
        prev_text = text
        text = regex.sub(r'!\[(.*?)\]\((.*?)\)', image_replacer, text)
        iteration_count += 1
    
    # 2.3 링크 처리
    # JavaScript 링크
    text = safe_regex_sub(r'\[([^\]]*)\]\(javascript:void\(0\)(?:\s*;[^)]*)?(?:\s+"(?:[^"\\]|\\.)*")?\s*\)', r'\1', text)
    text = safe_regex_sub(r'\[([^\]]*)\]\(javascript:[^)]*\)', r'\1', text)
    
    # 특수 링크 패턴
    special_patterns = [
        (r'\[([^\]]*)\[([^\]]*)\]\]\([^)]*\)', r'\1[\2]'),
        (r'\[\s*([^\]]*?)\s*\]\([^)]*\s+"[^"]*"\s*\)', r'\1'),
        (r'\[([^\]]*)\]\(mailto:.*?\)', r'\1'),
        (r'\[\]\(\)', ''),
        (r'\[([^\]]*)\]\(#\)', r'\1 '),
        (r'\[([^\]]*)\]\(/[^)]*?\.aspx\)', r'\1 '),
        (r'\[([^\]]*)\]\(\?[^)]*\s*"[^"]*"\)', r'\1'),
    ]
    
    for pattern, replacement in special_patterns:
        text = safe_regex_sub(pattern, replacement, text)
    
    # 일반 링크 처리
    for _ in range(3):
        prev_text = text
        text = safe_regex_sub(r'\[([^\[\]]*?)\]\((?:[^()]|\([^()]*\))*?\)', r'\1', text)
        if prev_text == text:
            break
    
    # 2.4 HTML 태그 제거
    html_tag_pattern = r'<(?:br\s*/?|p\s*/?|/p|div[^>]*|/div|span[^>]*|/span|strong|/strong|em|/em|[^>]+)>'
    text = safe_regex_sub(html_tag_pattern, '', text)
    
    # 2.5 특수 텍스트 제거
    special_text_patterns = [
        (r'자막\s*열기\s*자막\s*접기|(?:\[자막 열기\](?:\([^)]*\))?\s*\[자막 접기\](?:\([^)]*\))?)', '', regex.MULTILINE),
        (r'^\s*[=-]{3,}\s*$', '', regex.MULTILINE),
        (r'(?:\[HOME\]|HOME).*?\n|\[(?:이전글|다음글)\\\\.*?\]\(.*?\)|\[목록\]\(.*?\)|(?:이전글|다음글) \[.*?\]\(.*?\)', '', regex.DOTALL),
        (r'^(?:_?닫기_?|주문하기|이전\s*다음|확인|동의|검색|레이어\s*닫기|prevnext|Pause|상세검색|카카오톡페이스북트위터라인닫기|하루\s*동안\s*보지\s*않기닫기)$', '', regex.MULTILINE | regex.IGNORECASE),
    ]
    
    for pattern_tuple in special_text_patterns:
        if len(pattern_tuple) == 3:
            pattern, replacement, flags = pattern_tuple
        else:
            pattern, replacement = pattern_tuple
            flags = 0
        text = safe_regex_sub(pattern, replacement, text, flags=flags)
    
    # 2.6 정리 및 포맷팅
    text = safe_regex_sub(r'\n{3,}', '\n\n', text)
    text = safe_regex_sub(r' +$', '', text, flags=regex.MULTILINE)
    text = safe_regex_sub(r'^\s*-\s*', '- ', text, flags=regex.MULTILINE)
    
    # 2.7 용어 통일
    text = safe_regex_sub(r'피해\s*사례', '피해사례', text)
    text = safe_regex_sub(r'주의\s*사항', '주의사항', text)
    text = safe_regex_sub(r'대응\s*방안', '대응방안', text)
    
    # 3단계: 테이블 처리
    for idx, table in enumerate(table_data):
        marker = table['marker']
        current_pos = text.find(marker)
        if current_pos >= 0:
            table['current_position'] = current_pos
        else:
            table['current_position'] = table.get('original_position', float('inf'))
        
        # HTML 테이블이 있으면 사용
        if html_tables and idx < len(html_tables):
            html_table_content = html_tables[idx]
            html_table_content = clean_js_patterns_in_table(html_table_content)
            table['processed'] = html_table_content
        else:
            # 마크다운 테이블 처리
            if table.get('is_single_row', False):
                original_table = table['original']
                original_table = clean_js_patterns_in_table(original_table)
                processed_table = process_single_row_table(original_table)
                table['processed'] = processed_table if processed_table else original_table
            else:
                original_table = table['original']
                original_table = clean_js_patterns_in_table(original_table)
                table_lines = original_table.split('\n')
                processed_table = process_markdown_table(table_lines, start_idx=0, end_idx=len(table_lines) - 1)
                table['processed'] = processed_table if processed_table else original_table
    
    # 추가 HTML 테이블 처리
    if html_tables and len(html_tables) > len(table_data):
        for i in range(len(table_data), len(html_tables)):
            if i > 0 and i-1 < len(table_data):
                prev_table = table_data[i-1]
                next_pos = text.find(prev_table['marker']) + len(prev_table['marker'])
            else:
                next_pos = len(text)
            
            new_marker = f'<<__TABLE_MARKER_{len(table_data)}__>>'
            table_data.append({
                'marker': new_marker,
                'original': '',
                'processed': html_tables[i],
                'original_position': next_pos,
                'current_position': next_pos,
                'table_index': len(table_data)
            })
            text = text[:next_pos] + '\n\n' + new_marker + '\n\n' + text[next_pos:]
    
    # 마커를 처리된 테이블로 교체
    sorted_tables = sorted(table_data, key=lambda t: t.get('current_position', float('inf')))
    
    for table in sorted_tables:
        marker = table['marker']
        if marker in text:
            processed = table['processed'] or table['original']
            if processed:
                text = text.replace(marker, processed)
            else:
                text = text.replace(marker, '')
        else:
            processed = table['processed'] or table['original']
            if not processed:
                continue
            
            # 컨텍스트 기반 삽입 시도
            inserted = False
            
            if 'context_before' in table and table['context_before']:
                context_before = '\n'.join(table['context_before'])
                if context_before:
                    context_pos = text.find(context_before)
                    if context_pos >= 0:
                        insert_pos = context_pos + len(context_before)
                        if insert_pos > 0 and text[insert_pos-1] != '\n':
                            processed = '\n' + processed
                        if insert_pos < len(text) and text[insert_pos] != '\n':
                            processed = processed + '\n'
                        text = text[:insert_pos] + processed + text[insert_pos:]
                        inserted = True
            
            if not inserted and 'context_after' in table and table['context_after']:
                context_after = '\n'.join(table['context_after'])
                if context_after:
                    context_pos = text.find(context_after)
                    if context_pos >= 0:
                        insert_pos = context_pos
                        if insert_pos > 0 and text[insert_pos-1] != '\n':
                            processed = '\n' + processed
                        if insert_pos < len(text) and text[insert_pos] != '\n':
                            processed = processed + '\n'
                        text = text[:insert_pos] + processed + text[insert_pos:]
                        inserted = True
            
            if not inserted:
                if 'original_position' in table and table['original_position'] >= 0:
                    orig_pos = table['original_position']
                    if orig_pos < len(text):
                        text = text[:orig_pos] + processed + text[orig_pos:]
                    else:
                        text += "\n\n" + processed
                else:
                    text += "\n\n" + processed
    
    # 남은 마커 제거
    final_remaining_markers = [marker for table in table_data if (marker := table['marker']) in text]
    for marker in final_remaining_markers:
        text = text.replace(marker, '')
    
    text = text.strip()
    text = postprocess_duplicate_table_headers(text)
    
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
    마크다운 콘텐츠 전처리 통합 진입점입니다.
    
    콘텐츠 타입(공지사항/일반 정보)을 자동으로 판별하고
    적절한 전처리 로직을 적용합니다.
    
    판별 우선순위:
        1. menu_path에 공지사항 키워드가 있는 경우
        2. markdown_text에 공지사항 헤딩 패턴이 있는 경우
        3. 위 조건에 해당하지 않으면 일반 정보로 처리
    
    Args:
        markdown_text: 원본 마크다운 텍스트
        menu_path: 메뉴 경로 문자열 (공지사항 판별용, 선택적)
        html_content: 원본 HTML 문자열 (테이블 처리용, 선택적)
                     제공 시 rowspan/colspan이 정확히 처리됨
        
    Returns:
        Tuple[str, str]: (전처리된 텍스트, 처리 타입)
            - 처리 타입: 'notice' 또는 'info'
    
    Example:
        >>> processed, ptype = preprocess_content(md_text, menu_path="/공지사항/목록")
        >>> print(ptype)  # 'notice'
    """
    if not markdown_text:
        return "", "info"
    
    # ============================================================
    # 공지사항 여부 판별
    # 1순위: 경로 기반 판별
    # 2순위: 콘텐츠 기반 판별
    # ============================================================
    is_notice = False
    
    if menu_path and is_notice_path(menu_path):
        is_notice = True
    elif is_notice_content(markdown_text):
        is_notice = True
    
    # ============================================================
    # 처리 타입에 따른 전처리 실행
    # - notice: 공지사항 특화 전처리
    # - info: 일반 정보 전처리 (HTML 테이블 처리 포함)
    # ============================================================
    if is_notice:
        processed = clean_markdown_notice(markdown_text)
        process_type = 'notice'
    else:
        processed = clean_markdown_info(markdown_text, html_content)
        process_type = 'info'
    
    logger.debug(f"[preprocess_content] Done: type={process_type}, len={len(processed)}")
    
    return processed, process_type


