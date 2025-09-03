"""Menu Manager Info entity"""
from sqlalchemy import Column, Integer, BigInteger, Text, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.database.base import Base

class MenuManagerInfo(Base):
    """Menu manager info database model - Entity within Menu aggregate"""
    __tablename__ = "menu_manager_info"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(BigInteger, ForeignKey("menu_links.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    team_name = Column(Text, nullable=False)
    manager_names = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    
    # Relationship to menu link
    menu_link = relationship("MenuLink", back_populates="manager_info")
    
    def __repr__(self):
        return f"<MenuManagerInfo(id={self.id}, menu_id={self.menu_id}, team='{self.team_name}')>"
    
    def update_team_info(self, team_name: str = None, manager_names: str = None, updated_by: str = None):
        """Update team information"""
        if team_name is not None:
            self.team_name = team_name
        if manager_names is not None:
            self.manager_names = manager_names
        if updated_by is not None:
            self.updated_by = updated_by
