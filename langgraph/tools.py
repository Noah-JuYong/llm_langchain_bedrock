"""
각종 툴을 모은 모듈
"""

from langchain_core.tools import tool
from rag_store import search_stores


@tool
def rag_search(cate: str) -> str:
    """
    가격, 특징, 메뉴, 카테고리 등 입력받아서 -> 백터 유사도 검색 -> 실제 식당 정보 제공(환각증세 회피)
    """
    res = search_stores(cate)  # 상위 2개만 반환
    return res if res else "관련 식당 정보를 찾을 수 없습니다."
