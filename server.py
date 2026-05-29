"""
백엔드 프로그램
기능
    - ~/chat URL 제공
    - 클라이언트 채팅입력 => ~/chat 요청 => 프롬프트 구성 => bedrock 호출 => 응답 => 처리 => 프론트
"""

from fastapi import FastAPI
from pydantic import BaseModel
from llm import chain

app = FastAPI(title="식사 메뉴 추천 AI")


class UserRequest(BaseModel):
    query: str


@app.post("/chat")
async def chat(req: UserRequest):
    try:
        response = chain.invoke({"user_input": req.query})
        return {"response": response.content}
    except Exception as e:
        return {"reponse": f"에러 {e}"}
