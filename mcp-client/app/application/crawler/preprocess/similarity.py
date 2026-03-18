"""
Text Similarity Analysis Module

TF-IDF(Term Frequency-Inverse Document Frequency)와 Cosine Similarity를
사용하여 텍스트 간 유사도를 분석하고 중복 콘텐츠를 감지하는 모듈입니다.

주요 기능:
    - 크롤링된 텍스트 콘텐츠 간 유사도 분석
    - 중복 콘텐츠 자동 감지 (임계값 기반)
    - 특정 URL 패턴 제외 (공지사항, 이벤트 등)

알고리즘:
    1. 텍스트 전처리 (마크다운 제거, 정규화)
    2. TF-IDF 벡터화 (유니그램 + 바이그램)
    3. Cosine Similarity 계산
    4. 임계값 기반 중복 판정

사용 예시:
    >>> analyzer = TextSimilarityAnalyzer(threshold=0.95)
    >>> duplicates, mapping = analyzer.find_duplicates(texts, urls)
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


# =============================================================================
# 상수 정의
# =============================================================================

# 유사도 분석에서 제외할 URL 패턴
# 공지사항, 이벤트 등 동적으로 변하는 콘텐츠는 중복 분석에서 제외
EXCLUDE_URL_PATTERNS = [
    r"inside\.kt\.com/html/notice/",      # 공지사항
    r"inside\.kt\.com/html/safety/",      # 안전 공지
    r"event\.kt\.com",                    # 이벤트
    r"globalroaming\.kt\.com",            # 로밍 상품 (상품별 페이지 구조가 유사)
    r"product\.kt\.com/wDic/productDetail\.do",  # 부가서비스 상세 (생활편의/금융결제 등 여러 메뉴에서 동일 상품 링크 → hierarchy만 다름)
    r"shop\.kt\.com",                     # KT Shop (모바일/태블릿 등 동일 상품 여러 경로에서 수집)
    r"product\.kt\.com/wDic",   
]


# =============================================================================
# 데이터 클래스
# =============================================================================

@dataclass
class DuplicateInfo:
    """
    중복 콘텐츠 정보를 담는 데이터 클래스입니다.
    
    중복으로 감지된 두 항목의 정보와 유사도 점수를 저장합니다.
    
    Attributes:
        original_idx: 원본 항목의 인덱스 (유지되는 항목)
        duplicate_idx: 중복 항목의 인덱스 (제거 대상)
        original_url: 원본 항목의 URL
        duplicate_url: 중복 항목의 URL
        similarity_score: 유사도 점수 (0.0 ~ 1.0, 1.0이 완전 동일)
    """
    original_idx: int
    duplicate_idx: int
    original_url: str
    duplicate_url: str
    similarity_score: float


# =============================================================================
# 유사도 분석기 클래스
# =============================================================================

class TextSimilarityAnalyzer:
    """
    TF-IDF + Cosine Similarity 기반 텍스트 유사도 분석기입니다.
    
    크롤링된 텍스트 콘텐츠 간의 유사도를 분석하여 중복 항목을 감지합니다.
    대량의 텍스트에서 효율적으로 중복을 찾기 위해 벡터화 기법을 사용합니다.
    
    TF-IDF 설정:
        - max_features: 10,000 (메모리와 성능의 균형)
        - ngram_range: (1, 2) - 단어 단위 + 2-gram으로 문맥 파악
        - max_df: 0.95 - 95% 이상 문서에 등장하는 너무 흔한 단어 제외 (구분력 없음)
    
    Attributes:
        threshold: 중복 판정 임계값 (기본 0.95 = 95% 이상 유사)
        exclude_patterns: 분석 제외 URL 패턴 리스트
        vectorizer: TF-IDF 벡터화 객체
    
    Example:
        >>> analyzer = TextSimilarityAnalyzer(threshold=0.90)
        >>> duplicates, mapping = analyzer.find_duplicates(
        ...     texts=["텍스트1", "텍스트2", "텍스트1과 유사"],
        ...     urls=["url1", "url2", "url3"]
        ... )
    """
    
    def __init__(
        self,
        threshold: float = 0.95,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        TextSimilarityAnalyzer 초기화
        
        Args:
            threshold: 중복으로 판단할 유사도 임계값 (기본값: 0.95)
                      0.0 ~ 1.0 범위, 높을수록 엄격한 판정
            exclude_patterns: 제외할 URL 패턴 리스트 (정규표현식)
                             None이면 EXCLUDE_URL_PATTERNS 사용
        """
        self.threshold = threshold
        self.exclude_patterns = exclude_patterns if exclude_patterns is not None else EXCLUDE_URL_PATTERNS
        
        # --------------------------------------------------------
        # TF-IDF 벡터화 설정
        # --------------------------------------------------------
        self.vectorizer = TfidfVectorizer(
            max_features=10000,      # 최대 특성(단어) 수 제한
            stop_words=None,         # 한국어 불용어 사전 없음
            ngram_range=(1, 2),      # 유니그램(단어) + 바이그램(2단어 조합)
            min_df=1,                # 최소 1개 문서에 등장해야 함
            max_df=0.95,             # 95% 이상 문서에 등장하면 제외 (공통 단어)
        )
    
    def _should_exclude_url(self, url: str) -> bool:
        """
        URL이 분석 제외 패턴에 해당하는지 확인합니다.
        
        공지사항, 이벤트 등 동적으로 변하는 콘텐츠는
        중복 분석에서 제외해야 합니다.
        
        Args:
            url: 확인할 URL 문자열
            
        Returns:
            bool: 제외해야 하면 True, 분석 대상이면 False
        """
        if not url or not self.exclude_patterns:
            return False
        
        for pattern in self.exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def _preprocess_text(self, text: str) -> str:
        """
        텍스트 전처리 (정규화)를 수행합니다.
        
        TF-IDF 벡터화 전에 텍스트를 정규화하여
        일관된 비교가 가능하도록 합니다.
        
        처리 단계:
            1. 마크다운 특수 문자 제거 (#, *, _, [], (), `)
            2. 연속 공백을 단일 공백으로 변환
            3. 앞뒤 공백 제거
            4. 소문자 변환 (영문의 경우)
        
        Args:
            text: 원본 텍스트 문자열
            
        Returns:
            str: 정규화된 텍스트 문자열
        """
        if not text:
            return ""
        
        # --------------------------------------------------------
        # 마크다운 특수 문자 제거
        # 유사도 비교 시 포맷팅 차이로 인한 오차 방지
        # --------------------------------------------------------
        text = re.sub(r'[#*_\[\]\(\)`]', ' ', text)
        
        # --------------------------------------------------------
        # 공백 정규화
        # --------------------------------------------------------
        text = re.sub(r'\s+', ' ', text)  # 연속 공백 → 단일 공백
        text = text.strip()                # 앞뒤 공백 제거
        
        # --------------------------------------------------------
        # 소문자 변환 (영문 대소문자 차이 무시)
        # --------------------------------------------------------
        text = text.lower()
        
        return text
    
    def find_duplicates(
        self,
        texts: List[str],
        urls: Optional[List[str]] = None
    ) -> Tuple[List[DuplicateInfo], Dict[int, int]]:
        """
        텍스트 리스트에서 중복 쌍을 탐지합니다.
        
        모든 텍스트 쌍의 유사도를 계산하고, 임계값 이상인 쌍을
        중복으로 판정합니다. 먼저 등장한 항목을 원본으로,
        나중에 등장한 항목을 중복으로 처리합니다.
        
        알고리즘:
            1. 텍스트 전처리 및 필터링
            2. TF-IDF 벡터화 (N개 텍스트 → N x M 행렬)
            3. 코사인 유사도 계산 (N x N 행렬)
            4. 임계값 이상 쌍 추출
        
        시간 복잡도: O(N²) - N개 텍스트의 모든 쌍 비교
        
        Args:
            texts: 분석할 텍스트 리스트
            urls: 각 텍스트에 대응하는 URL 리스트 (선택적)
                  None이면 "item_0", "item_1", ... 형태로 자동 생성
            
        Returns:
            Tuple[List[DuplicateInfo], Dict[int, int]]:
                - duplicates: 중복 정보 리스트
                - duplicate_to_original: 중복 인덱스 → 원본 인덱스 매핑
        """
        # --------------------------------------------------------
        # 입력 검증: 최소 2개 이상의 텍스트 필요
        # --------------------------------------------------------
        if not texts or len(texts) < 2:
            logger.info("[find_duplicates] Skip: less than 2 texts")
            return [], {}
        
        # URL 기본값 설정
        if urls is None:
            urls = [f"item_{i}" for i in range(len(texts))]
        
        # --------------------------------------------------------
        # 1단계: 텍스트 전처리
        # --------------------------------------------------------
        processed_texts = [self._preprocess_text(t) for t in texts]
        
        # --------------------------------------------------------
        # 2단계: 필터링
        # - 빈 텍스트 제외
        # - 제외 패턴 URL 제외 (공지사항, 이벤트 등)
        # --------------------------------------------------------
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
            logger.info(f"[find_duplicates] Excluded {excluded_count} URLs (notice/event)")
        
        if len(valid_texts) < 2:
            logger.info("[find_duplicates] Skip: less than 2 valid texts")
            return [], {}
        
        logger.info(f"[find_duplicates] Start: {len(valid_texts)} texts, threshold={self.threshold}")
        
        # --------------------------------------------------------
        # 3단계: TF-IDF 벡터화 및 유사도 계산
        # --------------------------------------------------------
        try:
            # TF-IDF 벡터화: 텍스트 → 수치 벡터
            tfidf_matrix = self.vectorizer.fit_transform(valid_texts)
            
            # 코사인 유사도: 모든 쌍의 유사도 행렬 계산
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
        except Exception as e:
            logger.error(f"[find_duplicates] TF-IDF vectorization failed: {e}")
            return [], {}
        
        # --------------------------------------------------------
        # 4단계: 중복 쌍 탐지
        # 유사도가 임계값 이상인 쌍을 찾음
        # --------------------------------------------------------
        duplicates: List[DuplicateInfo] = []
        duplicate_to_original: Dict[int, int] = {}
        processed_pairs: Set[Tuple[int, int]] = set()
        
        # 이미 중복으로 마킹된 인덱스 추적 (연쇄 중복 방지)
        marked_as_duplicate: Set[int] = set()
        
        for i in range(len(valid_texts)):
            # 이미 중복으로 마킹된 항목은 원본이 될 수 없음
            if i in marked_as_duplicate:
                continue
                
            for j in range(i + 1, len(valid_texts)):
                if j in marked_as_duplicate:
                    continue
                
                # 이미 처리된 쌍인지 확인 (중복 처리 방지)
                pair = (min(i, j), max(i, j))
                if pair in processed_pairs:
                    continue
                processed_pairs.add(pair)
                
                similarity = similarity_matrix[i][j]
                
                # 임계값 이상이면 중복으로 판정
                if similarity >= self.threshold:
                    # 유효 인덱스 → 원본 인덱스로 변환
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
                    
                    logger.debug(
                        f"[find_duplicates] Found: {urls[original_idx]} <-> {urls[duplicate_idx]} "
                        f"(score={similarity:.4f})"
                    )
        
        logger.info(f"[find_duplicates] Done: {len(duplicates)} duplicates in {len(texts)} items")
        
        return duplicates, duplicate_to_original
    
    def get_similarity_score(self, text1: str, text2: str) -> float:
        """
        두 텍스트 간의 유사도 점수를 계산합니다.
        
        단일 쌍의 유사도만 필요할 때 사용합니다.
        대량 비교 시에는 find_duplicates()가 더 효율적입니다.
        
        Args:
            text1: 첫 번째 텍스트 문자열
            text2: 두 번째 텍스트 문자열
            
        Returns:
            float: 유사도 점수 (0.0 ~ 1.0)
                   - 0.0: 완전히 다름
                   - 1.0: 완전히 동일
                   - 입력이 비어있으면 0.0 반환
        
        Example:
            >>> analyzer = TextSimilarityAnalyzer()
            >>> score = analyzer.get_similarity_score("안녕하세요", "안녕하세요!")
            >>> print(f"{score:.4f}")  # 0.9xxx
        """
        # 빈 입력 처리
        if not text1 or not text2:
            return 0.0
        
        # 전처리
        processed_texts = [
            self._preprocess_text(text1),
            self._preprocess_text(text2)
        ]
        
        # 전처리 후 빈 텍스트 확인
        if not processed_texts[0] or not processed_texts[1]:
            return 0.0
        
        try:
            # TF-IDF 벡터화 및 유사도 계산
            tfidf_matrix = self.vectorizer.fit_transform(processed_texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
            return float(similarity[0][0])
        except Exception as e:
            logger.warning(f"[get_similarity_score] Error: {e}")
            return 0.0


# =============================================================================
# 기본 인스턴스
# =============================================================================

# 기본 분석기 인스턴스 (임계값 95%)
# 모듈 임포트 시 바로 사용 가능: from similarity import default_analyzer
default_analyzer = TextSimilarityAnalyzer(threshold=0.95)
