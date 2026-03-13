"""GNB 메뉴 추출 API 라우터"""
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.application.gnb.gnb_menu_service import gnb_menu_service
from app.domains.gnb.repositories.menu_repository import menu_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gnb", tags=["GNB Menu"])


# ── Request / Response 모델 ──

class ExtractMenusRequest(BaseModel):
    save_to_db: bool = Field(True, description="추출 결과를 menus 테이블에 저장 여부")
    delay: float = Field(1.0, ge=0.0, le=10.0, description="페이지 간 대기 시간(초)")


class ExtractMenusTaskResponse(BaseModel):
    task_id: str
    message: str


class ExtractMenusTaskStatus(BaseModel):
    task_id: str
    status: str
    step: Optional[str] = None
    progress: Optional[dict] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class MenuStatsResponse(BaseModel):
    total: int
    active: int
    with_mobile_url: int
    without_mobile_url: int


# ── Endpoints ──

@router.post("/extract_menus", response_model=ExtractMenusTaskResponse)
async def extract_menus(request: ExtractMenusRequest = None):
    """
    GNB 메뉴 추출 태스크를 생성하고 백그라운드에서 실행합니다.
    즉시 task_id를 반환하며, GET /gnb/extract_menus/{task_id}로 진행 상황을 폴링할 수 있습니다.
    """
    save_to_db = request.save_to_db if request else True
    delay = request.delay if request else 1.0

    logger.info(f"🚀 GNB 메뉴 추출 태스크 생성 (save_to_db={save_to_db}, delay={delay})")
    task_id = gnb_menu_service.create_extraction_task(
        save_to_db=save_to_db,
        delay=delay,
    )

    return ExtractMenusTaskResponse(
        task_id=task_id,
        message="GNB 메뉴 추출 태스크가 생성되었습니다.",
    )


@router.get("/extract_menus/{task_id}", response_model=ExtractMenusTaskStatus)
async def get_extract_menus_task(task_id: str):
    """GNB 메뉴 추출 태스크 진행 상황 조회"""
    task = gnb_menu_service.get_extraction_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return ExtractMenusTaskStatus(
        task_id=task.task_id,
        status=task.status,
        step=task.step,
        progress=task.progress,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/extract_menus_tasks", response_model=list)
async def list_extract_menus_tasks(limit: int = Query(10, ge=1, le=50)):
    """GNB 메뉴 추출 태스크 목록 조회"""
    return gnb_menu_service.get_extraction_tasks(limit=limit)


@router.get("/menus", response_model=list)
async def get_menus(
    limit: int = Query(100, ge=1, le=5000, description="조회 개수"),
):
    """저장된 GNB 메뉴 목록 조회"""
    try:
        menus = await menu_repository.get_active_menus()
        items = [
            {
                "id": m.id,
                "pc_url": m.pc_url,
                "mobile_url": m.mobile_url,
                "menu_path": m.menu_path,
                "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in menus[:limit]
        ]
        return items
    except Exception as e:
        logger.error(f"메뉴 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"메뉴 조회 실패: {str(e)}")


@router.get("/stats", response_model=MenuStatsResponse)
async def get_menu_stats():
    """GNB 메뉴 통계 조회"""
    try:
        stats = await menu_repository.get_stats()
        return MenuStatsResponse(**stats)
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.post("/update_mobile_urls")
async def update_mobile_urls():
    """모바일 URL 후처리 실행 (기본 도메인 변환 규칙 적용)"""
    try:
        updated = await gnb_menu_service.update_mobile_urls()
        return {
            "success": True,
            "message": f"모바일 URL {updated}개 업데이트 완료",
            "updated_count": updated,
        }
    except Exception as e:
        logger.error(f"모바일 URL 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모바일 URL 업데이트 실패: {str(e)}")
