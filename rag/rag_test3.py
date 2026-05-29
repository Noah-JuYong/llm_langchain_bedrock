"""
저장된 백터 디비 로드
llmㅇㄹ 이용 추론 -> 프롬프트에 rag를 이용한 검색 증강용 데이터 추가하여 추론 진행
    프롬프트 (질의 + rag 검색결과)
랭체인의 체인 구성
"""

from langchain_community.vectorstores import FAISS  # 백터디비
from langchain_aws import BedrockEmbeddings  # 토크나이저
import boto3
from dotenv import load_dotenv
import os
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnablePassthrough,
)  # 질문 검색과 사용자 질문 세팅 등 동시작업
from langchain_core.output_parsers import (
    StrOutputParser,
)  # llm 응답 파싱 -> 문자열 추출

load_dotenv()

tokenizer = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",  # "amazon.titan-embed-text-v1",
    region_name=os.getenv("AWS_REGION"),
)

vector_db = FAISS.load_local(
    "hp-story", tokenizer, allow_dangerous_deserialization=True
)

bedrock_client = boto3.client(
    service_name="bedrock-runtime", region_name=os.getenv("AWS_REGION")
)

llm = ChatBedrock(
    client=bedrock_client,
    model="openai.gpt-oss-120b-1:0",
    model_kwargs={"max_tokens": 512, "temperature": 0.7},
)

prompt = ChatPromptTemplate.from_template("""
다음의 제공된 context(문백, 참고)을 사용하여 질문에 답변해 주세요.
만약, 문맥에서 답을 찾을 수 없다면, "잘 모르겠음"이라고 대답 하세요.

<context>
{context}
<context>

질문: {user_input}
""")

retriever = vector_db.as_retriever(
    search_kwargs={"k": 4}
)  # 유사성 높은 문서(청크) 상위 3개 참조


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


# 각종 기능을 결합 -> 랭체인 파이프라인 구성 LCEL 문법 | 사용해서 열거
rag_chain = (
    {"context": retriever | format_docs, "user_input": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 실행
query = "해리초터와 친한 친구 2명?"
res = rag_chain.invoke(query)
print("== AI 답변 ==")
print(res)
