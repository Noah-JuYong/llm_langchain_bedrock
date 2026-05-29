"""
bedrock 을 이용한 llm 호출
"""

import boto3
from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
import os

load_dotenv()
print(os.getenv("AWS_REGION"))
print(os.getenv("MODEL_ID"))
print(os.getenv("AWS_BEARER_TOKEN_BEDROCK"))

bedrock_client = boto3.client(
    service_name="bedrock-runtime", region_name=os.getenv("AWS_REGION")
)
llm = ChatBedrockConverse(
    client=bedrock_client, model=os.getenv("MODEL_ID"), max_tokens=512, temperature=0.7
)

fewshot_samples = [
    {
        "input": "오늘 점심 메뉴 추천해줘. 비가 오고 있어서 나가기 귀찮아. 혼자 먹을 거야.",
        "output": "비 오는 날, 집에서 편하게 즐길 수 있는 **'따뜻한 김치수제비와 해물파전'**을 추천합니다! 빗소리와 부침개 부치는 소리가 비슷해 감성을 자극하고, 칼칼한 국물은 가라앉은 기분을 전환해줄 거예요. 배달 앱을 이용하신다면 근처 칼국수 맛집의 세트 메뉴를 확인해보세요.",
    },
    {
        "input": "직장 동료들 5명이랑 저녁 회식 메뉴 골라줘. 날씨는 맑고 다들 기분 최고야! 고기 종류면 좋겠어.",
        "output": "기분 좋은 저녁 회식에는 역시 **'제주 흑돼지 오겹살'**이 제격입니다! 5명이라면 고기를 직접 구워주는 전문점에 가셔서 편하게 대화를 나눠보세요. 맑은 날씨에 어울리는 시원한 '김치말이 국수'를 후식으로 곁들이면 완벽한 마무리가 될 거예요.",
    },
    {
        "input": "내일 점심에 데이트가 있어. 날씨는 화창하대. 여자친구가 가벼운 걸 먹고 싶어 하는데 분위기 좋은 메뉴 없을까?",
        "output": "화창한 날 데이트라면 신선한 **'부라타 치즈 샐러드를 곁들인 바질 페스토 파스타'**는 어떨까요? 건강하고 가벼우면서도 색감이 예뻐 사진 찍기에도 좋습니다. 통창이 있는 이탈리안 레스토랑에서 화이트 와인 한 잔을 곁들이면 로맨틱한 분위기가 배가될 거예요.",
    },
    {
        "input": "금요일 퇴근길인데 너무 스트레스 받아. 매운 거 먹고 싶은데 혼자 먹기 좋은 저녁 메뉴 추천해줘.",
        "output": "일주일 동안 정말 고생 많으셨어요! 스트레스를 한 방에 날려줄 **'마라탕과 꿔바로우 소(小)'**를 추천합니다. 원하는 재료를 듬뿍 넣어 아주 매운 단계로 즐겨보세요. 얼얼한 매운맛이 엔도르핀을 돌게 해줄 거예요. 시원한 캔맥주 하나 사서 집에서 넷플릭스를 보며 드시는 건 어떨까요?",
    },
]

fewshot_sample_format = prompt = ChatPromptTemplate.from_messages(
    [("human", "{input}"), ("ai", "{output}")]
)

fewshot_prompt = FewShotChatMessagePromptTemplate(
    examples=fewshot_samples, example_prompt=fewshot_sample_format
)

last_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            '당싱는 직장인들의 식사 메뉴 고민을 해결해주는 계획적인 "메뉴 추천 마스터"입니다',
        ),
        fewshot_prompt,
        ("human", "{user_input}"),
    ]
)


chain = last_prompt | llm
