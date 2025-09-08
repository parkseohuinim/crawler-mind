"""JSON Compare API Router"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import logging
import asyncio
import json
from typing import Optional

from app.domains.json_compare.schemas.json_compare_schemas import (
    JsonComparisonRequest,
    JsonComparisonResponse,
    JsonComparisonTaskResponse,
    JsonComparisonResultResponse
)
from app.domains.json_compare.services.json_compare_service import json_compare_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/json-compare", tags=["json-compare"])


@router.post("/compare", response_model=JsonComparisonResponse)
async def create_comparison(request: JsonComparisonRequest):
    """JSON 파일 비교 작업 생성"""
    try:
        # JSON 유효성 검사
        try:
            json.loads(request.file1_content)
            json.loads(request.file2_content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
        
        # 작업 생성
        task_id = json_compare_service.create_comparison_task(request)
        
        # 백그라운드에서 비교 처리
        asyncio.create_task(process_comparison_async(task_id))
        
        return JsonComparisonResponse(
            task_id=task_id,
            status="pending",
            message="JSON 비교 작업이 시작되었습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create comparison: {e}")
        raise HTTPException(status_code=500, detail=f"비교 작업 생성 중 오류: {str(e)}")


async def process_comparison_async(task_id: str):
    """비동기 비교 처리"""
    try:
        result = json_compare_service.process_comparison(task_id)
        logger.info(f"Comparison completed for task: {task_id}")
    except Exception as e:
        logger.error(f"Comparison failed for task {task_id}: {e}", exc_info=True)


@router.get("/task/{task_id}", response_model=JsonComparisonTaskResponse)
async def get_task_status(task_id: str):
    """작업 상태 조회"""
    try:
        task = json_compare_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return JsonComparisonTaskResponse(
            id=task.id,
            file1_name=task.file1_name,
            file2_name=task.file2_name,
            created_at=task.created_at,
            status=task.status,
            result=JsonComparisonResultResponse(**task.result.to_dict()) if task.result else None,
            error_message=task.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=500, detail=f"작업 상태 조회 중 오류: {str(e)}")


@router.get("/task/{task_id}/result", response_model=JsonComparisonResultResponse)
async def get_comparison_result(task_id: str):
    """비교 결과 조회"""
    try:
        task = json_compare_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        if not task.result:
            raise HTTPException(status_code=404, detail="비교 결과를 찾을 수 없습니다")
        
        return JsonComparisonResultResponse(**task.result.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get comparison result: {e}")
        raise HTTPException(status_code=500, detail=f"비교 결과 조회 중 오류: {str(e)}")


@router.get("/task/{task_id}/download")
async def download_pdf_report(task_id: str):
    """PDF 리포트 다운로드"""
    try:
        task = json_compare_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        if not task.result or not task.result.pdf_file_path:
            raise HTTPException(status_code=404, detail="PDF 리포트를 찾을 수 없습니다")
        
        pdf_content = json_compare_service.get_pdf_file(task_id)
        if not pdf_content:
            raise HTTPException(status_code=404, detail="PDF 파일을 읽을 수 없습니다")
        
        # PDF 파일명을 날짜+시간 형식으로 변경
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"report_{timestamp}.pdf"
        
        return StreamingResponse(
            iter([pdf_content]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_content))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download PDF: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 다운로드 중 오류: {str(e)}")


@router.delete("/task/{task_id}")
async def cleanup_task(task_id: str, background_tasks: BackgroundTasks):
    """작업 정리"""
    try:
        task = json_compare_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        # 백그라운드에서 정리
        background_tasks.add_task(json_compare_service.cleanup_task, task_id)
        
        return {"message": "작업 정리가 예약되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup task: {e}")
        raise HTTPException(status_code=500, detail=f"작업 정리 중 오류: {str(e)}")
