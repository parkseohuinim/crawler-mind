"""
기존 JSON 파일에 유사도 분석을 적용하여 중복 마킹하는 스크립트

Usage:
    python apply_similarity_to_json.py <json_file_path> [--threshold 0.99]
    
원본/중복 결정 기준:
1. hierarchy depth가 더 깊은 것(하위) → 원본 유지
2. depth가 같으면 docId 숫자가 더 작은 것 → 원본 유지
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.application.crawler.preprocess.similarity import TextSimilarityAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_docid_number(docid: str) -> int:
    """
    docId에서 숫자 부분 추출
    예: "ktcom_1764" -> 1764
    """
    if not docid:
        return float('inf')
    
    match = re.search(r'(\d+)$', docid)
    if match:
        return int(match.group(1))
    return float('inf')


def determine_original_and_duplicate(item_a: dict, item_b: dict, idx_a: int, idx_b: int) -> tuple:
    """
    두 중복 항목 중 원본과 중복을 결정
    
    기준:
    1. hierarchy depth가 더 깊은 것(하위) → 원본
    2. depth가 같으면 docId 숫자가 더 작은 것 → 원본
    
    Returns:
        (original_idx, duplicate_idx)
    """
    depth_a = len(item_a.get("hierarchy", []))
    depth_b = len(item_b.get("hierarchy", []))
    
    if depth_a != depth_b:
        if depth_a > depth_b:
            return idx_a, idx_b
        else:
            return idx_b, idx_a
    
    docid_a = item_a.get("docId", "")
    docid_b = item_b.get("docId", "")
    
    num_a = extract_docid_number(docid_a)
    num_b = extract_docid_number(docid_b)
    
    if num_a <= num_b:
        return idx_a, idx_b
    else:
        return idx_b, idx_a


def apply_similarity_analysis(results: list, threshold: float = 0.99) -> tuple:
    """
    결과 리스트에 유사도 분석을 적용하여 중복 항목을 삭제
    
    Returns:
        (중복이 삭제된 결과 리스트, 삭제된 개수)
    """
    if len(results) < 2:
        return results, 0
    
    # 유효한 텍스트와 URL 추출 (인덱스 유지)
    valid_indices = []
    texts = []
    urls = []
    
    for idx, item in enumerate(results):
        text = item.get("text", "")
        url = item.get("url", "")
        if text and text.strip() and url:
            valid_indices.append(idx)
            texts.append(text)
            urls.append(url)
    
    logger.info(f"유효한 항목: {len(valid_indices)}개 / 전체: {len(results)}개")
    
    if len(texts) < 2:
        return results, 0
    
    # 유사도 분석 실행
    analyzer = TextSimilarityAnalyzer(threshold=threshold)
    duplicates, dup_map = analyzer.find_duplicates(texts, urls)
    
    if not duplicates:
        logger.info("중복 항목 없음")
        return results, 0
    
    # 삭제할 인덱스 수집
    indices_to_remove = set()
    
    for dup_info in duplicates:
        # valid_indices를 통해 실제 results 인덱스로 변환
        idx_a = valid_indices[dup_info.original_idx]
        idx_b = valid_indices[dup_info.duplicate_idx]
        
        # 원본/중복 결정
        original_idx, duplicate_idx = determine_original_and_duplicate(
            results[idx_a], results[idx_b], idx_a, idx_b
        )
        
        # 이미 삭제 대상인 항목이 원본으로 선택된 경우 스킵
        if original_idx in indices_to_remove:
            continue
        
        indices_to_remove.add(duplicate_idx)
        
        original_url = results[original_idx].get("url", "")
        duplicate_url = results[duplicate_idx].get("url", "")
        logger.info(
            f"중복 삭제: {duplicate_url} (원본: {original_url}, "
            f"유사도: {dup_info.similarity_score:.4f})"
        )
    
    # 중복 항목 삭제 (인덱스 역순으로 삭제해야 인덱스가 밀리지 않음)
    for idx in sorted(indices_to_remove, reverse=True):
        del results[idx]
    
    return results, len(indices_to_remove)


def main():
    parser = argparse.ArgumentParser(description='JSON 파일에 유사도 분석 적용')
    parser.add_argument('json_file', help='수정할 JSON 파일 경로')
    parser.add_argument('--threshold', type=float, default=0.95, help='유사도 임계값 (기본값: 0.95)')
    parser.add_argument('--output', '-o', help='출력 파일 경로 (기본값: 원본 파일 덮어쓰기)')
    args = parser.parse_args()
    
    json_path = Path(args.json_file)
    
    if not json_path.exists():
        logger.error(f"파일이 존재하지 않습니다: {json_path}")
        sys.exit(1)
    
    logger.info(f"JSON 파일 로드 중: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"총 {len(data)}개 항목 로드됨")
    logger.info(f"유사도 임계값: {args.threshold}")
    
    # 유사도 분석 적용
    modified_data, duplicate_count = apply_similarity_analysis(data, args.threshold)
    
    # 결과 저장
    output_path = Path(args.output) if args.output else json_path
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(modified_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 완료: {duplicate_count}개 중복 삭제됨")
    logger.info(f"저장됨: {output_path}")
    
    # 통계 출력
    status_counts = {}
    for item in modified_data:
        status = item.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    logger.info("=== status 통계 ===")
    for status, count in sorted(status_counts.items()):
        logger.info(f"  {status}: {count}개")


if __name__ == "__main__":
    main()
