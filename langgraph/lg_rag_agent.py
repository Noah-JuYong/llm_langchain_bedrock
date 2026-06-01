"""
식사 추천
    - RAG 활용 -> 툴로 차용하여 활용 : @tool => rag 활용( 백터 디비 활용)
        - 환각 형상 방지(할루시네이션)
            - 존재하지 않는 것을 있는 것처럼 창작하여 답변
        - 내부 데이터 접근 불가
            - LLM 관점에서 private한 데이터는 모름
            - 보안 이슈
        - 최신 정보 부재 (LLM이 모르는 정보)

    - 전체 의사결정 구조
        - 랭그래프 활용
    - 필요시 부분적으로 랭체인 고려
        - 프럼프트 => LLM 추론 : 랭체인으로 묶어서 하나의 단위(노드)로 구성 가능함
    - 프럼프트
        - fewshot 활용
"""

# 1. 모듈 가져오기
from langgraph.graph import StateGraph, END
from typing import (
    TypedDict,
    List,
)  # 커스텀 공유메모리(그래프상 노드가 공유하는) [ {}, {}, .. ]
from langchain_core.tools import tool  # 툴 정의할때 사용 데코레이터용
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_aws import ChatBedrockConverse
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv
import os
import boto3

# rag 추가
from tools import rag_search  # rag 도구를 외부에 구성, 커스텀

# 환경변수 로드
load_dotenv()

# LLM 모델 구성 ChatBedrockConverse
llm = ChatBedrockConverse(
    model=os.getenv("MODEL_ID"),
    max_tokens=1000,
    temperature=0.5,
    region_name=os.getenv("AWS_REGION"),
)

# 툴 등록한 LLM 모델 획득
tools = [rag_search]
llm_with_tools = llm.bind_tools(tools)

# 퓨샷 프럼프트 구성
# 샘플의 형태는 다양할 수 있다.
examples = [
    {
        "input": "비 오는날 국물이 땡겨",
        "output": "국룰이죠. 칼국수와 잔치국수가 좋습니다.",
    },
    {
        "input": "다이어트를 위해서 오늘 칼로리가 낮은것으로",
        "output": "관리하시는 군요. 닭가슴 샐러드 드세요.",
    },
]
example_prompt = ChatPromptTemplate.from_messages(
    [("human", "{input}"), ("ai", "{output}")]
)
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=examples, example_prompt=example_prompt
)
final_prompt = ChatPromptTemplate.from_messages(
    [
        # 1. 페르소나
        (
            "system",
            "당신은 센스 있는 식사 메뉴 추천 전문가입니다. 사용자의 상황에 맞춰서 메뉴를 추천하고, 필요하면 도구를 사용하여 실제 식당을 찾으세요.",
        ),
        # 2. 퓨샷 샘플
        few_shot_prompt,
        # 3. 사용자 질문
        ("human", "{messages}"),
    ]
)


# 랭그래프 상태 구성
class AgentState(TypedDict):
    messages: List[BaseMessage]


# 노드 정의
# 사용자의 질의(대화)를 보고, 생각하는 단계 구성 (메뉴 추천, 도구 사용 결정)
def thinking_node(state: AgentState):
    msg = state["messages"]
    chain = final_prompt | llm_with_tools
    res = chain.invoke({"messages": msg})
    return {"messages": [res]}


# 툴, 도구를 사용하기로 결정했다면, 실제 도구 제공 -> 외부기능 -> .... => MCP 연계
def tool_node(state: AgentState):
    pass


# 검색 결과를 바탕으로 최종 답변 추론
# 실제는 다시 thinking_node로 다시 가서 최종 구성해도됨.
def final_answer_node(state: AgentState):
    msg = state["messages"]
    res = llm.invoke(msg)
    return {"messages": res}


# 랭그래프 연결
workflow = StateGraph(AgentState)
workflow.add_node("thinking", thinking_node)
# workflow.add_node("tool", tool_node)
# workflow.add_node("final_answer", final_answer_node)
workflow.set_entry_point(
    "thinking"
)  # 최초 프럼프트를 가지고 추론 진행(직접 ok, 도구 ok)


# 조건부 엣지
# LLM 호출을 통해서 답변 마무리, 도구를 이용하여 마무리 할지등
# def custom_check_tool_node(state: AgentState):
#     pass


# workflow.add_conditional_edges("thinking", custom_check_tool_node)
# workflow.add_edge("tool", "final_answer")  # 도구 사용 => 최종답변노드, 방향성설정
# workflow.add_edge("final_answer", END)  # 그래프이 끝 지정
workflow.add_edge("thinking", END)  # 그래프이 끝 지정
# 흐름 시나리오
# 프럼프트 => thinking => END
# 프럼프트 => thinking => 부족함 => tool => rag => final_answer => END

# 랭그래프객체
app = workflow.compile()

if __name__ == "__main__":
    res = app.invoke({"messages": [HumanMessage(content="가벼운 식사")]})
    print(res["messages"][0].content)
