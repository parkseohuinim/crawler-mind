"""Crawling result entity"""
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class CrawlingResult:
    """Entity representing the result of a crawling operation"""
    title: Optional[str] = None
    text_length: int = 0
    link_count: int = 0
    links: List[str] = None
    summary: Optional[str] = None
    screenshot: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.links is None:
            self.links = []
    
    @property
    def is_successful(self) -> bool:
        """Check if crawling was successful"""
        return self.error is None
    
    @property
    def has_content(self) -> bool:
        """Check if result has meaningful content"""
        return bool(self.title or self.summary or self.text_length > 0)
