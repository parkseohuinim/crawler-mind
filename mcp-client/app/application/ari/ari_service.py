"""ARI HTML Processing Service"""
import logging
import tempfile
from typing import List, Dict, Any, Optional
try:
    from markdownify import markdownify as md_convert
except Exception:  # 런타임 환경에 따라 미설치 가능
    md_convert = None  # graceful fallback

try:
    import pymupdf4llm
    import fitz  # PyMuPDF
except ImportError:
    pymupdf4llm = None
    fitz = None

from fastapi import UploadFile
import uuid
import os
import json
from datetime import datetime
from bs4 import BeautifulSoup
from app.infrastructure.mcp.mcp_service import mcp_service

logger = logging.getLogger(__name__)

class AriService:
    """ARI HTML 파일 처리 서비스"""
    
    def __init__(self):
        self.temp_dir = "/tmp/ari_html"
        self.output_dir = "/tmp/ari_json"
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def process_html_files(self, files: List[UploadFile]) -> Dict[str, Any]:
        """
        HTML 파일들을 처리하여 header, footer, sidebar를 제외하고 JSON 형태로 저장
        
        Args:
            files: 업로드된 HTML 파일들
            
        Returns:
            처리 결과 정보
        """
        try:
            if not files:
                raise ValueError("업로드된 파일이 없습니다")
            
            # 파일 저장 및 처리
            processed_files = []
            total_size = 0
            
            for file in files:
                if not file.filename.endswith('.html'):
                    logger.warning(f"HTML이 아닌 파일 무시: {file.filename}")
                    continue
                
                # 고유한 파일명 생성
                file_id = str(uuid.uuid4())
                file_path = os.path.join(self.temp_dir, f"{file_id}_{file.filename}")
                json_path = os.path.join(self.output_dir, f"{file_id}.json")
                
                # 파일 저장
                content = await file.read()
                total_size += len(content)
                
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                # HTML에서 header, footer, sidebar 제외하여 JSON으로 변환
                processed_data = await self._extract_main_content(content.decode('utf-8', errors='ignore'))
                
                # JSON 파일로 저장
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(processed_data, f, ensure_ascii=False, indent=2)
                
                processed_files.append({
                    'original_filename': file.filename,
                    'file_id': file_id,
                    'file_path': file_path,
                    'json_path': json_path,
                    'size': len(content),
                    'processed_data': processed_data,
                    'upload_time': datetime.now().isoformat()
                })
                
                logger.info(f"HTML 파일 처리 완료: {file.filename} ({len(content)} bytes)")
            
            return {
                'success': True,
                'processed_files': processed_files,
                'total_files': len(processed_files),
                'total_size': total_size,
                'message': f"{len(processed_files)}개의 HTML 파일이 성공적으로 처리되었습니다"
            }
            
        except Exception as e:
            logger.error(f"HTML 파일 처리 중 오류: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"HTML 파일 처리 중 오류가 발생했습니다: {str(e)}"
            }
    
    async def _extract_main_content(self, html_content: str) -> Dict[str, Any]:
        """
        HTML에서 header, footer, sidebar를 제외한 메인 콘텐츠를 추출하여 JSON으로 변환
        
        Args:
            html_content: 원본 HTML 내용
            
        Returns:
            추출된 콘텐츠의 JSON 데이터
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제거할 요소들 (header, footer, sidebar, nav 등 + Confluence 특화)
            elements_to_remove = [
                'header', 'footer', 'nav', 'aside', 'sidebar',
                '.header', '.footer', '.nav', '.aside', '.sidebar',
                '.navigation', '.menu', '.breadcrumb',
                
                # Confluence 특화 UI 요소들
                'div.aui-page-header-actions',     # 페이지 액션 버튼들
                'div.page-metadata',               # 페이지 메타데이터
                'ul.aui-nav-breadcrumbs',         # 브레드크럼
                'div.page-actions',               # 페이지 액션들
                'div.aui-toolbar2',               # 툴바
                'div.comment-container',          # 댓글 컨테이너
                'div.like-button-container',      # 좋아요 버튼
                'div.page-labels',                # 페이지 라벨
                'div.comment-actions',            # 댓글 액션
                'span.st-table-filter',           # 스마트 테이블 필터
                'svg',                            # SVG 아이콘들
                'div.confluence-information-macro', # 정보 매크로
                'div.aui-message',                # 메시지
                'div.page-metadata-modification-info', # 수정 정보
                '.aui-page-header-actions',       # 페이지 헤더 액션
                '.page-metadata',                 # 페이지 메타데이터 (클래스)
                '.like-button-container',         # 좋아요 버튼 (클래스)
                '.page-labels',                   # 페이지 라벨 (클래스)
            ]
            
            # 요소 제거
            for selector in elements_to_remove:
                for element in soup.select(selector):
                    element.decompose()
            
            # 메인 콘텐츠 추출 - Confluence 특화
            main_content = None
            
            # 1. Confluence의 main-content 영역 우선 찾기
            main_content = soup.find('div', {'id': 'main-content'})
            
            # 2. wiki-content 클래스가 있는 div 찾기
            if not main_content:
                main_content = soup.find('div', {'class': 'wiki-content'})
            
            # 3. 일반적인 main 태그 찾기
            if not main_content:
                main_content = soup.find('main')
            
            # 4. body 태그 찾기
            if not main_content:
                main_content = soup.find('body')
            
            # 5. 최후의 수단으로 전체 soup 사용
            if not main_content:
                main_content = soup
            
            # 텍스트 추출
            text_content = main_content.get_text(separator=' ', strip=True)
            
            # 제목 추출
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""
            
            # (요청에 따라) headings, links는 content에서 제거
            
            # 원복: 메인 콘텐츠만 추출하도록 간소화 (이미지/첨부/댓글/테이블 비활성화)
            images: List[Dict[str, Any]] = []
            structured_tables: List[Dict[str, Any]] = []
            tables_markdown: List[str] = []
            attachments: List[Dict[str, Any]] = []
            comments: List[Dict[str, Any]] = []
            
            # 위에서 파싱한 결과 사용

            # JSON 데이터 구성
            result = {
                'content': {
                    'text': text_content
                },
                'metadata': {
                    'title': title_text,
                    'extracted_at': datetime.now().isoformat(),
                    'content_length': len(text_content),
                    'tables_markdown': tables_markdown,
                    'structured_tables': structured_tables,
                    'images': images,
                    'attachments': attachments,
                    'comments': comments
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"HTML 콘텐츠 추출 중 오류: {e}")
            return {
                'content': {
                    'text': '콘텐츠 추출 중 오류가 발생했습니다.'
                },
                'metadata': {
                    'title': 'Error',
                    'extracted_at': datetime.now().isoformat(),
                    'content_length': 0,
                    'error': str(e),
                    'tables_markdown': [],
                    'images': [],
                    'attachments': [],
                    'comments': []
                }
            }


    def extract_clean_html(self, html_content: str) -> str:
        """exclude 요소 제거 후 main-content 원문 HTML을 그대로 반환"""
        soup = BeautifulSoup(html_content, 'html.parser')
        elements_to_remove = [
            'header', 'footer', 'nav', 'aside', 'sidebar',
            '.header', '.footer', '.nav', '.aside', '.sidebar',
            '.navigation', '.menu', '.breadcrumb',
            'div.aui-page-header-actions', 'div.page-metadata', 'ul.aui-nav-breadcrumbs',
            'div.page-actions', 'div.aui-toolbar2', 'div.comment-container', 'div.like-button-container',
            'div.page-labels', 'div.comment-actions', 'span.st-table-filter', 'svg',
            'div.confluence-information-macro', 'div.aui-message', 'div.page-metadata-modification-info',
            '.aui-page-header-actions', '.page-metadata', '.like-button-container', '.page-labels',
        ]
        for selector in elements_to_remove:
            for el in soup.select(selector):
                el.decompose()

        main_content = soup.find('div', {'id': 'main-content'})
        if not main_content:
            main_content = soup.find('div', {'class': 'wiki-content'})
        if not main_content:
            main_content = soup.find('main') or soup.find('body') or soup

        # main-content 내부 HTML만 반환
        try:
            return main_content.decode_contents() if hasattr(main_content, 'decode_contents') else str(main_content)
        except Exception:
            return str(main_content)

    def _parse_tables(self, root: BeautifulSoup) -> Dict[str, Any]:
        """중첩/병합 테이블을 처리하여 구조화 + 마크다운 생성"""
        structured: List[Dict[str, Any]] = []
        markdowns: List[str] = []

        def extract_text(el) -> str:
            # 줄바꿈 로직 제거 - 원본 텍스트 유지
            text = el.get_text(separator=' ', strip=True) or ''
            return text.strip()

        def limit_text(text: str, limit: int = None) -> str:
            # 내용 생략 문제 해결 - 제한 없이 모든 내용 표시
            return text if text else ""

        def get_table_rows(table_el) -> List[Any]:
            rows: List[Any] = []
            for sec_name in ['thead', 'tbody', 'tfoot']:
                for sec in table_el.find_all(sec_name, recursive=False):
                    rows.extend(sec.find_all('tr', recursive=False))
            rows.extend(table_el.find_all('tr', recursive=False))
            return rows

        def build_grid(table_el) -> Dict[str, Any]:
            rows = get_table_rows(table_el)
            grid: List[List[str]] = []
            span_map: Dict[tuple, Dict[str, int]] = {}
            max_cols = 0
            
            for r_idx, tr in enumerate(rows):
                if len(grid) <= r_idx:
                    grid.append([])
                c_idx = 0
                
                while (r_idx, c_idx) in span_map:
                    grid[r_idx].append('')
                    span_map[(r_idx, c_idx)]['remaining_rowspan'] -= 1
                    if span_map[(r_idx, c_idx)]['remaining_rowspan'] > 0:
                        span_map[(r_idx + 1, c_idx)] = span_map[(r_idx, c_idx)].copy()
                    del span_map[(r_idx, c_idx)]
                    c_idx += 1

                for cell in tr.find_all(['td', 'th'], recursive=False):
                    cell_text = extract_text(cell)
                    rowspan = int(cell.get('rowspan', 1) or 1)
                    colspan = int(cell.get('colspan', 1) or 1)

                    grid[r_idx].append(cell_text)
                    c_idx += 1
                    for _ in range(colspan - 1):
                        grid[r_idx].append('')
                        c_idx += 1

                    if rowspan > 1:
                        for rs in range(1, rowspan):
                            for cs in range(colspan):
                                span_map[(r_idx + rs, (c_idx - colspan) + cs)] = {
                                    'text': cell_text,
                                    'remaining_rowspan': rowspan - rs
                                }
                max_cols = max(max_cols, len(grid[r_idx]))

            for r in grid:
                if len(r) < max_cols:
                    r.extend([''] * (max_cols - len(r)))

            # 빈 열 제거
            col_count = max_cols
            used: List[bool] = [False] * col_count
            for row in grid:
                for idx, val in enumerate(row):
                    if idx < col_count and (val or '').strip():
                        used[idx] = True
            keep_indices = [i for i, u in enumerate(used) if u]
            if keep_indices:
                grid = [[row[i] for i in keep_indices] for row in grid]
                max_cols = len(keep_indices)

            return {'grid': grid, 'cols': max_cols}

        def is_header_cell(cell) -> bool:
            """셀이 헤더인지 판단"""
            # 1. th 태그인 경우
            if cell.name == 'th':
                return True
            
            # 2. td 태그지만 내부에 strong/b 태그가 있는 경우
            if cell.name == 'td':
                # p > strong 또는 직접 strong/b 태그 확인
                strong_tags = cell.find_all(['strong', 'b'])
                if strong_tags:
                    # strong 태그의 텍스트가 셀 전체 텍스트의 대부분을 차지하는지 확인
                    cell_text = extract_text(cell).strip()
                    strong_text = ' '.join(extract_text(tag).strip() for tag in strong_tags)
                    if strong_text and len(strong_text) >= len(cell_text) * 0.7:  # 70% 이상
                        return True
                
                # 3. CSS 클래스 기반 헤더 감지 (Confluence 테이블)
                cell_classes = cell.get('class', [])
                if any('highlight' in str(cls) for cls in cell_classes):  # highlight-grey 등
                    return True
            
            return False

        def detect_headers(table_el, grid_obj) -> Dict[str, Any]:
            header_rows: List[List[str]] = []
            thead = table_el.find('thead')
            
            if thead and thead.find_all('tr'):
                for tr in thead.find_all('tr', recursive=False):
                    if tr.find_all(['th', 'td']):
                        expanded: List[str] = []
                        for cell in tr.find_all(['th', 'td'], recursive=False):
                            txt = extract_text(cell)
                            span = int(cell.get('colspan', 1) or 1)
                            expanded.extend([txt] * max(1, span))
                        header_rows.append(expanded)
            else:
                # 복잡한 테이블 헤더 감지 개선
                body_rows: List[Any] = []
                for tbody in table_el.find_all('tbody', recursive=False):
                    body_rows.extend(tbody.find_all('tr', recursive=False))
                if not body_rows:
                    body_rows = table_el.find_all('tr', recursive=False)
                
                # 상위 2-3행에서 헤더 패턴 찾기
                max_scan = min(3, len(body_rows))
                collected = 0
                
                for i, tr in enumerate(body_rows[:max_scan]):
                    cells = tr.find_all(['th', 'td'], recursive=False)
                    if not cells:
                        continue
                    
                    # 헤더 가능성 체크 - 엄격한 조건만 사용
                    is_likely_header = False
                    
                    # 1. th 태그 또는 strong 태그가 있는 경우
                    if any(is_header_cell(c) for c in cells):
                        is_likely_header = True
                    
                    # 2. rowspan/colspan이 있는 첫 번째 행인 경우 (복잡한 헤더 구조)
                    elif i == 0 and any(  # 첫 번째 행만 체크
                        int(c.get('rowspan', 1) or 1) > 1 or int(c.get('colspan', 1) or 1) > 1 
                        for c in cells
                    ):
                        is_likely_header = True
                    
                    if is_likely_header and collected < 3:  # 최대 3행까지 헤더로 인식
                        expanded: List[str] = []
                        for cell in cells:
                            txt = extract_text(cell).strip()
                            # 빈 셀이나 전각 공백은 빈 문자열로 처리
                            if txt == '　' or not txt:
                                txt = ''
                            span = int(cell.get('colspan', 1) or 1)
                            expanded.extend([txt] * max(1, span))
                        header_rows.append(expanded)
                        collected += 1
                    elif collected > 0:
                        # 헤더 행 이후 일반 데이터 행이 나오면 중단
                        break

            cols = grid_obj['cols']
            
            # 휴리스틱 방법 제거 - thead, th 태그만 사용
            if not header_rows:
                # 헤더가 없으면 기본 컬럼명 생성
                headers = [f"컬럼{i+1}" for i in range(cols)]
                return {'headers': headers, 'header_rows_count': 0}

            # 헤더 행 길이 보정
            norm_rows: List[List[str]] = []
            for row in header_rows:
                row = row[:cols] + [''] * max(0, cols - len(row))
                norm_rows.append(row)

            # 다중 헤더 행 병합 - 계층적 헤더명 생성
            headers = []
            for c in range(cols):
                name_parts = []
                for r in range(len(norm_rows)):
                    if norm_rows[r][c] and norm_rows[r][c].strip():
                        name_parts.append(norm_rows[r][c].strip())
                
                if name_parts:
                    # 중복 제거하면서 계층 구조 유지
                    unique_parts = []
                    for part in name_parts:
                        if part not in unique_parts:
                            unique_parts.append(part)
                    
                    if len(unique_parts) == 1:
                        name = unique_parts[0]
                    else:
                        # 계층적 헤더명: "상위헤더 > 하위헤더"
                        name = ' > '.join(unique_parts)
                else:
                    name = f"컬럼{c+1}"
                
                headers.append(name)
                
            return {'headers': headers, 'header_rows_count': len(norm_rows)}

        def preprocess_markdown_text(text: str) -> str:
            """마크다운 문법 전처리"""
            if not text:
                return text
            
            # 마크다운 특수문자 이스케이프
            text = text.replace('|', '\\|')  # 테이블 구분자
            text = text.replace('*', '\\*')  # 볼드/이탤릭
            text = text.replace('_', '\\_')  # 언더스코어
            text = text.replace('#', '\\#')  # 헤더
            text = text.replace('[', '\\[')  # 링크
            text = text.replace(']', '\\]')  # 링크
            text = text.replace('`', '\\`')  # 코드
            
            return text

        def grid_to_markdown(grid_obj, headers: List[str], header_rows_count: int, title: Optional[str]) -> str:
            lines = []
            if title:
                lines.append(f"### {title}")
                lines.append("")  # 제목 후 빈 줄
                
            # 헤더 - 마크다운 전처리 적용
            processed_headers = [preprocess_markdown_text(h) for h in headers]
            lines.append('|' + '|'.join(processed_headers) + '|')
            lines.append('|' + '|'.join(' --- ' for _ in headers) + '|')
            
            # 데이터 행 - 마크다운 전처리 적용
            data_rows = grid_obj['grid'][header_rows_count if header_rows_count > 0 else 1:]
            for row in data_rows:
                preview_vals = [preprocess_markdown_text(limit_text(str(v))) for v in row[:len(headers)]]
                if all(v.strip() == '' for v in preview_vals):
                    continue
                lines.append('|' + '|'.join(preview_vals) + '|')
            
            lines.append("")  # 테이블 후 빈 줄
            return '\n'.join(lines)

        # 테이블 파싱 실행
        table_index = 0
        for tbl in root.find_all('table'):
            try:
                table_index += 1
                grid_obj = build_grid(tbl)
                header_info = detect_headers(tbl, grid_obj)
                headers = header_info['headers']
                header_rows_count = header_info['header_rows_count']
                
                # 마크다운 생성
                table_name = f"테이블 {table_index}"
                caption = tbl.find('caption')
                if caption:
                    cap = extract_text(caption)
                    if cap:
                        table_name = cap
                        
                markdowns.append(grid_to_markdown(
                    grid_obj, headers, header_rows_count, table_name
                ))
                
            except Exception as e:
                logger.warning(f"Table parse failed at index {table_index}: {e}")
                continue

        return {'structured': structured, 'markdown': markdowns}

    def extract_markdown(self, html_content: str) -> str:
        """하이브리드 방식: 테이블은 기존 로직으로, 나머지는 pymupdf4llm/markdownify로 처리"""
        cleaned_html = self.extract_clean_html(html_content)
        soup = BeautifulSoup(cleaned_html, 'html.parser')
        
        # 1. 테이블을 별도로 파싱하여 마크다운 생성
        table_markdowns = []
        try:
            parsed_tables = self._parse_tables(soup)
            table_markdowns = parsed_tables.get('markdown', [])
        except Exception as e:
            logger.warning(f"Table parsing failed: {e}")
        
        # 2. 테이블을 제거한 HTML에서 나머지 텍스트 추출
        for table in soup.find_all('table'):
            table.decompose()
        
        remaining_html = str(soup)
        
        # 3. 나머지 내용을 마크다운으로 변환
        remaining_markdown = ""
        
        # 3-1. pymupdf4llm 시도
        if pymupdf4llm is not None and remaining_html.strip():
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
                    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body>
    {remaining_html}
</body>
</html>"""
                    temp_html.write(full_html)
                    temp_html_path = temp_html.name
                
                markdown_result = pymupdf4llm.to_markdown(temp_html_path)
                
                try:
                    os.unlink(temp_html_path)
                except:
                    pass
                
                if markdown_result and markdown_result.strip():
                    remaining_markdown = markdown_result
                    
            except Exception as e:
                logger.warning(f"pymupdf4llm conversion failed: {e}")
                try:
                    if 'temp_html_path' in locals():
                        os.unlink(temp_html_path)
                except:
                    pass
        
        # 3-2. markdownify 폴백
        if not remaining_markdown and md_convert is not None:
            try:
                remaining_markdown = md_convert(
                    remaining_html,
                    heading_style="ATX",
                    strip=['style', 'script']
                )
            except Exception as e:
                logger.warning(f"markdownify failed: {e}")
        
        # 3-3. 최종 폴백
        if not remaining_markdown:
            try:
                soup_remaining = BeautifulSoup(remaining_html, 'html.parser')
                remaining_markdown = soup_remaining.get_text('\n', strip=True)
            except Exception:
                remaining_markdown = remaining_html
        
        # 4. 결과 조합 - 테이블 간 적절한 줄바꿈 추가
        result_parts = []
        
        if remaining_markdown.strip():
            result_parts.append(remaining_markdown.strip())
        
        if table_markdowns:
            # 테이블들을 추가하되, 각 테이블 사이에 충분한 간격 확보
            for i, table_md in enumerate(table_markdowns):
                if i > 0:  # 첫 번째 테이블이 아닌 경우
                    result_parts.append("")  # 테이블 간 빈 줄 추가
                result_parts.append(table_md.strip())
        
        return '\n\n'.join(result_parts) if result_parts else ""


# 싱글톤 인스턴스
ari_service = AriService()
