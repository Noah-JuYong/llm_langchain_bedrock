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
            - api 담당 -> bedrock과 통신 역할
        - langchain
            - 프롬프트 엔지니어링 담당
            - 프롬프트, llm 호출등 파이프라인 구축
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
        source llm_venv/bin/activate
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
- LLM을 활용하여 복잡한 다중 에이전트 시스템, 워크플로우 빌드를 도와주는 오픈소스 프레임웍
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
        - 그래프 전체를 관통하는 공유메모리
        - 노드에서 작업이 완료되고 특정 값, 상태를 공유메모리에 업데이트하면 다른 노드가 이를 엑세스 하여 진행 가능.
- 사용 이유
    - 체인 단방향 
        - looping(되돌아가기)이 어려움
            - 문제 발생시 다시 이전 노드(에이전트, 작업)로 돌아가는 구조를 작성하기 어렵다
        - 사람의 개입시 (승인, ..) -> 일시정지, 재개 구현하기 어렵다
        - 역할 분담
            - 에이전트 규모에 따라서는 협업필요함 -> 단방향을 절차적 진행되기 때문에 협업하는 구조가 수직 구조임
    - 반복 루프, 인간 개입, 다중 에이전트 (A2A) 협업 수월
- 설치
    ```
        # requirements.txt 추가
        langgraph 
    ```