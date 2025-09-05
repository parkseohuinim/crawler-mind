"""Document entity for RAG system"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Document:
    """Document entity representing a piece of content for RAG"""
    
    id: str
    title: str
    content: str
    url: Optional[str] = None
    mobile_url: Optional[str] = None
    hierarchy: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary for storage"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'mobile_url': self.mobile_url,
            'hierarchy': self.hierarchy,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_json_data(cls, data: Dict[str, Any]) -> 'Document':
        """Create document from JSON data (like data_2025-09-03.json format)"""
        return cls(
            id=data.get('docId', ''),
            title=data.get('title', ''),
            content=data.get('text', ''),
            url=data.get('url'),
            mobile_url=data.get('murl'),
            hierarchy=data.get('hierarchy', []),
            metadata=data.get('metadata', {}),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
