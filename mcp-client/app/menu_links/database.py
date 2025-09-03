"""Menu Links database models and operations"""
from sqlalchemy import Column, BigInteger, Text, String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from typing import List, Optional
from app.database import Base

class MenuLink(Base):
    """Menu link database model"""
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

class MenuManagerInfo(Base):
    """Menu manager info database model"""
    __tablename__ = "menu_manager_info"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(BigInteger, ForeignKey("menu_links.id", ondelete="CASCADE"), nullable=False, index=True)
    team_name = Column(Text, nullable=False)
    manager_names = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    
    # Relationship to menu link
    menu_link = relationship("MenuLink", back_populates="manager_info")
