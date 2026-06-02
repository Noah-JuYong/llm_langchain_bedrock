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

- 이슈
    - 도구 사용은 LLM이 자율적으로 진행
    - 현재는 LLM 스스로 해결하는 이슈, 확인후 정정
    - 페르소나에서 강력하게 도구 사용을 강제하면 일단 도구 사용 작동함 (참고)
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
        "output": "관리하시는군요. 닭가슴, 샐러드 드세요.",
    },
]
example_prompt = ChatPromptTemplate.from_messages(
    [
        ("human", "{input}"),
        ("ai", "{output}"),
    ]
)
few_shot_prompt = FewShotChatMessagePromptTemplate(
    examples=examples, example_prompt=example_prompt
)
final_prompt = ChatPromptTemplate.from_messages(
    [
        # 1. 페르소나
        (
            "system",
            "당신은 센스 있는 식사 메뉴 추천 전문가입니다. 사용자의 상황에 맞춰서 메뉴를 추천하고, 필요하면 도구를 사용하여 식당을 찾으세요.",
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
    # 사용자 입력내용 추출(획득)
    msg = state[
        "messages"
    ]  # 사용자 -> UI -> 입력 -> 엔터 -> 서버 -> 랭그래프객체.invoke(프럼프트)
    # 랭체인 구성 (일반향) : 퓨샷 프럼프트(페르소나, 샘플 구성되어 있음)
    chain = final_prompt | llm_with_tools
    # 1차 추론 요청 진행
    res = chain.invoke({"messages": msg})
    # 응답 결과 반환
    return {"messages": [res]}


# 툴, 도구를 사용하기로 결정했다면, 실제 도구 제공 -> 외부기능 -> .... => MCP 연계
def tool_node(state: AgentState):
    # RAG를 이용한 검색 증강 => LLM이 모르는 데이터를 프럼프트에 반영하여 추론 요청하는 과정
    last_msg = state["messages"][-1]
    print("tool_node 호출 : 툴 사용 LLM이 응답", last_msg.tool_calls)
    if last_msg.tool_calls:
        # 툴획득
        # 등록된 도구가 1개라는 것을 알기 대문에 0으로 고정 => 도구가 많아지면 상황에 따른 선택 부여(용도는 정해져 있음)
        tool = last_msg.tool_calls[0]
        # last_msg.tool_calls 세팅되었을대 값 (아래 샘플)
        """
        last_msg.tool_calls[
            {
                'name':'rag_search',
                'args':{'cate':'가벼운 식사'},
                'id'  :'tooluse-zfwefewfwecvwerfwec',
                'type':'tool_call'
            }
        ]
        """
        # 툴사용(rag 수행)
        result = rag_search.invoke(tool["args"])  # 사용자가 질문한 내용을 추출하여 호출
        print("RAG 호출 결과 : ", result)
        return {
            "messages": [
                HumanMessage(
                    content=f"[사내데이터 검색결과]: {result}\n 제공된 정보를 기반으로 최종 답변을 해주세요."
                )
            ]
        }
    # 보험용
    return {"messages": []}


# 검색 결과를 바탕으로 최종 답변 추론
# 실제는 다시 thinking_node로 다시 가서 최종 구성해도됨.
def final_answer_node(state: AgentState):
    msg = state["messages"]
    res = llm.invoke(
        msg
    )  # 툴이 필요 없거나, 툴을 사용했거나 => 답변에 충족하는 내용을 가지고 있으므로 llm으로 처리
    return {"messages": [res]}
    pass


# 랭그래프 연결
workflow = StateGraph(AgentState)
workflow.add_node("thinking", thinking_node)
workflow.add_node("tool", tool_node)
workflow.add_node("final_answer", final_answer_node)
workflow.set_entry_point(
    "thinking"
)  # 최초 프럼프트를 가지고 추론 진행(직접 ok, 도구 ok)


# 조건부 엣지
# LLM 호출을 통해서 답변 마무리, 도구를 이용하여 마무리 할지등
def custom_check_tool_node(state: AgentState):
    # thinking 작업 마무리 -> 답변이 충분 -> END
    # 부족하니 => 도구 => tool : (컨텍스트 추가(검색증강을 통해서 부속적인 내용 추가) => LLM 추론)
    # 마지막메세지 : AI응답 => tool_calls 값 체크
    last_msg = state["messages"][-1]
    # 툴 사용여부 체크
    if last_msg.tool_calls:
        print("툴 사용 필요")
        return "tool"
    # 툴 사용 필요 없다 => 답변이 완벽하다 => END
    return END


workflow.add_conditional_edges("thinking", custom_check_tool_node)
workflow.add_edge("tool", "final_answer")  # 도구 사용 => 최종답변노드, 방향성설정
workflow.add_edge("final_answer", END)  # 그래프이 끝 지정, 추론의 마무리

# 흐름 시나리오
# 프럼프트 => thinking => END
# 프럼프트 => thinking => 부족함 => tool => rag => final_answer => END

# 랭그래프객체
랭그래프객체 = workflow.compile()

if __name__ == "__main__":
    res = 랭그래프객체.invoke({"messages": "배가 불러"})  # 가벼운 식사 => 사용자 입력
    print(res)
