"""Menu Link entity"""
from sqlalchemy import Column, BigInteger, Text, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.database.base import Base

class MenuLink(Base):
    """Menu link database model - Aggregate Root"""
    __tablename__ = "menu_links"
    
    id = Column(BigInteger, primary_key=True, index=True)
    document_id = Column(String(50), nullable=True, index=True)
    menu_path = Column(Text, nullable=False, index=True)
    pc_url = Column(Text, nullable=True)
    mobile_url = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    
    # Relationship to manager info
    manager_info = relationship("MenuManagerInfo", back_populates="menu_link", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MenuLink(id={self.id}, menu_path='{self.menu_path}')>"
    
    def has_manager(self) -> bool:
        """Check if menu link has associated manager info"""
        return self.manager_info is not None
    
    def get_manager_team(self) -> str | None:
        """Get manager team name if exists"""
        return self.manager_info.team_name if self.manager_info else None
    
    def get_manager_names(self) -> str | None:
        """Get manager names if exists"""
        return self.manager_info.manager_names if self.manager_info else None
