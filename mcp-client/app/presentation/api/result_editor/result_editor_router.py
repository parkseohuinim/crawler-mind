"""Result Editor API Router - 크롤링 결과 JSON의 text 필드 수정"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List
import json
import re as re_module
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/result-editor", tags=["result-editor"])

RESULT_DIR = Path(__file__).parent.parent.parent.parent / "application" / "crawler" / "result"


class ResultFileInfo(BaseModel):
    filename: str
    size_bytes: int
    doc_count: int
    created_at: str


class DocInfo(BaseModel):
    docId: str
    title: str
    url: str
    text: str
    hierarchy: List[str] = []


class UpdateDocTextRequest(BaseModel):
    filename: str
    docId: str
    new_text: str


class UpdateDocTextResponse(BaseModel):
    success: bool
    message: str
    backup_file: Optional[str] = None


class BatchReplaceRequest(BaseModel):
    filename: str
    doc_ids: List[str]
    find_text: str
    replace_text: str = ""
    use_regex: bool = False


class BatchReplaceResult(BaseModel):
    docId: str
    match_count: int
    replaced: bool


class BatchReplaceResponse(BaseModel):
    success: bool
    message: str
    backup_file: Optional[str] = None
    affected_count: int = 0
    results: List[BatchReplaceResult] = []


@router.get("/files", response_model=List[ResultFileInfo])
async def list_result_files():
    """결과 JSON 파일 목록 조회 (최신순)"""
    try:
        if not RESULT_DIR.exists():
            return []

        files = []
        for f in sorted(RESULT_DIR.glob("data_*.json"), reverse=True):
            try:
                content = f.read_text(encoding="utf-8")
                data = json.loads(content)
                doc_count = len(data) if isinstance(data, list) else 0
            except Exception:
                doc_count = 0

            date_part = f.stem.replace("data_", "")
            files.append(ResultFileInfo(
                filename=f.name,
                size_bytes=f.stat().st_size,
                doc_count=doc_count,
                created_at=date_part,
            ))

        return files
    except Exception as e:
        logger.error(f"Failed to list result files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doc", response_model=DocInfo)
async def get_doc(
    filename: str = Query(..., description="JSON 파일명"),
    docId: str = Query(..., description="문서 ID"),
):
    """특정 파일에서 docId로 문서 조회"""
    try:
        file_path = (RESULT_DIR / filename).resolve()
        if not str(file_path).startswith(str(RESULT_DIR.resolve())):
            raise HTTPException(status_code=403, detail="접근이 거부되었습니다")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="잘못된 파일 형식입니다")

        for doc in data:
            if doc.get("docId") == docId:
                return DocInfo(
                    docId=doc["docId"],
                    title=doc.get("title", ""),
                    url=doc.get("url", ""),
                    text=doc.get("text", ""),
                    hierarchy=doc.get("hierarchy", []),
                )

        raise HTTPException(status_code=404, detail=f"docId '{docId}'를 찾을 수 없습니다")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-docs")
async def search_docs(
    filename: str = Query(..., description="JSON 파일명"),
    query: str = Query("", description="검색어"),
    search_field: str = Query("all", description="검색 대상: all, docId, title, text"),
    limit: int = Query(50, description="최대 결과 수"),
):
    """파일 내 문서 검색 (docId, title, text 기준)"""
    try:
        file_path = (RESULT_DIR / filename).resolve()
        if not str(file_path).startswith(str(RESULT_DIR.resolve())):
            raise HTTPException(status_code=403, detail="접근이 거부되었습니다")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="잘못된 파일 형식입니다")

        results = []
        q = query.lower()
        for doc in data:
            doc_id = doc.get("docId", "")
            title = doc.get("title", "")
            text = doc.get("text", "")

            if not q:
                matched = True
            elif search_field == "docId":
                matched = q in doc_id.lower()
            elif search_field == "title":
                matched = q in title.lower()
            elif search_field == "text":
                matched = q in text.lower()
            else:
                matched = q in doc_id.lower() or q in title.lower() or q in text.lower()

            if matched:
                item = {
                    "docId": doc_id,
                    "title": title,
                    "url": doc.get("url", ""),
                    "textLength": len(text),
                }
                if search_field == "text" and q:
                    idx = text.lower().find(q)
                    if idx != -1:
                        start = max(0, idx - 40)
                        end = min(len(text), idx + len(query) + 40)
                        snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
                        item["textSnippet"] = snippet
                results.append(item)
                if len(results) >= limit:
                    break

        return {"results": results, "total": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/doc", response_model=UpdateDocTextResponse)
async def update_doc_text(request: UpdateDocTextRequest):
    """특정 문서의 text 필드 수정 (원본 자동 백업)"""
    try:
        file_path = (RESULT_DIR / request.filename).resolve()
        if not str(file_path).startswith(str(RESULT_DIR.resolve())):
            raise HTTPException(status_code=403, detail="접근이 거부되었습니다")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="잘못된 파일 형식입니다")

        doc_found = False
        for doc in data:
            if doc.get("docId") == request.docId:
                doc["text"] = request.new_text
                doc_found = True
                break

        if not doc_found:
            raise HTTPException(status_code=404, detail=f"docId '{request.docId}'를 찾을 수 없습니다")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}.bak_{timestamp}{file_path.suffix}"
        backup_path = file_path.parent / backup_name
        shutil.copy2(file_path, backup_path)

        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"Updated docId={request.docId} in {request.filename}, backup={backup_name}")

        return UpdateDocTextResponse(
            success=True,
            message=f"docId '{request.docId}' 텍스트가 수정되었습니다",
            backup_file=backup_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update doc text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/batch", response_model=BatchReplaceResponse)
async def batch_replace_text(request: BatchReplaceRequest):
    """여러 문서의 text 필드에서 일괄 치환/삭제 (원본 자동 백업)"""
    try:
        file_path = (RESULT_DIR / request.filename).resolve()
        if not str(file_path).startswith(str(RESULT_DIR.resolve())):
            raise HTTPException(status_code=403, detail="접근이 거부되었습니다")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        if not request.find_text:
            raise HTTPException(status_code=400, detail="찾을 텍스트가 비어있습니다")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="잘못된 파일 형식입니다")

        target_ids = set(request.doc_ids)

        if request.use_regex:
            try:
                pattern = re_module.compile(request.find_text)
            except re_module.error as e:
                raise HTTPException(status_code=400, detail=f"잘못된 정규식: {e}")

        results: List[BatchReplaceResult] = []
        affected_count = 0

        for doc in data:
            doc_id = doc.get("docId", "")
            if doc_id not in target_ids:
                continue

            text = doc.get("text", "")
            if request.use_regex:
                count = len(pattern.findall(text))
                if count > 0:
                    doc["text"] = pattern.sub(request.replace_text, text)
                    affected_count += 1
            else:
                count = text.count(request.find_text)
                if count > 0:
                    doc["text"] = text.replace(request.find_text, request.replace_text)
                    affected_count += 1

            results.append(BatchReplaceResult(
                docId=doc_id,
                match_count=count,
                replaced=count > 0,
            ))

        if affected_count == 0:
            return BatchReplaceResponse(
                success=True,
                message="일치하는 내용이 없어 변경사항이 없습니다",
                affected_count=0,
                results=results,
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}.bak_{timestamp}{file_path.suffix}"
        backup_path = file_path.parent / backup_name
        shutil.copy2(file_path, backup_path)

        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        action = "삭제" if not request.replace_text else "치환"
        msg = f"{affected_count}개 문서에서 일괄 {action} 완료"
        logger.info(f"Batch replace in {request.filename}: {msg}, backup={backup_name}")

        return BatchReplaceResponse(
            success=True,
            message=msg,
            backup_file=backup_name,
            affected_count=affected_count,
            results=results,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to batch replace: {e}")
        raise HTTPException(status_code=500, detail=str(e))
