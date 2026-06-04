# 1. 모듈가져오기
import boto3
from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import dotenv
import os

dotenv.load_dotenv()

# LLM 생성, 차후 에이전트별로 역활에 따라 최적의 LLM 배치 할수 있음
# 모든 에이전트가 모두 사용. 페르소나에 따라 역활, 성능 조정할 수 있다
llm = ChatBedrock(
    model_id=os.getenv("MODEL_ID"),
    client=boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION")),
    model_kwargs={"temperature": 0.7},
)

# Agent 1, 신입 개발자를 위한 프럼프트 구성
developer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            '당신은 열정적인 "신입 파이썬 개발자"입니다. 요청받은 기능을 구현하는 코드를 작성하세요. 설명은 최소화 하고 코드 위주로 작성하세요.',
        ),
        ("user", "{request}"),
    ]
)
# Agent 2, 전문 리뷰어를 위한 프럼프트 구성
reviewer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """당신은 까다로운 "전문 개발자"입니다. 신입 개발자가 작성한 코드를 리뷰하세요. 
보안 취약점, 비효율적인 부분, 스타일 가이드를 점검하고 수정 제안을 하세요.
코드가 완벽하자면, "PASS"라고만 답하세요.
""",
        ),
        ("user", "다음 코드를 리뷰해주세요:\n\n{code}"),
    ]
)
# Agent 3, (코드 리뷰를 기반으로 코드를 수정하는 )리파인더를 위한 프럼프트 구성
refiner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            '당신은 열정적인 "신입 파이썬 개발자"입니다. 전문개발자의 리뷰를 보고 코드를 수정하여 다시 제출하세요.',
        ),
        (
            "user",
            "이전 코드:\n{original_code}\n\n리뷰 내용:\n{feedback}\n\n위 내용을 반영하여 개선된 전체 코드를 다시 작성하세요",
        ),
    ]
)


# 랭체인 구성
developer_agent = developer_prompt | llm | StrOutputParser()
reviewer_agent = reviewer_prompt | llm | StrOutputParser()
refiner_agent = refiner_prompt | llm | StrOutputParser()


# 협업 구성
def run_agent_collaboration(topic):
    # 1. 목표 로그(프럼프트) 출력
    print(f"목표 : {topic}\n" + "=" * 50)

    # 2. 신입 개발자 초안 작성
    print(f"\n[신입 개발자] 코드 작성 중..")
    draft_code = developer_agent.invoke({"request": topic})
    # print(f'--\n{draft_code}')

    # 3. 전문 개발자 리뷰 작성 -> PASS 가 나올때가지 반복 처리 가능 -> 반복문 사용
    print(f"\n[전문 개발자] 리뷰 검토 중..")
    feedback = reviewer_agent.invoke({"code": draft_code})

    if feedback == "PASS":
        print(f"--[최종코드]--\n{draft_code}")
    else:
        print(f"--\n{feedback}")
        # 4. 신입 개발자 피드백 반영
        print(f"\n[신입 개발자] 피드백 반영하여 수정 중..")
        final_code = refiner_agent.invoke(
            {"original_code": draft_code, "feedback": feedback}
        )
        print(f"--[최종코드]--\n{final_code}")
    pass


# 구동
if __name__ == "__main__":
    run_agent_collaboration(
        "사용자 비밀번호를 입력받아 DB에 저장하는 간단한 함수(보안 고려)"
    )
