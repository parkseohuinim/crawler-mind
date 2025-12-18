"""
Page Handler Registry

URL 패턴과 핸들러 함수를 매핑하고 라우팅하는 기능을 제공합니다.
모든 핸들러는 비동기(async)로 통일되어 있습니다.
"""

import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple

logger = logging.getLogger(__name__)

# 페이지 핸들러 함수 타입 (비동기 전용)
PageHandlerFunc = Callable[[str, Any, Optional[str]], Awaitable[Dict[str, Any]]]

# URL 패턴과 핸들러 함수를 매핑하는 글로벌 레지스트리
URL_PATTERNS: List[Tuple[Pattern, PageHandlerFunc]] = []


def register_page_handler(url_pattern: str, handler_func: PageHandlerFunc) -> None:
    """
    URL 패턴과 핸들러 함수를 등록
    
    Args:
        url_pattern: 정규식 패턴
        handler_func: 비동기 핸들러 함수
    """
    compiled_pattern = re.compile(url_pattern)
    URL_PATTERNS.append((compiled_pattern, handler_func))
    logger.debug(f"핸들러 등록됨: {url_pattern} -> {handler_func.__name__}")


def get_registered_handlers() -> List[Tuple[str, str]]:
    """등록된 핸들러 목록 반환"""
    return [(pattern.pattern, func.__name__) for pattern, func in URL_PATTERNS]


async def route_url(
    url: str, 
    fclient: Any, 
    menu: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    URL에 맞는 핸들러를 찾아서 실행 (비동기)
    
    Args:
        url: 처리할 URL
        fclient: 스크래핑 클라이언트 (PageHandlerClient 인스턴스)
        menu: 메뉴 정보
        
    Returns:
        Optional[Dict[str, Any]]: 핸들러 결과 또는 None (기본 스크래핑용)
    """
    for pattern, handler_func in URL_PATTERNS:
        if pattern.match(url):
            try:
                logger.info(f"🎯 URL 매칭됨: {url} -> {handler_func.__name__}")
                
                # 핸들러 시그니처에 따라 인자 전달
                # 대부분의 핸들러: (url, fclient, menu)
                # 일부 핸들러: (url, fclient)
                import inspect
                sig = inspect.signature(handler_func)
                params = list(sig.parameters.keys())
                
                if len(params) >= 3:
                    result = await handler_func(url, fclient, menu)
                else:
                    result = await handler_func(url, fclient)
                    
                return result
            except Exception as e:
                logger.error(f"❌ 핸들러 실행 중 오류: {handler_func.__name__} - {str(e)}")
                return None
    
    # 핸들러가 없는 경우 None 반환 (기본 스크래핑 실행을 위해)
    logger.info(f"🔍 URL에 맞는 핸들러가 없어 기본 스크래핑을 실행합니다: {url}")
    return None


def clear_handlers() -> None:
    """등록된 핸들러 모두 제거 (테스트용)"""
    global URL_PATTERNS
    URL_PATTERNS.clear()
    logger.info("모든 핸들러가 제거되었습니다")


def get_handler_for_url(url: str) -> Optional[Tuple[str, PageHandlerFunc]]:
    """
    URL에 매칭되는 핸들러 반환 (실행하지 않음)
    
    Args:
        url: 확인할 URL
        
    Returns:
        Optional[Tuple[str, PageHandlerFunc]]: (패턴 문자열, 핸들러 함수) 또는 None
    """
    for pattern, handler_func in URL_PATTERNS:
        if pattern.match(url):
            return (pattern.pattern, handler_func)
    return None


def get_handler_count() -> int:
    """등록된 핸들러 수 반환"""
    return len(URL_PATTERNS)
