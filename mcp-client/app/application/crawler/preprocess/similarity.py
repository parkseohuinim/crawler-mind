"""
텍스트 유사도 분석 모듈

TF-IDF + Cosine Similarity를 사용하여 텍스트 간 유사도를 분석하고
중복 콘텐츠를 감지합니다.
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# 유사도 분석에서 제외할 URL 패턴 (공지사항, 이벤트 등)
EXCLUDE_URL_PATTERNS = [
    r"inside\.kt\.com/html/notice/",      # 공지사항
    r"inside\.kt\.com/html/safety/",      # 안전 공지
    r"event\.kt\.com",                    # 이벤트
]


@dataclass
class DuplicateInfo:
    """중복 정보를 담는 데이터 클래스"""
    original_idx: int           # 원본 항목 인덱스
    duplicate_idx: int          # 중복 항목 인덱스
    original_url: str           # 원본 URL
    duplicate_url: str          # 중복 URL
    similarity_score: float     # 유사도 점수 (0.0 ~ 1.0)


class TextSimilarityAnalyzer:
    """
    TF-IDF + Cosine Similarity 기반 텍스트 유사도 분석기
    
    크롤링된 텍스트 콘텐츠 간의 유사도를 분석하여
    중복 항목을 감지합니다.
    """
    
    def __init__(
        self,
        threshold: float = 0.95,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        Args:
            threshold: 중복으로 판단할 유사도 임계값 (기본값: 0.95)
            exclude_patterns: 제외할 URL 패턴 리스트 (기본값: EXCLUDE_URL_PATTERNS)
        """
        self.threshold = threshold
        self.exclude_patterns = exclude_patterns if exclude_patterns is not None else EXCLUDE_URL_PATTERNS
        self.vectorizer = TfidfVectorizer(
            max_features=10000,      # 최대 특성 수
            stop_words=None,         # 한국어이므로 기본 불용어 사용 안함
            ngram_range=(1, 2),      # 유니그램 + 바이그램
            min_df=1,                # 최소 문서 빈도
            max_df=0.95,             # 최대 문서 빈도 (너무 흔한 단어 제외)
        )
    
    def _should_exclude_url(self, url: str) -> bool:
        """
        URL이 제외 패턴에 해당하는지 확인
        
        Args:
            url: 확인할 URL
            
        Returns:
            제외해야 하면 True
        """
        if not url or not self.exclude_patterns:
            return False
        
        for pattern in self.exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def _preprocess_text(self, text: str) -> str:
        """
        텍스트 전처리 (정규화)
        
        Args:
            text: 원본 텍스트
            
        Returns:
            정규화된 텍스트
        """
        if not text:
            return ""
        
        # 마크다운 특수 문자 제거
        text = re.sub(r'[#*_\[\]\(\)`]', ' ', text)
        # 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        # 앞뒤 공백 제거
        text = text.strip()
        # 소문자 변환 (영문의 경우)
        text = text.lower()
        
        return text
    
    def find_duplicates(
        self,
        texts: List[str],
        urls: Optional[List[str]] = None
    ) -> Tuple[List[DuplicateInfo], Dict[int, int]]:
        """
        텍스트 리스트에서 중복 쌍을 탐지
        
        Args:
            texts: 분석할 텍스트 리스트
            urls: 각 텍스트에 대응하는 URL 리스트 (선택적)
            
        Returns:
            Tuple[List[DuplicateInfo], Dict[int, int]]:
                - 중복 정보 리스트
                - 중복 인덱스 -> 원본 인덱스 매핑
        """
        if not texts or len(texts) < 2:
            logger.info("유사도 분석: 텍스트가 2개 미만이므로 건너뜁니다")
            return [], {}
        
        # URL 기본값 설정
        if urls is None:
            urls = [f"item_{i}" for i in range(len(texts))]
        
        # 텍스트 전처리
        processed_texts = [self._preprocess_text(t) for t in texts]
        
        # 제외할 URL 필터링 + 빈 텍스트 필터링
        excluded_count = 0
        valid_indices = []
        for i, t in enumerate(processed_texts):
            if not t.strip():
                continue
            if self._should_exclude_url(urls[i]):
                excluded_count += 1
                continue
            valid_indices.append(i)
        
        valid_texts = [processed_texts[i] for i in valid_indices]
        
        if excluded_count > 0:
            logger.info(f"유사도 분석: {excluded_count}개 URL 제외 (공지사항/이벤트)")
        
        if len(valid_texts) < 2:
            logger.info("유사도 분석: 유효한 텍스트가 2개 미만이므로 건너뜁니다")
            return [], {}
        
        logger.info(f"유사도 분석 시작: {len(valid_texts)}개 텍스트 (임계값: {self.threshold})")
        
        try:
            # TF-IDF 벡터화
            tfidf_matrix = self.vectorizer.fit_transform(valid_texts)
            
            # 코사인 유사도 계산
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
        except Exception as e:
            logger.error(f"TF-IDF 벡터화 실패: {e}")
            return [], {}
        
        # 중복 탐지
        duplicates: List[DuplicateInfo] = []
        duplicate_to_original: Dict[int, int] = {}
        processed_pairs: Set[Tuple[int, int]] = set()
        
        # 이미 중복으로 마킹된 인덱스 추적
        marked_as_duplicate: Set[int] = set()
        
        for i in range(len(valid_texts)):
            if i in marked_as_duplicate:
                continue
                
            for j in range(i + 1, len(valid_texts)):
                if j in marked_as_duplicate:
                    continue
                
                # 이미 처리된 쌍인지 확인
                pair = (min(i, j), max(i, j))
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)
                
                similarity = similarity_matrix[i][j]
                
                if similarity >= self.threshold:
                    # 원본 인덱스로 변환
                    original_idx = valid_indices[i]
                    duplicate_idx = valid_indices[j]
                    
                    duplicate_info = DuplicateInfo(
                        original_idx=original_idx,
                        duplicate_idx=duplicate_idx,
                        original_url=urls[original_idx],
                        duplicate_url=urls[duplicate_idx],
                        similarity_score=round(similarity, 4)
                    )
                    
                    duplicates.append(duplicate_info)
                    duplicate_to_original[duplicate_idx] = original_idx
                    marked_as_duplicate.add(j)
                    
                    logger.info(
                        f"중복 발견: {urls[original_idx]} ↔ {urls[duplicate_idx]} "
                        f"(유사도: {similarity:.4f})"
                    )
        
        logger.info(
            f"유사도 분석 완료: {len(texts)}개 항목 중 "
            f"{len(duplicates)}개 중복 감지"
        )
        
        return duplicates, duplicate_to_original
    
    def get_similarity_score(self, text1: str, text2: str) -> float:
        """
        두 텍스트 간의 유사도 점수 계산
        
        Args:
            text1: 첫 번째 텍스트
            text2: 두 번째 텍스트
            
        Returns:
            유사도 점수 (0.0 ~ 1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        processed_texts = [
            self._preprocess_text(text1),
            self._preprocess_text(text2)
        ]
        
        if not processed_texts[0] or not processed_texts[1]:
            return 0.0
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(processed_texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            return float(similarity[0][0])
        except Exception as e:
            logger.warning(f"유사도 계산 실패: {e}")
            return 0.0


# 기본 분석기 인스턴스
default_analyzer = TextSimilarityAnalyzer(threshold=0.95)
