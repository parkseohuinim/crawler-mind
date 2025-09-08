"""JSON Compare Schemas"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class JsonComparisonRequest(BaseModel):
    """JSON 비교 요청 스키마"""
    file1_name: str = Field(..., description="첫 번째 JSON 파일명")
    file2_name: str = Field(..., description="두 번째 JSON 파일명")
    file1_content: str = Field(..., description="첫 번째 JSON 파일 내용")
    file2_content: str = Field(..., description="두 번째 JSON 파일 내용")


class JsonComparisonResponse(BaseModel):
    """JSON 비교 응답 스키마"""
    task_id: str = Field(..., description="작업 ID")
    status: str = Field(..., description="작업 상태")
    message: str = Field(..., description="응답 메시지")


class JsonComparisonResultResponse(BaseModel):
    """JSON 비교 결과 응답 스키마"""
    id: str = Field(..., description="결과 ID")
    file1_name: str = Field(..., description="첫 번째 파일명")
    file2_name: str = Field(..., description="두 번째 파일명")
    file1_size: int = Field(..., description="첫 번째 파일 크기")
    file2_size: int = Field(..., description="두 번째 파일 크기")
    total_objects_1: int = Field(..., description="첫 번째 파일 객체 수")
    total_objects_2: int = Field(..., description="두 번째 파일 객체 수")
    objects_removed: int = Field(..., description="삭제된 객체 수")
    objects_added: int = Field(..., description="추가된 객체 수")
    objects_modified: int = Field(..., description="수정된 객체 수")
    objects_unchanged: int = Field(..., description="변경되지 않은 객체 수")
    total_changes: int = Field(..., description="총 변경사항 수")
    javascript_pages: int = Field(..., description="JavaScript 검출 페이지 수")
    created_at: datetime = Field(..., description="생성 시간")
    status: str = Field(..., description="상태")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    pdf_file_path: Optional[str] = Field(None, description="PDF 파일 경로")
    summary_report: Optional[str] = Field(None, description="요약 리포트")


class JsonComparisonTaskResponse(BaseModel):
    """JSON 비교 작업 응답 스키마"""
    id: str = Field(..., description="작업 ID")
    file1_name: str = Field(..., description="첫 번째 파일명")
    file2_name: str = Field(..., description="두 번째 파일명")
    created_at: datetime = Field(..., description="생성 시간")
    status: str = Field(..., description="작업 상태")
    result: Optional[JsonComparisonResultResponse] = Field(None, description="비교 결과")
    error_message: Optional[str] = Field(None, description="오류 메시지")
