"""
- RAG 기반 검색 기능 제공
- 필요시 백터 디비 초기화(초기 데이터 구축)
    - 인메모리 구성하되, 1회성 설정 (향후 백터 디비는 외부에 구성 필요)
- 검색어 => 백터디비 검색(유사도) => 결과값 반환
"""

from langchain_community.vectorstores import FAISS
from langchain_aws import BedrockEmbeddings
import boto3
from dotenv import load_dotenv
import os

# 환경변수 로드 => 장기키 os 환경변수에 세팅
load_dotenv()

# 임베딩 모델 구성 => 토크나이저 획득
tokenizer = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",  # "amazon.titan-embed-text-v1",
    region_name=os.getenv("AWS_REGION"),
)

# 더미 데이터 구성( LLM이 모르는 사내, 최신 데이터 등)
data = [
    "가게명: 스파이시 웍, 메뉴: 마라탕, 꿔바로우, 특징: 아주 매움, 스트레스 풀림, 가격: 15000원",
    "가게명: 헬시 샐러드, 메뉴: 닭가슴살 샐러드, 샌드위치, 특징: 다이어트, 가벼움, 신선함, 가격: 9000원",
    "가게명: 엄마손 백반, 메뉴: 김치찌개, 제육볶음, 특징: 집밥 스타일, 가성비, 든든함, 가격: 8000원",
    "가게명: 골든 스시, 메뉴: 초밥 세트, 우동, 특징: 고급스러움, 깔끔함, 월급날 추천, 가격: 25000원",
    "가게명: 해장국 천국, 메뉴: 뼈해장국, 순대국, 특징: 국물 진함, 비 오는 날 추천, 가격: 10000원",
]

vector_db = FAISS.from_texts(data, embedding=tokenizer)


def search_stores(query: str, k: int = 2):
    docs = vector_db.similarity_search(query, k)
    print(f"=== [RAG 검색 결과] : {docs}")
    return "\n".join([doc.page_content for doc in docs])


if __name__ == "__main__":
    print("유사도 기반 검색 ", search_stores("가벼운 식사"))
