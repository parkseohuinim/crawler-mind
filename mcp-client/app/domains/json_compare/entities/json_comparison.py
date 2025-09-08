"""JSON Comparison Entity"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class JsonComparisonResult:
    """JSON 비교 결과 엔티티"""
    id: str
    file1_name: str
    file2_name: str
    file1_size: int
    file2_size: int
    total_objects_1: int
    total_objects_2: int
    objects_removed: int
    objects_added: int
    objects_modified: int
    objects_unchanged: int
    total_changes: int
    javascript_pages: int
    created_at: datetime
    status: str  # 'processing', 'completed', 'failed'
    error_message: Optional[str] = None
    pdf_file_path: Optional[str] = None
    summary_report: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'file1_name': self.file1_name,
            'file2_name': self.file2_name,
            'file1_size': self.file1_size,
            'file2_size': self.file2_size,
            'total_objects_1': self.total_objects_1,
            'total_objects_2': self.total_objects_2,
            'objects_removed': self.objects_removed,
            'objects_added': self.objects_added,
            'objects_modified': self.objects_modified,
            'objects_unchanged': self.objects_unchanged,
            'total_changes': self.total_changes,
            'javascript_pages': self.javascript_pages,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'error_message': self.error_message,
            'pdf_file_path': self.pdf_file_path,
            'summary_report': self.summary_report
        }


@dataclass
class JsonComparisonTask:
    """JSON 비교 작업 엔티티"""
    id: str
    file1_path: str
    file2_path: str
    file1_name: str
    file2_name: str
    created_at: datetime
    status: str  # 'pending', 'processing', 'completed', 'failed'
    result: Optional[JsonComparisonResult] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'file1_path': self.file1_path,
            'file2_path': self.file2_path,
            'file1_name': self.file1_name,
            'file2_name': self.file2_name,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'result': self.result.to_dict() if self.result else None,
            'error_message': self.error_message
        }
