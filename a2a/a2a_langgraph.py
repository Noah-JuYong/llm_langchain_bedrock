"""
- 에이전트 => 그래프상 노드
- 에이전트 워크플로우 : 작성->리뷰->체크->수정작성->리뷰->체크...
    - 엣지 구성(규칙, 시작, 종료) :
       - 특정 횟수를 초과하면 종료,
       - 시작 노드 지정
       - PASS 후 종료
       - FAIL이면 다시 작성 -> 순환구조, 2개의 노드로 구성 완료 -> 신입 개발자 에이전트의 진화 (기억만 하면)
- 아킥텍쳐
    - Langgraph
    - State : 대화 내용, 수정 횟수 저장하는 공유 메모리
    - Node
        - Coder Node    : 상태(메모리)를 읽고 코드 신규 생성/수정
        - Reviewer Node : 코드를 검증하고 Pass/Fail 판정(리뷰 내용 전달)
    - Edge
        - entry_point      : Coder Node
        - node_dir         : Coder Node -> Reviewer Node
        - Conditional Edge : Reviewer Node를 타겟, Reviewer의 판정에 따라 Coder Node 갈지, End 갈지 결정

"""

# 1. 모듈가져오기
import boto3
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from typing import Annotated, List, TypedDict
import operator  # 수정 요청한 회수 계산을 위한 처리 => 리액트의 리듀서의 기능 담당(참고)
import dotenv
import os

dotenv.load_dotenv()


# 2. 상태 정의 (메세지-messages, 재시도횟수-iterations, AgentState)
class AgentState(TypedDict):
    # Annotated[ ... ] : 메타데이터 표기
    # 타입힌트 제시, operator.add 전달 -> 상태 업데이트 방식 명확하게 지정
    # 덮어쓰지 말고, 기존 내용에 새로운 내용을 추가하라
    # 대화를 기억하는 방법을 => 누적하여 보관
    messages: Annotated[List[BaseMessage], operator.add]
    # 재시도 회수, 리뷰등을 통해 수정 내용 발생시 최대 순환 수정 회수 제한 비교용
    iterations: int


# 3. LLM 정의
llm = ChatBedrock(
    model_id=os.getenv("MODEL_ID"),
    client=boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION")),
    model_kwargs={"temperature": 0.5},
)


# 4. 노드 정의 -> Agent 정의
#    함수형태로 통합 구성 (프럼프트, 랭체인 구성, 추론요청, 결과반환(생략) )
def coder_node(state: AgentState):
    # 메세지 추출 (최초 사용자, 이전 노드의 출력)
    msg = state["messages"]
    # 프럼프트 구성
    coder_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                '당신은 "초보 파이썬 개발자"입니다. 요청받은 기능을 구현하는 코드를 작성하세요. 리뷰어의 피드백이 있다면 그것을 반영하여 코드를 수정하시오',
            ),
            # 해당 메세제가. HumanMessage, AIMessage, SystemMessage or  형태를 잘 모르겠다 => 알아서 세팅 placeHolder
            ("placeholder", "{messages}"),
        ]
    )
    # 랭체인 구성 (프럼프트=>llm) -> 에이전트 실체
    chain = coder_prompt | llm
    # 추론 행위 요청 -> 실제 추론 행위 실행
    draft_code = chain.invoke({"messages": msg})

    # 응답값 결과 처리 (대화 메세지 정리, 수정 시도 횟수 업데이트)
    return {"messages": [draft_code], "iterations": state.get("iterations", 0) + 1}


def reviewer_node(state: AgentState):
    # 전체 메세지 획득
    msg = state["messages"]
    # 마지막 메세지 획득
    last_msg = state["messages"][-1]  # 코더가 작성한 코드
    # 프럼프트
    reviewer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 까다로운 '전문 개발자'입니다. 신입 개발자가 작성한 코드를 엄격하게 리뷰하세요.\n"
                "보안 취약점, 비효율적인 부분, 스타일 가이드등를 점검하고 수정 제안을 하세요.\n"
                "코드가 완벽하고, 보안 문제가 없다면 반드시 'PASS'라고만 답하세요.\n"
                "문제가 있다면 'FAIL'이라고 적고, 구체적인 수정 지시사항을 남기세요.",
            ),
            ("user", "다음 코드를 리뷰해주세요:\n\n{code}"),
        ]
    )
    # 랭체인 연결
    chain = reviewer_prompt | llm
    # 이전 코드를 삽입하여 프럼프트 구성하여 llm 호출
    review = chain.invoke({"code": last_msg.content})
    # 반복회수 x
    return {"messages": [review]}


# 5. 조건부 엣지 정의
def is_continue(state: AgentState):
    msg = state["messages"]
    # 현 시점의 최종 메세지
    last_msg = state["messages"][-1].content
    # 최종 상태의 시도 횟수
    iterations = state["iterations"]

    # 1. 안정장치, 무제한으로 풀면 => 토큰을 무제한 사용 => 비용 폭탄
    if iterations >= 3:  # 최대 3번만 반복
        print("-- [System] 최대 반복 횟수 도달. 추론 행위를 종료합니다. --")
        return "my_end"

    # 2. 리뷰 통과 여부 체크
    if "PASS" in last_msg:  # 메세지중에 존재함 하면 종료
        print("-- [System] 축하합니다. 리뷰 통과. 추론 행위를 종료합니다. --")
        return "my_end"

    # 3. 다시 수정 작성
    print("-- [System] 리뷰 거절. 다시 작성자에게 보냅니다. (FAIL) --")
    return "gogo"

    pass


# 6. 그래프 구성
# 그래프 뼈대 준비
workflow = StateGraph(AgentState)
# 노드 등록
workflow.add_node("coder", coder_node)
workflow.add_node("reviewer", reviewer_node)
# 시작점 등록
workflow.set_entry_point("coder")
# 방향성 (무조건 이동)
workflow.add_edge("coder", "reviewer")
# 조건부 엣지
workflow.add_conditional_edges(
    "reviewer",
    is_continue,
    {
        "my_end": END,  # 매핑을 통해서 문자열 => 특정 노드, 행위로 대체할 수 있음
        "gogo": "coder",  # 다시 수정
    },
)
# 랭그래프 구성완료
app = workflow.compile()

# 7. 실행
if __name__ == "__main__":
    # 초기 질문
    # 반복 행위를 위해서 비효적인 주문 제시
    initial_input = "리스트에서 중복을 제거하고, 정렬하는 파이썬 함수를 만들어줘. 단, 좀 비효율적으로 작성해줘"
    # 초기 상태값 구성
    inputs = {"messages": [HumanMessage(content=initial_input)], "iterations": 0}
    print("시작요청", inputs)

    # 과정을 확인하고 싶다 => stream
    for output in app.stream(inputs):
        print("-" * 70 + "\n")
        print(output)
        print("\n" + "-" * 70)

    print("수행 완료")
