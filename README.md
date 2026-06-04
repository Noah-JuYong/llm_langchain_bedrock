# 목표 (기본형)
    - llm 기반 서비스 구성
    - 주요기능
        - bedrock 사용 -> llm 호출 담당
        - llm 모델
            - claude, openai, google등 사용
        - 웹 프런트 화면 
            - streamlit 사용 (프런트 담당)
            - 파이썬으로만 구성 (html, css, js x)
            - 채팅화면
        - 백엔드
            - fastapi 구성
            - 화면 x
            - api 담당 -> bedrock과 통신 역활
        - langchain
            - 프럼프트 엔지니어링 담당
            - 프럼프트 , llm 호출등 파이프라인 구축
    - 서비스 주제
        - 식사 메뉴 해결사 (메뉴 추천)

# 목표 (확장형)
    - RAG
    - vectorDB
    - MCP
    - chain -> graph 파이프라인 마이그레이션
    - Agent
    - A2A

# 구조
/
L .env                  : 환경변수, bedrock 키
L .gitignore            : 가상환경, .env 등 추가하여 git 미반영
L requirements.txt      : 패키지
L app.py                : 프런트, streamlit
L server.py             : 백엔드, fastapi
L llm/__init__.py             : bedrock 통신 모듈

# 세팅
- 가상환경 구축
    ```
        python -m venv llm_venv        
    ```
- 활성화
    ```
        # 윈도우
        .\llm_venv\Scripts\activate
        # 맥
        source llm_venv\bin\activate
    ```
- .gitignore 내용 세팅
    - 가상환경 배제
    ```  
        ...
        # 가상환경제외
        llm_venv
    ```
- 패키지 설치
    ```
        (llm_venv)> pip install -r requirements.txt
    ```
    ```
        # 백엔드 구성, bedrock 호출
        fastapi
        # fastapi 구동
        uvicorn
        # 프런트 구성
        streamlit
        # 프런트 -> 백엔드 요청
        requests
        # AWS SDK
        boto3
        # 랭체인 AWS 전용
        langchain-aws
        # 랭체인 코어 라이브러리
        langchain-core
        # 환경변수, .env 로드
        python-dotenv
    ```

# 환경변수
- .env
    ```
        AWS_REGION=us-east-1
        MODEL_ID=google.gemma-3-27b-it
        AWS_BEARER_TOKEN_BEDROCK=...
    ```

# 구동
- 백엔드 : server.py
    ```
        uvicorn server:app --reload --port 8000
    ```
    - 테스트 
        - http://127.0.0.1:8000/chat post 방식 요청

- 프런트 : app.py
    ```
        streamlit run app.py
    ```

# RAG
- 검색 증강 <- fewshot을 일부 샘플, RAG 관련 데이터를 (유사도검사) 정밀하게 추출하여 제공
    - llm이 한번도 접하지 못한 데이터 (사내 데이터, 개인 데이터, llm 생성 이후로 발생된 데이터, ..) 활용
    - 데이터에 대한 보안 이슈등 llm 학습시 동원됮 않는 데이터를 추론하기에는 한계 존재
        - 파인튜닝 -> 신규 학습, 모델 공개등 -> 신뢰x 진행하기 어려움. 비용 많이 발생
        - RAG  -> 추론 요청시 사내 데이터를 추가하여 전달 -> llm 제공 회사의 신뢰성
        - 최신 움직임
            - 에지 -> 사내 구축 -> 클라우드 중심 => 온프레미스, 디바이스 AI모델 이동 움직임 => `델`에서 입증 
                -> 한달 내 : CPU 중요성(`에이전트` 작동)이 GPU보다 커지고 있음
                    -> 인텔, AMD, ARM 설계=>제작/50% 점유, 엔비디아 CPU 제작
        - 백터디비!!

- 사내 데이터 노출 X, llm 강력한 추론/생성등 능력치 사용 => rag 도구 사용
- llm 훈련하지 않는 최신 정보, 기업 내부 데이터에 대한 정확하고 신뢰성 있는 답변/응답을 생성할수 있는 기술
- 파인튜닝(재학습)에 비해 비용 효율적임 -> 백터 디비 업데이트 해주면됨
- 추가 설치 패키지 => requirements.txt 추가
```
    langchain-community
    faiss-cpu
    langchain
```

# VECTOR db
- 장기기억, rag를 위한 저장소/검색기능, 유사도 기능
- 데이터 : 자연어 -> 토크나이저(제품 선정) -> 백터화
- 제품
    - Pinecone : 무료 계정당 1개 디비 생성
    - Milvus:
    - Qdrant:
    - 메모리 기반
        - Chroma
        - FAISS : 메타
    - aws 
    - ...
- 토크나이저 => BedrockEmbedding => 모델 교체

# 랭그래프(LangGraph)
- LLM을 활요하여 복잡한 다중 에이전트 시스템, 워크플로우 빌드를 도와주는 오픈소스 프레임웍
- 랭체인에서 만든 라이브러리
- 비교
    - 워크플로우 일직선 : langchain
    - 워크플로우 그래프 : langgraph
- 구성
    - 노드(node) : 
        - 실제 수행할 작업(task, 액션) 단위
        - 프럼프트 실행, 파이썬 코드 실행, api 호출, ...
        - 특정 수행 목적을 가진 에이전트(어떤 작업을 수행하는 단위, 규모는 제각각)
    - 엣지(edge) : 
        - 노드와 노드를 `연결`하는 경로
        - A 노드의 작업이 끝나면 B 노드로 이동하여 작업 시작해라 -> `규칙` 규정
        - 조건에 따라 특정 노드로 이동하여 작업 진행 -> `조건`부 엣지
    - 상태관리 (state) : 
    `   - 그래프 전체를 관통하는 공유메모리
        - 노드에서 작업이 완료되고 특정 값, 상태를 공유메모리에 업데이트하면 다른 노드가 이를 엑세스 하여 진행 가능.
- 사용 이유
    - 체인 단방향 
        - looping(되돌아가기)이 어려움
            - 문제 발생시 다시 이전 노드(에이전트, 작업)로 돌아가는 구조를 작성하기 어렵다
        - 사람의 개입시 (승인, ..) -> 일시정지, 재개 구현하기 어렵다
        - 역활 분담
            - 에이전트 규모에 따라서는 협업필요함 -> 단반향을 절차적 진행되기 때문에 협업하는 구조가 수직 구조임
    - 반복 루프, 인간 개입, 다중 에이전트 (A2A) 협업 수월
- 설치
    ```
        # requirements.txt 추가
        langgraph 
    ```

# Agent, A2A(Agent - to - Agent) 아킥텍쳐
- 개요
    - 어떤 작업은 하나의 거대한 모델(llm)이 모두 처리 하는 것이 아님
    - 전문화된 페르소나를 가진 에이전트들이 서로 결과물을 입력받아서 작업을 고도화 하는 방식(협업)
        - User Task : 사용자가 주제를 던짐
        - Agent A (Developer) : 요청을 받아서 1차 코드 작성
        - Agent B (Reviewer)  : 앞에서 작성된 코드를 받아서 분석, 보안 취약점등등 체크 리뷰(지적)
        - Feedback Loop : Agent A는 Agent B의 리뷰를 바탕으로 코드를 수정 => 반복
- 구성
    - A2A_langchain
    - A2A_langgraph
- 특징
    - 순차적 협업 패턴
        - 에이전트 정의
            - Developer Agent : '구현'에 집중하는 프럼프트를 가짐. 창의적, 생상적 등등 역활
            - Reviewer Agent  : '비판', '분석','평가'에 집중하는 프럼프트를 가짐. 논리적, 검증적인 등등 역활
            - 체크 : Claude/코덱스등는 성능이 너무 좋아서 -> 한번에 완료될수도 잇으므로 -> xxx한 주니어 개발자로 설정
        - 메세지 전달
            - 다른 에이전트의 출력이 다른 에이전트의 입력이 됨
        - 피드백 루프
            - 일을 지시하고 마무리 되는것인 아니라, 리뷰 결과에 따라 행동 결정
            - 카운트 부여 -> 반복 회수를 제한 할수 있음

# MCP (Model Context Protocol)
- 개요
    - AI 기업 앤프로픽 최초 개발 (2024.11)
    - 오픈소스 프로토콜
- 목적
    - LLM 활용의 한계   
        - 특정 데이터, 개발 도구(DB등) 연결할려면 개별적이 API 커스텀 구성하여 연동 코드 매번 작성, 라이브러리 구축필요
        - 시간/비용 발생. 비효율적
        - 이것을 표준화시켜서 (USB-C)와 같은 방식으로 한번만 구현하면 어떤 앱이든 플러그인 형태로 바로 연결되도록 고안
    - 소유권
        - 오픈소스로 개발 -> 2025.12 -> 리눅스재단 예하 -> 에이전틴 AI 재단 이관
            - 참여 : 오픈AI, 구글 딥마인드, MS, 젯브레인,... 
        - https://github.com/modelcontextprotocol
    - 결론
        - AI 어플리케이션의 도구(툴) 통합을 표준화, 간소화