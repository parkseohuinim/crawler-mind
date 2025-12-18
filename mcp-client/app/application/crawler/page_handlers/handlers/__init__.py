"""
Page Handlers - 도메인별 핸들러 모듈

각 도메인별 핸들러를 import하여 자동으로 등록합니다.
핸들러 모듈 import 시 register_page_handler가 자동 호출되어
URL 패턴이 등록됩니다.
"""

# 핸들러 모듈 import (import 시 자동으로 register_page_handler 호출됨)
from . import membership          # KT 멤버십 (제휴 브랜드, FAQ)
from . import interpark           # 인터파크 공지사항
from . import globalroaming       # 글로벌 로밍 공지사항
from . import kt_notice           # KT 공지사항 (inside.kt.com)
from . import gigagenie           # 지니지니 (FAQ, 상세, 뉴스)
from . import ktshop              # KT Shop (액세서리, 팝업, 모바일 제품, 요금제)
from . import network_notice      # 네트워크 공지사항
from . import safety_notice       # 안전한 통신생활 공지사항
from . import kt_event            # KT 이벤트 (진행중 이벤트)
from . import kt_past_event       # KT 지난 이벤트 (주석 처리된 핸들러 포함)
from . import tv_channel          # 지니TV 채널 편성표
from . import webzine             # 웹진 리스트
from . import faq                 # FAQ (영화예매, ERMS)
from . import wdic                # KT 상품사전 (상품 상세, 카테고리 목록)
from . import winner_announcements  # KT Shop 당첨자발표

__all__ = [
    "membership",
    "interpark",
    "globalroaming",
    "kt_notice",
    "gigagenie",
    "ktshop",
    "network_notice",
    "safety_notice",
    "kt_event",
    "kt_past_event",
    "tv_channel",
    "webzine",
    "faq",
    "wdic",
    "winner_announcements",
]
