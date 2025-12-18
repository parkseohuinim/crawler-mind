"""
Page Handlers 모듈

URL 패턴 기반의 페이지별 커스텀 핸들러를 제공합니다.
"""

from app.application.crawler.page_handlers.handler_registry import (
    PageHandlerFunc,
    URL_PATTERNS,
    register_page_handler,
    get_registered_handlers,
    get_handler_for_url,
    route_url,
)

# 핸들러들을 import하여 자동 등록
from app.application.crawler.page_handlers.handlers import (
    ktshop,
    kt_event,
    kt_past_event,
    tv_channel,
    winner_announcements,
)

# 클라이언트 import
from app.application.crawler.page_handler_client import page_handler_client

__all__ = [
    "PageHandlerFunc",
    "URL_PATTERNS",
    "register_page_handler",
    "get_registered_handlers",
    "get_handler_for_url",
    "route_url",
    "page_handler_client",
    # 핸들러 모듈
    "ktshop",
    "kt_event",
    "kt_past_event",
    "tv_channel",
    "winner_announcements",
]
