"""
백터 디비 데이터 구축
"""

# RAG , 백터디비에 자연어->토큰화->저장, 검색(유사도기반)
# 1. 모듈 가져오기
from langchain_community.vectorstores import FAISS  # 백터디비
from langchain_aws import BedrockEmbeddings  # 토크나이저
import boto3
from dotenv import load_dotenv
import os

# 2. 환경변수 로드
load_dotenv()

# 3. 데이터 임시 편성 (llm 모르는/학습하지 않은 최신데이터or사내데이터 가정)
data = [
    "맥도널드 대표 제품은 빅맥이다.",
    "버거킹의 대표 제품은 와퍼이다.",
    "맘스터치의 대표 제품은 훨레버거이다.",
    "롯데리아의 대표 제품은 새우버거이다.",
]

# 4. 임베딩 (임베딩 모델 사용=> 학습 종료됨 것임, 학습시 사용된 다국어의 양 표현의 양으로 이해)
# 자연어 -> 토큰화(분절->백터화->패딩)
tokenizer = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",  # "amazon.titan-embed-text-v1",
    region_name=os.getenv("AWS_REGION"),
)

# 5. 백터 디비에 토큰화된 내용 입력
vector_db = FAISS.from_texts(data, tokenizer)  # 메모리 기반, 디비를 메모리에 로드

# 6. 검색 => 유사도 활용
docs = vector_db.similarity_search("새우?")

# 7. 결과 확인 -> 유사도가 가장 높은 데이터 추출(디비에 저장된)
print(docs[0].page_content)
# docs -> 유사도순으로 나열된 데이터
