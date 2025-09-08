import json
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List, Set
from datetime import datetime
import os
import html
import re

# PDF 관련 라이브러리는 선택적으로 import
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfutils
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class URLBasedComparator:
    def __init__(self):
        self.changes = {
            'modified': [],     # 수정된 객체들
            'added': [],        # 새로 추가된 객체들
            'removed': [],      # 삭제된 객체들
            'unchanged': 0      # 변경되지 않은 객체 수
        }
        self.stats = {}
        self.javascript_stats = {
            'pages_with_javascript': [],  # javascript가 포함된 페이지들
            'page_count': 0               # javascript가 포함된 페이지 수 (1개 페이지당 1개 카운팅)
        }
        
    def load_json(self, filepath: str) -> Any:
        """JSON 파일을 로드합니다. UTF-8 BOM을 자동으로 처리합니다."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except FileNotFoundError:
            error_msg = f"오류: 파일 '{filepath}'를 찾을 수 없습니다."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        except json.JSONDecodeError as e:
            error_msg = f"오류: '{filepath}' 파일의 JSON 형식이 올바르지 않습니다. 상세 오류: {e}"
            logger.error(error_msg)
            if "BOM" in str(e):
                logger.info("힌트: 파일에 UTF-8 BOM이 포함되어 있을 수 있습니다.")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"오류: 파일을 읽는 중 문제가 발생했습니다. {e}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def create_object_key(self, obj: Dict[str, Any]) -> str:
        """객체의 유니크 키를 생성합니다 (url + hierarchy 조합)."""
        if not isinstance(obj, dict):
            return str(hash(str(obj)))
        
        url = obj.get('url', '')
        hierarchy = obj.get('hierarchy', [])
        
        # hierarchy를 정렬된 문자열로 변환 (리스트 또는 딕셔너리 모두 지원)
        if isinstance(hierarchy, list):
            hierarchy_str = json.dumps(hierarchy, sort_keys=True) if hierarchy else ''
        elif isinstance(hierarchy, dict):
            hierarchy_str = json.dumps(hierarchy, sort_keys=True) if hierarchy else ''
        else:
            hierarchy_str = str(hierarchy) if hierarchy else ''
        
        return f"{url}|{hierarchy_str}"
    
    def clean_metadata_for_comparison(self, metadata: Any) -> Any:
        """비교용으로 metadata를 정리합니다 (changes 필드만 제거)."""
        if isinstance(metadata, dict):
            cleaned = {}
            for key, value in metadata.items():
                if key != 'changes':
                    cleaned[key] = value
            return cleaned
        return metadata
    
    def normalize_for_comparison(self, value: Any) -> Any:
        """비교를 위한 정규화: 문자열 공백, 개행, 유니코드 정규화."""
        import unicodedata
        import re
        
        if isinstance(value, str):
            # 유니코드 정규화 (NFC 형식으로 통일)
            normalized = unicodedata.normalize('NFC', value)
            # 연속된 공백을 하나로 통일
            normalized = re.sub(r'\s+', ' ', normalized)
            # 앞뒤 공백 제거
            normalized = normalized.strip()
            return normalized
        elif isinstance(value, dict):
            # 딕셔너리의 모든 값을 재귀적으로 정규화
            return {k: self.normalize_for_comparison(v) for k, v in value.items()}
        elif isinstance(value, list):
            # 리스트의 모든 요소를 재귀적으로 정규화
            return [self.normalize_for_comparison(item) for item in value]
        else:
            return value
    
    def deep_compare_metadata(self, old_metadata: Any, new_metadata: Any) -> bool:
        """metadata를 깊은 비교로 확인합니다."""
        # 먼저 직접 비교
        if old_metadata == new_metadata:
            return True
        
        # 둘 다 None이거나 하나만 None인 경우
        if old_metadata is None or new_metadata is None:
            return old_metadata == new_metadata
        
        # 정규화하여 비교
        try:
            old_normalized = self.normalize_for_comparison(old_metadata)
            new_normalized = self.normalize_for_comparison(new_metadata)
            
            # 정규화된 값으로 직접 비교
            if old_normalized == new_normalized:
                return True
            
            # JSON 문자열로 변환하여 비교 (키 순서 통일)
            old_json = json.dumps(old_normalized, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            new_json = json.dumps(new_normalized, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            
            return old_json == new_json
            
        except (TypeError, ValueError) as e:
            # JSON 변환 실패 시 디버깅 정보 출력 후 직접 비교
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"JSON 변환 실패: {e}")
            logger.debug(f"old_metadata type: {type(old_metadata)}")
            logger.debug(f"new_metadata type: {type(new_metadata)}")
            return old_metadata == new_metadata
    
    def create_object_mapping(self, data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """객체 키를 기반으로 매핑을 생성합니다."""
        import logging
        logger = logging.getLogger(__name__)
        
        mapping = {}
        for item in data:
            if isinstance(item, dict):
                key = self.create_object_key(item)
                if key in mapping:
                    logger.warning(f"중복 키 발견: {key[:100]}...")
                mapping[key] = item
            else:
                logger.warning(f"dict가 아닌 객체 발견: {str(item)[:100]}...")
        return mapping
    
    def format_hierarchy_for_display(self, hierarchy: Any) -> str:
        """hierarchy를 읽기 쉬운 형태로 포맷팅합니다."""
        if not hierarchy:
            return "(경로 없음)"
        
        # 리스트인 경우 (새로운 구조)
        if isinstance(hierarchy, list):
            return " > ".join([str(item) for item in hierarchy])
        
        # 딕셔너리인 경우 (기존 구조)
        elif isinstance(hierarchy, dict):
            # depth1 > depth2 > depth3 형태로 표시
            path_parts = []
            for i in range(1, 10):  # depth1부터 depth9까지 확인
                depth_key = f"depth{i}"
                if depth_key in hierarchy:
                    path_parts.append(hierarchy[depth_key])
                else:
                    break
            
            return " > ".join(path_parts) if path_parts else "(경로 없음)"
        
        # 기타 타입인 경우
        else:
            return str(hierarchy)
    
    def format_value_for_display(self, value: Any, max_length: int = 120) -> str:
        """값을 리포트 출력용으로 포맷팅합니다."""
        if isinstance(value, str):
            formatted = value.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
            if len(formatted) > max_length:
                formatted = formatted[:max_length] + "..."
            return formatted
        elif isinstance(value, (list, dict)):
            str_val = str(value)
            if len(str_val) > max_length:
                return str_val[:max_length] + "..."
            return str_val
        else:
            return str(value)
    
    def get_change_summary(self, old_val: Any, new_val: Any) -> str:
        """값의 변화를 요약해서 반환합니다."""
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            diff = new_val - old_val
            if old_val != 0:
                percent = (diff / old_val) * 100
                return f"{old_val} → {new_val} (변화: {diff:+}, {percent:+.1f}%)"
            else:
                return f"{old_val} → {new_val} (변화: {diff:+})"
        
        old_formatted = self.format_value_for_display(old_val, 60)
        new_formatted = self.format_value_for_display(new_val, 60)
        return f"'{old_formatted}' → '{new_formatted}'"
    
    def has_javascript_in_text(self, text: str) -> bool:
        """text 필드에서 'javascript' 문구가 있는지 확인합니다 (대소문자 구분 없음)."""
        if not isinstance(text, str):
            return False
        
        # 대소문자 구분 없이 'javascript' 검출
        text_lower = text.lower()
        return 'javascript' in text_lower
    
    def analyze_javascript_in_page(self, page_obj: Dict[str, Any]) -> Dict[str, Any]:
        """페이지 객체에서 javascript 관련 정보를 분석합니다."""
        text = page_obj.get('text', '')
        has_js = self.has_javascript_in_text(text)
        
        if has_js:
            return {
                'url': page_obj.get('url', ''),
                'title': page_obj.get('title', '제목 없음'),
                'hierarchy': page_obj.get('hierarchy', {}),
                'text_preview': text[:200] + ("..." if len(text) > 200 else "")
            }
        return None
    
    def find_metadata_subfield_changes(self, old_metadata: Dict[str, Any], new_metadata: Dict[str, Any], obj_key: str) -> List[Dict[str, Any]]:
        """metadata 내부의 세부 필드별 변경사항을 찾습니다."""
        changes = []
        
        if not isinstance(old_metadata, dict) or not isinstance(new_metadata, dict):
            return changes
        
        # metadata의 모든 키를 확인
        all_keys = set(old_metadata.keys()) | set(new_metadata.keys())
        
        for key in all_keys:
            if key == 'changes' or key != '페이지 내용':  # changes 필드와 페이지 내용이 아닌 필드는 제외
                continue
                
            old_value = old_metadata.get(key)
            new_value = new_metadata.get(key)
            
            # 정규화하여 비교
            old_normalized = self.normalize_for_comparison(old_value)
            new_normalized = self.normalize_for_comparison(new_value)
            
            if old_normalized != new_normalized:
                if old_value is None:
                    changes.append({
                        'type': 'metadata_subfield_added',
                        'field': f'metadata.{key}',
                        'subfield': key,
                        'value': new_value,
                        'object_key': obj_key
                    })
                elif new_value is None:
                    changes.append({
                        'type': 'metadata_subfield_removed',
                        'field': f'metadata.{key}',
                        'subfield': key,
                        'value': old_value,
                        'object_key': obj_key
                    })
                else:
                    # 배열이나 복잡한 구조의 경우 더 세부적으로 분석
                    if key == 'images' and isinstance(old_value, list) and isinstance(new_value, list):
                        # images 배열의 개별 변경사항 추적
                        image_changes = self.find_array_changes(old_value, new_value, f'metadata.{key}', obj_key)
                        changes.extend(image_changes)
                    elif key == 'internal_urls' and isinstance(old_value, list) and isinstance(new_value, list):
                        # internal_urls 배열의 개별 변경사항 추적
                        url_changes = self.find_array_changes(old_value, new_value, f'metadata.{key}', obj_key)
                        changes.extend(url_changes)
                    elif key == 'urls' and isinstance(old_value, list) and isinstance(new_value, list):
                        # urls 배열의 개별 변경사항 추적
                        url_changes = self.find_array_changes(old_value, new_value, f'metadata.{key}', obj_key)
                        changes.extend(url_changes)
                    else:
                        changes.append({
                            'type': 'metadata_subfield_modified',
                            'field': f'metadata.{key}',
                            'subfield': key,
                            'old_value': old_value,
                            'new_value': new_value,
                            'object_key': obj_key
                        })
        
        return changes
    
    def find_array_changes(self, old_array: List[Any], new_array: List[Any], field_name: str, obj_key: str) -> List[Dict[str, Any]]:
        """배열의 개별 요소 변경사항을 찾습니다."""
        changes = []
        
        # 길이가 다른 경우
        if len(old_array) != len(new_array):
            changes.append({
                'type': 'array_size_changed',
                'field': field_name,
                'old_size': len(old_array),
                'new_size': len(new_array),
                'object_key': obj_key
            })
        
        # 공통 요소들 비교
        min_len = min(len(old_array), len(new_array))
        for i in range(min_len):
            old_item = old_array[i]
            new_item = new_array[i]
            
            old_normalized = self.normalize_for_comparison(old_item)
            new_normalized = self.normalize_for_comparison(new_item)
            
            if old_normalized != new_normalized:
                changes.append({
                    'type': 'array_item_modified',
                    'field': f'{field_name}[{i}]',
                    'index': i,
                    'old_value': old_item,
                    'new_value': new_item,
                    'object_key': obj_key
                })
        
        return changes

    def find_object_changes(self, old_obj: Dict[str, Any], new_obj: Dict[str, Any], obj_key: str) -> List[Dict[str, Any]]:
        """두 객체 간의 세부 변경사항을 찾습니다 (특정 필드만 비교)."""
        changes = []
        
        # 비교할 필드들 정의 (text와 murl 필드만 비교)
        compare_fields = ['text', 'murl']
        
        for field in compare_fields:
            old_value = old_obj.get(field)
            new_value = new_obj.get(field)
            
            # metadata는 특별 처리 (changes 필드 제외)
            if field == 'metadata':
                old_cleaned = self.clean_metadata_for_comparison(old_value)
                new_cleaned = self.clean_metadata_for_comparison(new_value)
                # metadata는 직접 비교 먼저 시도
                if old_cleaned == new_cleaned:
                    is_different = False
                else:
                    # 깊은 비교 사용
                    is_different = not self.deep_compare_metadata(old_cleaned, new_cleaned)
                
                # metadata가 다른 경우 세부 필드별 분석
                if is_different:
                    metadata_changes = self.find_metadata_subfield_changes(old_cleaned, new_cleaned, obj_key)
                    changes.extend(metadata_changes)
            else:
                # 다른 필드들도 정규화하여 비교
                old_cleaned = self.normalize_for_comparison(old_value)
                new_cleaned = self.normalize_for_comparison(new_value)
                is_different = old_cleaned != new_cleaned
                
                # 정규화된 값으로 비교
                if is_different:
                    if old_cleaned is None:
                        changes.append({
                            'type': 'field_added',
                            'field': field,
                            'value': new_value,  # 원본 값 저장
                            'object_key': obj_key
                        })
                    elif new_cleaned is None:
                        changes.append({
                            'type': 'field_removed',
                            'field': field,
                            'value': old_value,  # 원본 값 저장
                            'object_key': obj_key
                        })
                    else:
                        changes.append({
                            'type': 'field_modified',
                            'field': field,
                            'old_value': old_value,  # 원본 값 저장
                            'new_value': new_value,  # 원본 값 저장
                            'object_key': obj_key
                        })
        
        return changes
    
    def compare_json(self, file1: str, file2: str, file1_name: str = None, file2_name: str = None) -> Dict[str, Any]:
        """두 JSON 파일을 URL 기반으로 비교합니다."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("JSON 파일 로딩 중...")
        data1 = self.load_json(file1)
        data2 = self.load_json(file2)
        
        logger.info(f"파일 로딩 완료")
        logger.info(f"   - 파일1: {len(str(data1)):,} characters")
        logger.info(f"   - 파일2: {len(str(data2)):,} characters")
        
        if not isinstance(data1, list) or not isinstance(data2, list):
            error_msg = "오류: JSON 파일의 최상위는 배열이어야 합니다."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"객체 키 기반 매핑 생성 중...")
        logger.info(f"   - 이전 파일: {len(data1):,}개 객체")
        logger.info(f"   - 현재 파일: {len(data2):,}개 객체")
        
        # 객체 키 기반 매핑 생성 (url + hierarchy)
        old_mapping = self.create_object_mapping(data1)
        new_mapping = self.create_object_mapping(data2)
        
        logger.info(f"   - 이전 파일 유효 객체: {len(old_mapping):,}개")
        logger.info(f"   - 현재 파일 유효 객체: {len(new_mapping):,}개")
        
        old_keys = set(old_mapping.keys())
        new_keys = set(new_mapping.keys())
        
        logger.info("객체 변경사항 분석 중...")
        
        # 삭제된 객체들
        removed_keys = old_keys - new_keys
        for obj_key in removed_keys:
            obj = old_mapping[obj_key]
            self.changes['removed'].append({
                'object_key': obj_key,
                'url': obj.get('url', ''),
                'object': obj
            })
        
        # 추가된 객체들
        added_keys = new_keys - old_keys
        for obj_key in added_keys:
            obj = new_mapping[obj_key]
            self.changes['added'].append({
                'object_key': obj_key,
                'url': obj.get('url', ''),
                'object': obj
            })
        
        # 공통 객체들 - 변경사항 확인 (murl, title, text, metadata만 비교)
        common_keys = old_keys & new_keys
        modified_count = 0
        
        for obj_key in common_keys:
            old_obj = old_mapping[obj_key]
            new_obj = new_mapping[obj_key]
            
            # 특정 필드만 비교해서 변경 여부 확인
            field_changes = self.find_object_changes(old_obj, new_obj, obj_key)
            
            if field_changes:
                # 변경된 객체
                self.changes['modified'].append({
                    'object_key': obj_key,
                    'url': old_obj.get('url', ''),
                    'old_object': old_obj,
                    'new_object': new_obj,
                    'field_changes': field_changes
                })
                modified_count += 1
                
                # 디버깅: 변경된 필드 정보 출력
                if modified_count <= 3:  # 처음 3개만 출력
                    logger.debug(f"  변경 감지: {obj_key[:50]}...")
                    for change in field_changes:
                        logger.debug(f"    - {change['field']}: {change['type']}")
                        if change['type'] == 'field_modified':
                            old_val = str(change['old_value'])[:100]
                            new_val = str(change['new_value'])[:100]
                            logger.debug(f"      이전: {old_val}...")
                            logger.debug(f"      현재: {new_val}...")
            else:
                self.changes['unchanged'] += 1
        
        # JavaScript 검출 분석
        logger.info("JavaScript 문구 검출 중...")
        all_pages = list(new_mapping.values())  # 현재 파일의 모든 페이지
        for page in all_pages:
            js_info = self.analyze_javascript_in_page(page)
            if js_info:
                self.javascript_stats['pages_with_javascript'].append(js_info)
        
        self.javascript_stats['page_count'] = len(self.javascript_stats['pages_with_javascript'])
        
        logger.info(f"분석 완료!")
        logger.info(f"   - 삭제된 객체: {len(removed_keys):,}개")
        logger.info(f"   - 추가된 객체: {len(added_keys):,}개")
        logger.info(f"   - 수정된 객체: {modified_count:,}개")
        logger.info(f"   - 변경없는 객체: {self.changes['unchanged']:,}개")
        logger.info(f"   - JavaScript 검출: {self.javascript_stats['page_count']:,}개 페이지")
        
        # 통계 생성
        stats = {
            'file1': file1_name if file1_name else Path(file1).name,
            'file2': file2_name if file2_name else Path(file2).name,
            'total_objects_1': len(old_mapping),
            'total_objects_2': len(new_mapping),
            'objects_removed': len(removed_keys),
            'objects_added': len(added_keys),
            'objects_modified': modified_count,
            'objects_unchanged': self.changes['unchanged'],
            'total_changes': len(removed_keys) + len(added_keys) + modified_count,
            'javascript_pages': self.javascript_stats['page_count']
        }
        
        self.stats = stats
        return stats
    
    def _setup_korean_font(self) -> str:
        """크로스 플랫폼 한글 폰트를 설정합니다."""
        import platform
        import urllib.request
        import logging
        logger = logging.getLogger(__name__)
        
        # fonts 폴더 생성 - 로컬 fonts 폴더와 프로젝트 루트 fonts 폴더 모두 확인
        local_fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        project_fonts_dir = os.path.join(project_root, 'fonts')
        
        # 로컬 fonts 폴더가 있으면 우선 사용, 없으면 프로젝트 루트 사용
        if os.path.exists(local_fonts_dir):
            fonts_dir = local_fonts_dir
        else:
            fonts_dir = project_fonts_dir
            os.makedirs(fonts_dir, exist_ok=True)
        
        # 한글 폰트 파일 경로들
        korean_font = None
        font_found = False
        
        logger.info("한글 폰트 설정 중...")
        
        # 1. 먼저 fonts 폴더의 폰트들 시도
        local_fonts = [
            (os.path.join(fonts_dir, 'NotoSansKR-Regular.ttf'), 'Noto Sans KR Regular'),
            (os.path.join(fonts_dir, 'NotoSansKR-Medium.ttf'), 'Noto Sans KR Medium'),
            (os.path.join(fonts_dir, 'NotoSansKR-Bold.ttf'), 'Noto Sans KR Bold'),
            (os.path.join(fonts_dir, 'NotoSansCJK-Regular.ttc'), 'Noto Sans CJK'),
            (os.path.join(fonts_dir, 'malgun.ttf'), '맑은 고딕')
        ]
        
        for font_path, font_name in local_fonts:
            if os.path.exists(font_path):
                try:
                    if font_path.endswith('.ttc'):
                        pdfmetrics.registerFont(TTFont('KoreanFont', font_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                    korean_font = 'KoreanFont'
                    logger.info(f"로컬 한글 폰트 등록 성공: {font_name}")
                    font_found = True
                    break
                except Exception as e:
                    logger.warning(f"로컬 폰트 등록 실패 ({font_name}): {e}")
                    continue
        
        # 2. 시스템 폰트 시도 (플랫폼별)
        if not font_found:
            system_font_paths = []
            system_name = platform.system().lower()
            
            if system_name == 'darwin':  # macOS
                system_font_paths = [
                    '/System/Library/Fonts/LucidaGrande.ttc',
                    '/Library/Fonts/Arial Unicode MS.ttf',
                    '/System/Library/Fonts/Arial Unicode MS.ttf',
                    '/System/Library/Fonts/AppleGothic.ttf',
                    '/System/Library/Fonts/Times.ttc',
                    '/System/Library/Fonts/AppleSDGothicNeo.ttc',  # 한글 전용 폰트
                ]
            elif system_name == 'windows':  # Windows
                system_font_paths = [
                    'C:/Windows/Fonts/malgun.ttf',  # 맑은 고딕
                    'C:/Windows/Fonts/gulim.ttc',   # 굴림
                    'C:/Windows/Fonts/batang.ttc',  # 바탕
                    'C:/Windows/Fonts/arial.ttf',   # Arial
                ]
            else:  # Linux
                system_font_paths = [
                    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                ]
            
            for font_path in system_font_paths:
                if os.path.exists(font_path):
                    try:
                        if font_path.endswith('.ttc'):
                            pdfmetrics.registerFont(TTFont('KoreanFont', font_path, subfontIndex=0))
                        else:
                            pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                        korean_font = 'KoreanFont'
                        logger.info(f"시스템 폰트 등록 성공: {os.path.basename(font_path)}")
                        font_found = True
                        break
                    except Exception as e:
                        logger.warning(f"시스템 폰트 등록 실패 ({os.path.basename(font_path)}): {e}")
                        continue
        
        # 3. Noto Sans KR 폰트 다운로드 시도 (GitHub Raw에서)
        if not font_found:
            try:
                logger.info("Noto Sans KR 폰트를 다운로드하는 중...")
                noto_kr_url = "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"
                noto_kr_path = os.path.join(fonts_dir, 'NotoSansKR-Regular.ttf')
                
                urllib.request.urlretrieve(noto_kr_url, noto_kr_path)
                logger.info("Noto Sans KR 폰트 다운로드 완료")
                
                pdfmetrics.registerFont(TTFont('KoreanFont', noto_kr_path))
                korean_font = 'KoreanFont'
                logger.info("Noto Sans KR 폰트 등록 성공")
                font_found = True
                
            except Exception as download_error:
                logger.warning(f"폰트 다운로드 실패: {download_error}")
                logger.warning("수동으로 한글 폰트를 fonts/ 폴더에 추가해주세요.")
        
        # 4. CID 폰트 시도 (일본어 폰트로 한글 지원)
        if not font_found:
            try:
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                cid_fonts = ['HeiseiKakuGo-W5', 'HeiseiMin-W3']
                for cid_font in cid_fonts:
                    try:
                        pdfmetrics.registerFont(UnicodeCIDFont(cid_font))
                        korean_font = cid_font
                        logger.info(f"CID 폰트 등록 성공: {cid_font}")
                        font_found = True
                        break
                    except:
                        continue
            except:
                pass
        
        # 5. 마지막 수단: 기본 폰트
        if not font_found:
            korean_font = 'Helvetica'
            logger.warning("경고: 한글 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
            logger.warning("한글이 깨져 보일 수 있습니다.")
        
        return korean_font
    
    def decode_html_entities(self, text: str) -> str:
        """HTML 엔티티를 실제 문자로 변환하고 HTML 태그를 제거합니다."""
        if not isinstance(text, str):
            return text
        
        # HTML 태그 제거
        text = self.clean_html_tags(text)
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        return text
    
    def clean_html_tags(self, text: str) -> str:
        """HTML 태그를 제거하고 안전한 텍스트로 변환합니다."""
        if not isinstance(text, str):
            return text
        
        # HTML 태그 제거 (복잡한 태그들 포함)
        text = re.sub(r'<[^>]+>', '', text)
        
        # 연속된 공백 및 줄바꿈 정리
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def escape_for_paragraph(self, text: str) -> str:
        """Paragraph에서 안전하게 표시될 수 있도록 텍스트를 이스케이프합니다."""
        if not isinstance(text, str):
            return text
        
        # 먼저 HTML 태그 제거
        text = self.clean_html_tags(text)
        
        # HTML 엔티티 디코딩
        text = html.unescape(text)
        
        # reportlab Paragraph에서 & 문자를 올바르게 처리하기 위해 &amp;로 변환
        text = text.replace('&', '&amp;')
        
        # 기타 특수문자 처리
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        return text
    
    def create_link_button(self, url: str) -> str:
        """URL을 위한 간단한 클릭 가능한 링크 버튼을 생성합니다."""
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            return "N/A"
        
        escaped_url = self.escape_for_paragraph(url)
        # 간단한 "링크" 버튼 형태
        return f'<link href="{escaped_url}">🔗 바로가기</link>'

    def generate_pdf_report(self, summary: Dict[str, Any], output_file: str, empty_url_items: List[Dict[str, Any]] = None) -> None:
        """비교 결과를 PDF 파일로 생성합니다."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab 라이브러리가 설치되지 않았습니다. 'pip install reportlab'을 실행하세요.")
        
        logger.info("PDF 리포트 생성 중...")
        
        # 한글 폰트 등록 (크로스 플랫폼 지원)
        korean_font = self._setup_korean_font()
        logger.info(f"사용할 폰트: {korean_font}")
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            output_file,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        
        # 커스텀 스타일 정의 (한글 폰트 적용)
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=korean_font,
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=korean_font,
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontName=korean_font,
            fontSize=12,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.darkgreen
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=korean_font,
            fontSize=10,
            spaceAfter=6
        )
        
        # 문서 내용 생성
        story = []
        
        # 제목
        story.append(Paragraph("웹사이트 변경사항 분석 리포트", title_style))
        story.append(Paragraph("(Website Change Analysis Report)", title_style))
        story.append(Spacer(1, 20))
            
            # 리포트 정보
        story.append(Paragraph("■ 리포트 생성 정보", heading_style))
        
        report_info = [
            ["생성 일시", datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분")],
            ["분석 기준", "URL + 페이지 계층구조 기반 객체 단위 비교"],
            ["비교 범위", "페이지 제목, 텍스트 내용, 메타데이터 (변경 이력 제외)"]
        ]
        
        info_table = Table(report_info, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), korean_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
            
            # 분석 대상 파일
        story.append(Paragraph("■ 분석 대상 파일", heading_style))
        
        file_info = [
            ["기준 파일", summary["file1"]],
            ["비교 파일", summary["file2"]]
        ]
        
        file_table = Table(file_info, colWidths=[2*inch, 4*inch])
        file_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), korean_font),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(file_table)
        story.append(Spacer(1, 20))
            
            # 분석 결과 요약
        story.append(Paragraph("■ 분석 결과 요약", heading_style))
        
        summary_data = [
            ["구분", "개수", "비율"],
            ["기준 파일 총 페이지 수", f"{summary['total_objects_1']:,}개", "100.0%"],
            ["비교 파일 총 페이지 수", f"{summary['total_objects_2']:,}개", f"{(summary['total_objects_2']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"],
            ["변경사항 없는 페이지", f"{summary['objects_unchanged']:,}개", f"{(summary['objects_unchanged']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"],
            ["변경사항 있는 페이지", f"{summary['total_changes']:,}개", f"{(summary['total_changes']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"],
            ["JavaScript 검출 페이지", f"{summary['javascript_pages']:,}개", f"{(summary['javascript_pages']/summary['total_objects_2']*100):,.1f}%" if summary['total_objects_2'] > 0 else "N/A"]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), korean_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), korean_font),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
            
            # 변경 유형별 상세 통계
        story.append(Paragraph("■ 변경 유형별 상세 통계", heading_style))
        
        change_data = [
            ["변경 유형", "개수", "전체 대비 비율"],
            ["신규 추가된 페이지", f"{summary['objects_added']:,}개", f"{(summary['objects_added']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"],
            ["삭제된 페이지", f"{summary['objects_removed']:,}개", f"{(summary['objects_removed']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"],
            ["내용이 수정된 페이지", f"{summary['objects_modified']:,}개", f"{(summary['objects_modified']/summary['total_objects_1']*100):,.1f}%" if summary['total_objects_1'] > 0 else "N/A"]
        ]
        
        change_table = Table(change_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        change_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), korean_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), korean_font),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(change_table)
        
        if summary['total_changes'] == 0:
            story.append(Spacer(1, 20))
            no_changes = Paragraph("※ 두 파일 간 변경사항이 발견되지 않았습니다.", normal_style)
            story.append(no_changes)
        
        story.append(PageBreak())
        
        # 상세 변경사항 목록
        story.append(Paragraph("상세 변경사항 목록", title_style))
        story.append(Spacer(1, 20))
        
        # 변경사항이 있는 경우에만 상세 목록 생성
        if summary['total_changes'] > 0:
            # 삭제된 페이지 (전체 표시)
            if len(self.changes['removed']) > 0:
                story.append(Paragraph(f"■ 삭제된 페이지 (총 {len(self.changes['removed'])}개)", heading_style))
                
                removed_data = [["URL", "페이지 제목", "페이지 경로", "링크"]]
                for change in self.changes['removed']:  # 모든 삭제된 페이지 표시
                    title = self.decode_html_entities(change['object'].get('title', '제목 없음'))
                    hierarchy = self.decode_html_entities(self.format_hierarchy_for_display(change['object'].get('hierarchy', {})))
                    url = self.decode_html_entities(change['url'])
                    
                    # Paragraph로 감싸서 자동 줄바꿈 적용
                    url_para = Paragraph(self.escape_for_paragraph(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                    title_para = Paragraph(self.escape_for_paragraph(title), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    hierarchy_para = Paragraph(self.escape_for_paragraph(hierarchy), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    link_para = Paragraph(self.create_link_button(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    
                    removed_data.append([url_para, title_para, hierarchy_para, link_para])
                
                removed_table = Table(removed_data, colWidths=[2.0*inch, 1.8*inch, 1.4*inch, 0.8*inch], repeatRows=1)
                removed_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.red),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), korean_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.mistyrose),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('WORDWRAP', (0, 0), (-1, -1), 'LTR')
                ]))
                
                story.append(removed_table)
                story.append(Spacer(1, 15))
            
            # 추가된 페이지 (전체 표시)
            if len(self.changes['added']) > 0:
                story.append(Paragraph(f"■ 추가된 페이지 (총 {len(self.changes['added'])}개)", heading_style))
                
                added_data = [["URL", "페이지 제목", "페이지 경로", "링크"]]
                for change in self.changes['added']:  # 모든 추가된 페이지 표시
                    title = self.decode_html_entities(change['object'].get('title', '제목 없음'))
                    hierarchy = self.decode_html_entities(self.format_hierarchy_for_display(change['object'].get('hierarchy', {})))
                    url = self.decode_html_entities(change['url'])
                    
                    # Paragraph로 감싸서 자동 줄바꿈 적용
                    url_para = Paragraph(self.escape_for_paragraph(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                    title_para = Paragraph(self.escape_for_paragraph(title), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    hierarchy_para = Paragraph(self.escape_for_paragraph(hierarchy), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    link_para = Paragraph(self.create_link_button(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=7, fontName=korean_font))
                    
                    added_data.append([url_para, title_para, hierarchy_para, link_para])
                
                added_table = Table(added_data, colWidths=[2.0*inch, 1.8*inch, 1.4*inch, 0.8*inch], repeatRows=1)
                added_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.green),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), korean_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('WORDWRAP', (0, 0), (-1, -1), 'LTR')
                ]))
                
                story.append(added_table)
                story.append(Spacer(1, 15))
            
            # 수정된 페이지 (전체 상세 표시)
            if len(self.changes['modified']) > 0:
                story.append(Paragraph(f"■ 수정된 페이지 (총 {len(self.changes['modified'])}개)", heading_style))
                
                modified_data = [["URL", "페이지 경로", "변경 필드", "변경 전", "변경 후", "링크"]]
                
                for change in self.changes['modified']:  # 모든 수정된 페이지 표시
                    url = self.decode_html_entities(change['url'])
                    hierarchy = self.decode_html_entities(self.format_hierarchy_for_display(change['new_object'].get('hierarchy', {})))
                    
                    # 각 필드 변경사항을 별도 행으로 표시
                    for field_change in change['field_changes']:
                        field_name = ""
                        old_value = ""
                        new_value = ""
                        
                        if field_change['type'] == 'field_modified':
                            field_display_name = {
                                'text': '페이지 내용',
                                'murl': '모바일 URL'
                            }.get(field_change['field'], field_change['field'])
                            
                            field_name = field_display_name
                            old_value = self.decode_html_entities(str(field_change['old_value'])[:200] + ("..." if len(str(field_change['old_value'])) > 200 else ""))
                            new_value = self.decode_html_entities(str(field_change['new_value'])[:200] + ("..." if len(str(field_change['new_value'])) > 200 else ""))
                            
                        elif field_change['type'] == 'field_added':
                            field_display_name = {
                                'text': '페이지 내용',
                                'murl': '모바일 URL'
                            }.get(field_change['field'], field_change['field'])
                            
                            field_name = f"{field_display_name} (신규)"
                            old_value = "(없음)"
                            new_value = self.decode_html_entities(str(field_change['value'])[:200] + ("..." if len(str(field_change['value'])) > 200 else ""))
                            
                        elif field_change['type'] == 'field_removed':
                            field_display_name = {
                                'murl': '모바일 URL',
                                'title': '페이지 제목',
                                'text': '페이지 내용',
                                'metadata': '메타데이터'
                            }.get(field_change['field'], field_change['field'])
                            
                            field_name = f"{field_display_name} (삭제)"
                            old_value = self.decode_html_entities(str(field_change['value'])[:200] + ("..." if len(str(field_change['value'])) > 200 else ""))
                            new_value = "(삭제됨)"
                            
                        elif field_change['type'] == 'metadata_subfield_modified':
                            subfield_display_name = {
                                'images': '이미지 정보',
                                'internal_urls': '내부 링크',
                                'external_urls': '외부 링크',
                                'forms': '폼 요소',
                                'scripts': '스크립트'
                            }.get(field_change['subfield'], field_change['subfield'])
                            
                            field_name = f"메타데이터.{subfield_display_name}"
                            old_value = self.decode_html_entities(str(field_change['old_value'])[:200] + ("..." if len(str(field_change['old_value'])) > 200 else ""))
                            new_value = self.decode_html_entities(str(field_change['new_value'])[:200] + ("..." if len(str(field_change['new_value'])) > 200 else ""))
                            
                        elif field_change['type'] == 'metadata_subfield_added':
                            subfield_display_name = {
                                'images': '이미지 정보',
                                'internal_urls': '내부 링크',
                                'external_urls': '외부 링크',
                                'forms': '폼 요소',
                                'scripts': '스크립트'
                            }.get(field_change['subfield'], field_change['subfield'])
                            
                            field_name = f"메타데이터.{subfield_display_name} (신규)"
                            old_value = "(없음)"
                            new_value = self.decode_html_entities(str(field_change['value'])[:200] + ("..." if len(str(field_change['value'])) > 200 else ""))
                            
                        elif field_change['type'] == 'metadata_subfield_removed':
                            subfield_display_name = {
                                'images': '이미지 정보',
                                'internal_urls': '내부 링크',
                                'external_urls': '외부 링크',
                                'forms': '폼 요소',
                                'scripts': '스크립트'
                            }.get(field_change['subfield'], field_change['subfield'])
                            
                            field_name = f"메타데이터.{subfield_display_name} (삭제)"
                            old_value = self.decode_html_entities(str(field_change['value'])[:200] + ("..." if len(str(field_change['value'])) > 200 else ""))
                            new_value = "(삭제됨)"
                            
                        elif field_change['type'] == 'array_size_changed':
                            field_parts = field_change['field'].split('.')
                            field_name_raw = field_parts[-1] if len(field_parts) > 1 else field_change['field']
                            display_name = {
                                'images': '이미지 목록',
                                'internal_urls': '내부 링크 목록',
                                'external_urls': '외부 링크 목록'
                            }.get(field_name_raw, field_name_raw)
                            
                            field_name = f"{display_name} (크기 변경)"
                            old_value = f"{field_change['old_size']}개"
                            new_value = f"{field_change['new_size']}개"
                            
                        elif field_change['type'] == 'array_item_modified':
                            field_parts = field_change['field'].split('.')
                            field_name_raw = field_parts[-1].split('[')[0] if len(field_parts) > 1 else field_change['field'].split('[')[0]
                            display_name = {
                                'images': '이미지',
                                'internal_urls': '내부 링크',
                                'external_urls': '외부 링크'
                            }.get(field_name_raw, field_name_raw)
                            
                            field_name = f"{display_name} #{field_change['index']+1}"
                            old_value = self.decode_html_entities(str(field_change['old_value'])[:200] + ("..." if len(str(field_change['old_value'])) > 200 else ""))
                            new_value = self.decode_html_entities(str(field_change['new_value'])[:200] + ("..." if len(str(field_change['new_value'])) > 200 else ""))
                        
                        # Paragraph로 감싸서 자동 줄바꿈 적용
                        url_para = Paragraph(self.escape_for_paragraph(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=5, fontName=korean_font))
                        hierarchy_para = Paragraph(self.escape_for_paragraph(hierarchy), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                        field_para = Paragraph(self.escape_for_paragraph(field_name), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                        old_para = Paragraph(self.escape_for_paragraph(old_value), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                        new_para = Paragraph(self.escape_for_paragraph(new_value), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                        link_para = Paragraph(self.create_link_button(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                        
                        modified_data.append([url_para, hierarchy_para, field_para, old_para, new_para, link_para])
                
                modified_table = Table(modified_data, colWidths=[1.2*inch, 1.0*inch, 0.9*inch, 1.4*inch, 1.4*inch, 0.6*inch], repeatRows=1)
                modified_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), korean_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.wheat),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('WORDWRAP', (0, 0), (-1, -1), 'LTR')
                ]))
                
                story.append(modified_table)
                story.append(Spacer(1, 15))
        
        # JavaScript 검출된 페이지 목록
        if len(self.javascript_stats['pages_with_javascript']) > 0:
            story.append(Paragraph(f"■ JavaScript 검출된 페이지 (총 {len(self.javascript_stats['pages_with_javascript'])}개)", heading_style))
            
            js_data = [["URL", "페이지 제목", "페이지 경로", "텍스트 미리보기", "링크"]]
            for js_page in self.javascript_stats['pages_with_javascript']:
                title = self.decode_html_entities(js_page.get('title', '제목 없음'))
                hierarchy = self.decode_html_entities(self.format_hierarchy_for_display(js_page.get('hierarchy', {})))
                url = self.decode_html_entities(js_page['url'])
                text_preview = self.decode_html_entities(js_page.get('text_preview', ''))
                
                # Paragraph로 감싸서 자동 줄바꿈 적용
                url_para = Paragraph(self.escape_for_paragraph(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=5, fontName=korean_font))
                title_para = Paragraph(self.escape_for_paragraph(title), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                hierarchy_para = Paragraph(self.escape_for_paragraph(hierarchy), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                preview_para = Paragraph(self.escape_for_paragraph(text_preview), ParagraphStyle('CellStyle', parent=normal_style, fontSize=5, fontName=korean_font))
                link_para = Paragraph(self.create_link_button(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                
                js_data.append([url_para, title_para, hierarchy_para, preview_para, link_para])
            
            js_table = Table(js_data, colWidths=[1.2*inch, 1.2*inch, 1.0*inch, 1.8*inch, 0.8*inch], repeatRows=1)
            js_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), korean_font),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (0, 0), (-1, -1), 'LTR')
            ]))
            
            story.append(js_table)
        
        # murl 필드가 비어있는 항목들의 담당자 정보
        if empty_url_items and len(empty_url_items) > 0:
            story.append(Spacer(1, 20))
            story.append(Paragraph(f"■ murl 필드가 비어있는 항목들의 담당자 정보 (총 {len(empty_url_items)}개)", heading_style))
            
            manager_data = [["URL", "페이지 제목", "페이지 경로", "담당자 정보"]]
            for item in empty_url_items:
                title = self.decode_html_entities(item.get('title', '제목 없음'))
                hierarchy = self.decode_html_entities(item.get('hierarchy', '경로 없음'))
                url = self.decode_html_entities(item.get('url', ''))
                manager_info = item.get('manager_info')
                
                # 담당자 정보 포맷팅 (담당자 정보가 있는 경우만 처리)
                team_name = manager_info.get('team_name', '')
                manager_names = manager_info.get('manager_names', '')
                manager_text = f"팀: {team_name}\n담당자: {manager_names}"
                
                # Paragraph로 감싸서 자동 줄바꿈 적용
                url_para = Paragraph(self.escape_for_paragraph(url), ParagraphStyle('CellStyle', parent=normal_style, fontSize=5, fontName=korean_font))
                title_para = Paragraph(self.escape_for_paragraph(title), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                hierarchy_para = Paragraph(self.escape_for_paragraph(hierarchy), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                manager_para = Paragraph(self.escape_for_paragraph(manager_text), ParagraphStyle('CellStyle', parent=normal_style, fontSize=6, fontName=korean_font))
                
                manager_data.append([url_para, title_para, hierarchy_para, manager_para])
            
            manager_table = Table(manager_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 1.8*inch], repeatRows=1)
            manager_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), korean_font),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('WORDWRAP', (0, 0), (-1, -1), 'LTR')
            ]))
            
            story.append(manager_table)
        
        # 페이지 마무리
        story.append(Spacer(1, 30))
        story.append(Paragraph("■ 분석 방법론", heading_style))
        methodology = [
            "• URL과 페이지 계층구조를 조합한 고유 식별자 기반 비교",
            "• 텍스트 정규화를 통한 정확한 변경사항 감지",
            "• 메타데이터 세부 필드별 상세 분석"
        ]
        for item in methodology:
            story.append(Paragraph(item, normal_style))
        
        story.append(Spacer(1, 15))
        story.append(Paragraph("■ 주의사항", heading_style))
        notes = [
            "• 본 리포트는 자동화된 분석 결과이므로 중요한 변경사항은 수동 검토를 권장합니다",
            "• URL 변경이나 페이지 구조 변경 시 추가 분석이 필요할 수 있습니다",
            "• 동적 콘텐츠나 시간 기반 정보는 정상적인 변경으로 간주될 수 있습니다"
        ]
        for item in notes:
            story.append(Paragraph(item, normal_style))
        
        # 푸터 정보
        story.append(Spacer(1, 20))
        footer_text = f"리포트 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | JSON 파일 비교 도구 v1.0"
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontName=korean_font, fontSize=8, alignment=TA_CENTER, textColor=colors.grey)
        story.append(Paragraph(footer_text, footer_style))
        
        # PDF 생성
        try:
            doc.build(story)
            logger.info("PDF 리포트 생성 완료!")
        except Exception as e:
            logger.error(f"PDF 생성 중 오류 발생: {e}")
            raise
    
    def generate_summary_report(self, summary: Dict[str, Any]) -> str:
        """요약 정보를 텍스트로 생성합니다."""
        report = []
        report.append("=" * 80)
        report.append("JSON 파일 비교 요약 리포트 (URL 기반 객체 비교)")
        report.append("=" * 80)
        report.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"이전 파일: {summary['file1']}")
        report.append(f"현재 파일: {summary['file2']}")
        report.append("")
        
        # 요약 통계
        report.append("변경사항 요약")
        report.append("-" * 40)
        report.append(f"이전 파일 총 객체 수: {summary['total_objects_1']:,}")
        report.append(f"현재 파일 총 객체 수: {summary['total_objects_2']:,}")
        report.append(f"전체 변경 객체 수: {summary['total_changes']:,}")
        report.append(f"변경되지 않은 객체: {summary['objects_unchanged']:,}")
        report.append("")
        report.append("변경 유형별 통계:")
        report.append(f"  • 삭제된 객체: {summary['objects_removed']:,}")
        report.append(f"  • 추가된 객체: {summary['objects_added']:,}")
        report.append(f"  • 수정된 객체: {summary['objects_modified']:,}")
        report.append("")
        report.append("JavaScript 검출 통계:")
        report.append(f"  • JavaScript 문구 검출 페이지: {summary['javascript_pages']:,}")
        report.append("")
        
        # 변화가 없는 경우
        if summary['total_changes'] == 0:
            report.append("두 파일이 완전히 동일합니다!")
        
        report.append("=" * 80)
        report.append("참고: URL + hierarchy를 고유 식별자로 사용하여 객체 단위로 비교했습니다.")
        report.append("비교 대상: murl, title, text, metadata (단, metadata.changes 필드는 제외)")
        report.append("자세한 변경사항은 CSV 파일을 확인하세요.")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description="두 JSON 파일을 URL 기반으로 객체 단위 비교하고 차이점을 PDF 리포트로 생성합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python json_compare.py data_2025-08-01.json data_2025-08-02.json
  python json_compare.py old.json new.json -o report.pdf
  
특징:
  - URL + hierarchy를 고유 식별자로 사용
  - 객체 단위로 추가/삭제/수정 구분
  - murl, title, text, metadata 필드만 비교 (metadata.changes 제외)
  - 같은 URL+hierarchy 내에서 필드별 변경사항 추적
  - 전문적인 PDF 형식으로 결과 출력
  - 크로스 플랫폼 한글 폰트 지원 (Windows, macOS, Linux)
  - 자동 폰트 다운로드로 한글 깨짐 방지
  
한글 폰트 지원:
  - 시스템 폰트 자동 감지 (맑은 고딕, Apple Gothic 등)
  - Noto Sans CJK 자동 다운로드 (인터넷 연결 필요)
  - fonts/ 폴더에서 사용자 지정 폰트 지원
        """
    )
    
    parser.add_argument("file1", help="이전 JSON 파일")
    parser.add_argument("file2", help="현재 JSON 파일") 
    parser.add_argument("-o", "--output", help="PDF 리포트를 저장할 파일 (기본값: comparison_report_YYYYMMDD_HHMMSS.pdf)")
    parser.add_argument("-q", "--quiet", action="store_true", help="콘솔 출력 없이 파일만 저장")
    
    args = parser.parse_args()
    
    # 기본 출력 파일명 설정
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if not args.output:
        pdf_output = f"comparison_report_{timestamp}.pdf"
    else:
        pdf_output = args.output if args.output.endswith('.pdf') else f"{args.output}.pdf"
    
    # 파일 존재 확인
    for filepath in [args.file1, args.file2]:
        if not Path(filepath).exists():
            print(f"오류: 파일 '{filepath}'를 찾을 수 없습니다.")
            sys.exit(1)
    
    # 비교 실행
    comparator = URLBasedComparator()
    summary = comparator.compare_json(args.file1, args.file2)
    
    # PDF 리포트 생성
    try:
        comparator.generate_pdf_report(summary, pdf_output)
        
        if not args.quiet:
            print("\n" + "="*50)
            print("비교 완료! 요약:")
            print(f"전체 변경 객체: {summary['total_changes']:,}개")
            print(f"- 삭제: {summary['objects_removed']:,}")
            print(f"- 추가: {summary['objects_added']:,}")
            print(f"- 수정: {summary['objects_modified']:,}")
            print("="*50)
            print(f"\nPDF 리포트가 '{pdf_output}' 파일에 저장되었습니다.")
        
        # 요약 정보도 콘솔에 출력 (quiet 모드가 아닌 경우)
        if not args.quiet:
            summary_report = comparator.generate_summary_report(summary)
            print("\n" + summary_report)
            
    except ImportError:
        print("오류: reportlab 라이브러리가 설치되지 않았습니다.")
        print("PDF 생성을 위해 다음 명령어를 실행하세요: pip install reportlab")
        sys.exit(1)
    except Exception as e:
        print(f"PDF 생성 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()