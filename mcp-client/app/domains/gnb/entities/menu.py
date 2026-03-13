"""Menu Entity - GNB 메뉴 추출 결과 (input_urls와 동일 스키마)"""
from sqlalchemy import Column, BigInteger, Text, String, DateTime, Integer, Boolean
from sqlalchemy.sql import func
from app.shared.database.base import Base


class Menu(Base):
    """GNB에서 추출된 메뉴 테이블"""
    __tablename__ = "menus"
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    pc_url = Column(Text, nullable=False, index=True)
    mobile_url = Column(Text, nullable=True)
    
    menu_path = Column(Text, nullable=True)  # "Shop^요금제^5G" 형태
    
    handler_name = Column(String(100), nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)
    
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)
    last_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Menu(id={self.id}, menu_path='{self.menu_path}', pc_url='{self.pc_url[:50]}...')>"
    
    def get_hierarchy_list(self) -> list:
        """menu_path를 hierarchy 리스트로 변환"""
        if not self.menu_path:
            return []
        return [seg.strip() for seg in self.menu_path.split("^") if seg.strip()]
