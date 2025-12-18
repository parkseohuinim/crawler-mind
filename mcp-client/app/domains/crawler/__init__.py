"""Crawler domain"""
from .entities.input_url import InputUrl
from .repositories.input_url_repository import InputUrlRepository, input_url_repository
from .schemas.daily_crawl_schemas import (
    DailyCrawlRequest,
    DailyCrawlTaskResponse,
    DailyCrawlStats,
)

__all__ = [
    "InputUrl",
    "InputUrlRepository",
    "input_url_repository",
    "DailyCrawlRequest",
    "DailyCrawlTaskResponse",
    "DailyCrawlStats",
]
