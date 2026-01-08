"""Daily Crawling Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List


class DailyCrawlRequest(BaseModel):
    """Daily Crawling 요청 스키마"""
    force_recrawl: bool = Field(
        default=True,
        description="이미 성공한 URL도 재크롤링 여부 (Daily Crawling은 기본 True)"
    )
    limit: Optional[int] = Field(
        default=None,
        description="최대 크롤링 URL 수 (None이면 전체, url_ids가 있으면 무시됨)"
    )
    url_ids: Optional[List[int]] = Field(
        default=[],
        description="테스트용: 특정 input_urls ID 목록 (지정 시 해당 ID만 크롤링)"
    )
    mode: Literal["sequential", "parallel"] = Field(
        default="parallel",
        description="실행 모드 (sequential: 순차, parallel: 병렬)"
    )
    concurrency: int = Field(
        default=3,
        ge=1,
        le=10,
        description="병렬 실행 시 동시 처리 수 (1~10, 기본값: 3)"
    )
    update_menu_links: bool = Field(
        default=True,
        description="menu_links DB 업데이트 여부 (기본값: True)"
    )


class DailyCrawlTaskResponse(BaseModel):
    """Daily Crawling 태스크 응답 스키마"""
    task_id: str = Field(..., description="태스크 ID")
    total_urls: int = Field(..., description="총 크롤링 대상 URL 수")
    message: str = Field(..., description="메시지")


class DailyCrawlStats(BaseModel):
    """Daily Crawling 통계 스키마"""
    total: int = Field(..., description="전체 URL 수")
    active: int = Field(..., description="활성 URL 수")
    success: int = Field(..., description="성공한 URL 수")
    failed: int = Field(..., description="실패한 URL 수")
    pending: int = Field(..., description="대기 중인 URL 수")

