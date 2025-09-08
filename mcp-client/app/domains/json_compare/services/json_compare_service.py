"""JSON Compare Service"""
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from app.domains.json_compare.entities.json_comparison import JsonComparisonResult, JsonComparisonTask
from app.domains.json_compare.schemas.json_compare_schemas import JsonComparisonRequest

logger = logging.getLogger(__name__)


class JsonCompareService:
    """JSON 비교 서비스"""
    
    def __init__(self, temp_dir: str = "/tmp/json_compare"):
        """JSON 비교 서비스 초기화"""
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, JsonComparisonTask] = {}
        
    def create_comparison_task(self, request: JsonComparisonRequest) -> str:
        """JSON 비교 작업 생성"""
        task_id = str(uuid.uuid4())
        
        # 임시 파일 생성
        file1_path = self.temp_dir / f"{task_id}_file1.json"
        file2_path = self.temp_dir / f"{task_id}_file2.json"
        
        try:
            # JSON 파일 저장
            with open(file1_path, 'w', encoding='utf-8') as f:
                f.write(request.file1_content)
            
            with open(file2_path, 'w', encoding='utf-8') as f:
                f.write(request.file2_content)
            
            # 작업 생성
            task = JsonComparisonTask(
                id=task_id,
                file1_path=str(file1_path),
                file2_path=str(file2_path),
                file1_name=request.file1_name,
                file2_name=request.file2_name,
                created_at=datetime.now(),
                status='pending'
            )
            
            self.tasks[task_id] = task
            logger.info(f"Created JSON comparison task: {task_id}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create comparison task: {e}")
            # 임시 파일 정리
            for file_path in [file1_path, file2_path]:
                if file_path.exists():
                    file_path.unlink()
            raise
    
    def get_task(self, task_id: str) -> Optional[JsonComparisonTask]:
        """작업 조회"""
        return self.tasks.get(task_id)
    
    def process_comparison(self, task_id: str) -> JsonComparisonResult:
        """JSON 비교 처리"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        try:
            task.status = 'processing'
            logger.info(f"Starting JSON comparison for task: {task_id}")
            
            # JSON 비교 실행
            from app.infrastructure.json_compare.json_compare import URLBasedComparator
            
            comparator = URLBasedComparator()
            summary = comparator.compare_json(task.file1_path, task.file2_path, task.file1_name, task.file2_name)
            logger.info(f"JSON comparison completed for task: {task_id}")
            
            # PDF 리포트 생성 (날짜+시간 형식)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
            pdf_path = self.temp_dir / f"report_{timestamp}.pdf"
            logger.info(f"Generating PDF report for task: {task_id}")
            comparator.generate_pdf_report(summary, str(pdf_path))
            logger.info(f"PDF report generated: {pdf_path}")
            
            # 요약 리포트 생성
            summary_report = comparator.generate_summary_report(summary)
            
            # 결과 생성
            result = JsonComparisonResult(
                id=str(uuid.uuid4()),
                file1_name=task.file1_name,
                file2_name=task.file2_name,
                file1_size=summary['total_objects_1'],
                file2_size=summary['total_objects_2'],
                total_objects_1=summary['total_objects_1'],
                total_objects_2=summary['total_objects_2'],
                objects_removed=summary['objects_removed'],
                objects_added=summary['objects_added'],
                objects_modified=summary['objects_modified'],
                objects_unchanged=summary['objects_unchanged'],
                total_changes=summary['total_changes'],
                javascript_pages=summary['javascript_pages'],
                created_at=datetime.now(),
                status='completed',
                pdf_file_path=str(pdf_path),
                summary_report=summary_report
            )
            
            task.result = result
            task.status = 'completed'
            
            logger.info(f"Completed JSON comparison task: {task_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process comparison task {task_id}: {e}", exc_info=True)
            task.status = 'failed'
            task.error_message = str(e)
            
            result = JsonComparisonResult(
                id=str(uuid.uuid4()),
                file1_name=task.file1_name,
                file2_name=task.file2_name,
                file1_size=0,
                file2_size=0,
                total_objects_1=0,
                total_objects_2=0,
                objects_removed=0,
                objects_added=0,
                objects_modified=0,
                objects_unchanged=0,
                total_changes=0,
                javascript_pages=0,
                created_at=datetime.now(),
                status='failed',
                error_message=str(e)
            )
            
            task.result = result
            return result
    
    def get_pdf_file(self, task_id: str) -> Optional[bytes]:
        """PDF 파일 조회"""
        task = self.tasks.get(task_id)
        if not task or not task.result or not task.result.pdf_file_path:
            return None
        
        pdf_path = Path(task.result.pdf_file_path)
        if not pdf_path.exists():
            return None
        
        try:
            with open(pdf_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read PDF file: {e}")
            return None
    
    def cleanup_task(self, task_id: str):
        """작업 정리"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        try:
            # 임시 파일 삭제
            for file_path in [task.file1_path, task.file2_path]:
                if Path(file_path).exists():
                    Path(file_path).unlink()
            
            # PDF 파일 삭제
            if task.result and task.result.pdf_file_path:
                pdf_path = Path(task.result.pdf_file_path)
                if pdf_path.exists():
                    pdf_path.unlink()
            
            # 작업 삭제
            del self.tasks[task_id]
            
            logger.info(f"Cleaned up task: {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup task {task_id}: {e}")


# 전역 서비스 인스턴스
json_compare_service = JsonCompareService()
