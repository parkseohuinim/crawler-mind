"""InputUrl Entity - 크롤링 대상 URL"""
from sqlalchemy import Column, BigInteger, Text, String, DateTime, Integer, Boolean
from sqlalchemy.sql import func
from app.shared.database.base import Base


class InputUrl(Base):
    """크롤링 대상 URL 테이블"""
    __tablename__ = "input_urls"
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    # URL 정보
    pc_url = Column(Text, nullable=False, index=True)
    mobile_url = Column(Text, nullable=True)
    
    # 분류 정보
    menu_path = Column(Text, nullable=True)  # "Shop^요금제^5G" 형태
    
    # 크롤링 설정
    handler_name = Column(String(100), nullable=True)  # 전용 핸들러 (nullable = 자동 감지)
    priority = Column(Integer, default=0)  # 우선순위 (높을수록 먼저)
    is_active = Column(Boolean, default=True, index=True)
    
    # 크롤링 상태
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)  # 'success', 'failed', 'skipped'
    last_error = Column(Text, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<InputUrl(id={self.id}, pc_url='{self.pc_url[:50]}...')>"
    
    def get_hierarchy_list(self) -> list:
        """menu_path를 hierarchy 리스트로 변환"""
        if not self.menu_path:
            return []
        return [seg.strip() for seg in self.menu_path.split("^") if seg.strip()]


