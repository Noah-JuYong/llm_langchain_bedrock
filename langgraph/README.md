# LangGraph 학습 정리

## 목차
1. [LangGraph란?](#1-langgraph란)
2. [기본 구조 (lg_test1.py)](#2-기본-구조-lg_test1py)
3. [LLM + Tool 연동 (lg_test2.py)](#3-llm--tool-연동-lg_test2py)
4. [단기 기억(Memory) 추가 (lg_test3.py)](#4-단기-기억memory-추가-lg_test3py)
5. [RAG 벡터DB 구성 (rag_store.py)](#5-rag-벡터db-구성-rag_storepy)
6. [RAG를 Tool로 변환 (tools.py)](#6-rag를-tool로-변환-toolspy)
7. [전체 에이전트 통합 (lg_rag_agent.py)](#7-전체-에이전트-통합-lg_rag_agentpy)
8. [전체 흐름 요약](#8-전체-흐름-요약)

---

## 1. LangGraph란?

LangGraph는 LLM 기반 애플리케이션을 **그래프(노드 + 엣지)** 구조로 설계할 수 있게 해주는 프레임워크다.

### 핵심 개념

| 개념 | 설명 |
|---|---|
| **Node(노드)** | 하나의 작업 단위. Python 함수로 정의. 상태를 입력받아 새 상태를 반환 |
| **Edge(엣지)** | 노드 간 이동 방향 설정. `A → B` 형태 |
| **Conditional Edge** | 조건에 따라 다음 노드가 달라지는 분기 엣지 |
| **State(상태)** | 노드들이 공유하는 메모리. `TypedDict`로 정의 |
| **StateGraph** | 상태를 공유하는 그래프 객체 |
| **compile()** | 그래프를 실행 가능한 앱으로 변환 |
| **invoke()** | 동기 실행 (결과가 나올 때까지 대기) |
| **stream()** | 비동기 실행 (노드 단위로 중간 결과를 스트리밍) |

### LangGraph vs LangChain

```
LangChain : 프롬프트 → LLM → 출력  (선형 파이프라인)
LangGraph : 노드 ↔ 노드 ↔ 노드    (사이클, 분기, 조건 가능한 그래프)
```

LangGraph는 LangChain의 상위 개념으로, 복잡한 에이전트 흐름(반복, 조건, 도구 사용)을 구조화할 때 사용한다.

---

## 2. 기본 구조 (`lg_test1.py`)

### 그래프 흐름

```
[START] → T1(add_prefix) → T2(add_surfix) → [END]
```

### 핵심 코드 설명

```python
# 상태 정의 : 노드들이 공유하는 공유 메모리 구조
class CustomState(TypedDict):
    msg: str

# 노드 정의 : 상태를 받아서 새 상태를 반환하는 함수
def add_prefix(status: CustomState):
    return {"msg": "헬로 " + status["msg"]}

def add_surfix(status: CustomState):
    return {"msg": status["msg"] + " !!"}

# 그래프 구성
workflow = StateGraph(CustomState)   # 상태 타입 지정
workflow.add_node("T1", add_prefix)  # 노드 등록
workflow.add_node("T2", add_surfix)
workflow.set_entry_point("T1")       # 시작 노드 지정
workflow.add_edge("T1", "T2")        # 노드 간 연결
workflow.add_edge("T2", END)         # 종료 지점 연결
app = workflow.compile()             # 실행 가능한 앱으로 변환

# 실행
res = app.invoke({"msg": "랭그래프"})
# 결과: {"msg": "헬로 랭그래프 !!"}
```

### 실행 결과

```
{"msg": "랭그래프"}
    → T1 실행 → {"msg": "헬로 랭그래프"}
    → T2 실행 → {"msg": "헬로 랭그래프 !!"}
```

### 정리
- `TypedDict`로 상태 구조를 명시적으로 정의한다
- 각 노드는 전체 상태를 받고, 변경할 키만 골라서 반환하면 된다
- `compile()` 이후에만 `invoke()`/`stream()` 실행 가능

---

## 3. LLM + Tool 연동 (`lg_test2.py`)

### 그래프 흐름

```
[START] → chatbot → (조건부 분기)
                    ├─ LLM이 직접 답변 → [END]
                    └─ LLM이 도구 필요 → tools → chatbot → ...
```

### MessagesState란?

`lg_test1.py`의 `CustomState` 대신 LangGraph 내장 상태를 사용한다.

```python
from langgraph.graph import MessagesState

# MessagesState 내부 구조 (라이브러리가 자동 제공)
class MessagesState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    #                                       ↑ 메시지를 덮어쓰지 않고 누적(append)하는 리듀서
```

- `add_messages` 리듀서 덕분에 새 메시지를 반환하면 기존 목록에 자동으로 추가된다
- 반드시 `list[BaseMessage]` 형태로 전달해야 한다

### @tool 데코레이터

```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """두 수를 곱한 후 반환"""   # ← 이 docstring을 LLM이 읽고 도구의 용도를 이해함
    return a * b
```

- `@tool`을 붙이면 함수가 LLM이 인식할 수 있는 JSON 스키마 형태로 자동 변환된다
- **docstring이 중요**: LLM은 이 설명을 보고 언제 이 도구를 써야 하는지 판단한다

### LLM에 Tool 등록

```python
tools = [multiply]
llm_with_tools = llm.bind_tools(tools)
# → "너는 이런 도구들을 사용할 수 있어"라고 LLM에게 알려주는 것
```

### ToolNode와 tools_condition

```python
from langgraph.prebuilt import ToolNode, tools_condition

workflow.add_node("tools", ToolNode(tools))  # 도구 실행 노드 자동 생성
workflow.add_conditional_edges(
    "chatbot",
    tools_condition,   # chatbot 응답 분석 → 도구 필요 여부 자동 판단
)
workflow.add_edge("tools", "chatbot")  # 도구 실행 후 다시 chatbot으로 복귀 (사이클)
```

| 상황 | 다음 노드 |
|---|---|
| LLM이 텍스트로 직접 답변 | `END` |
| LLM이 도구 호출 요청 | `tools` → `chatbot` → (반복) |

### 핵심 코드 (노드 함수)

```python
def chatbot_node(state: MessagesState):
    res = llm_with_tools.invoke(state["messages"])
    return {"messages": [res]}   # 리스트로 감싸야 함
```

### 실행 예시

```
유저: "3과 7을 곱하면?"
→ chatbot: LLM이 multiply 도구 필요하다고 판단
→ tools: multiply(3, 7) 실행 → 21
→ chatbot: 21을 받아서 "3과 7의 곱은 21입니다" 최종 답변
→ END
```

---

## 4. 단기 기억(Memory) 추가 (`lg_test3.py`)

### lg_test2.py와의 차이점

`lg_test2.py`와 그래프 구조는 동일하고, **대화 기억 기능**만 추가된다.

### MemorySaver

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()   # RAM에 대화 기록 저장 (프로그램 종료 시 삭제)
app = workflow.compile(checkpointer=memory)  # 컴파일 시 메모리 주입
```

| 저장소 | 특징 |
|---|---|
| `MemorySaver` | RAM 저장, 빠름, 휘발성 (개발/테스트용) |
| 외부 벡터DB | 디스크/서버 저장, 영구적 (실제 서비스용) |

### thread_id : 사용자별 대화 분리

```python
config = {"configurable": {"thread_id": "user-1"}}
# thread_id가 같으면 → 같은 대화 히스토리 공유
# thread_id가 다르면 → 완전히 독립된 대화

app.stream(prompt, stream_mode="values", config=config)
#                                         ↑ config를 반드시 함께 전달해야 기억 동작
```

### 동작 예시

```
[thread_id: "user-1"]
유저: "내 이름은 철수야"      → LLM: "안녕하세요, 철수님!"
유저: "내 이름이 뭐야?"       → LLM: "철수님이라고 하셨습니다."  ← 기억함

[thread_id: "user-2"]
유저: "내 이름이 뭐야?"       → LLM: "이름을 말씀해주시지 않았습니다."  ← 다른 세션
```

---

## 5. RAG 벡터DB 구성 (`rag_store.py`)

### RAG가 필요한 이유

| 문제 | 설명 | RAG 해결 방법 |
|---|---|---|
| **환각(Hallucination)** | LLM이 없는 정보를 있는 것처럼 창작 | 실제 DB에서 검색한 정보를 근거로 답변 |
| **내부 데이터 접근 불가** | LLM은 사내/비공개 데이터를 모름 | 사내 데이터를 벡터DB에 저장해서 검색 |
| **최신 정보 부재** | LLM의 학습 데이터에는 최신 정보가 없음 | 최신 데이터를 벡터DB에 지속 업데이트 |

### 전체 구조

```
원본 텍스트 데이터
    → BedrockEmbeddings(임베딩 모델) → 숫자 벡터로 변환
    → FAISS(벡터DB)에 저장

검색 쿼리
    → 동일하게 벡터로 변환
    → FAISS에서 유사도(코사인 유사도 등) 계산
    → 가장 유사한 k개 문서 반환
```

### 임베딩(Embedding)이란?

```
"마라탕" → [0.12, -0.85, 0.33, ...]  (수백~수천 차원의 숫자 배열)
"매운 음식" → [0.11, -0.82, 0.35, ...]  (의미가 비슷하면 벡터도 비슷)
```

텍스트의 **의미**를 숫자로 표현한 것. 의미가 비슷한 단어/문장은 벡터 공간에서 가까이 위치한다.

### 핵심 코드

```python
from langchain_community.vectorstores import FAISS
from langchain_aws import BedrockEmbeddings

# 임베딩 모델 (토크나이저)
tokenizer = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name=os.getenv("AWS_REGION"),
)

# 데이터 → 임베딩 → FAISS에 저장 (한 번에 처리)
vector_db = FAISS.from_texts(data, embedding=tokenizer)

# 유사도 검색
def search_stores(query: str, k: int = 2):
    docs = vector_db.similarity_search(query, k)  # 상위 k개 반환
    return "\n".join([doc.page_content for doc in docs])
```

### 실행 예시

```
search_stores("가벼운 식사")
→ 유사도 계산 결과:
   1위: "헬시 샐러드 - 닭가슴살 샐러드, 다이어트, 가벼움"
   2위: "엄마손 백반 - 김치찌개, 가성비"
```

---

## 6. RAG를 Tool로 변환 (`tools.py`)

```python
from langchain_core.tools import tool
from rag_store import search_stores

@tool
def rag_search(cate: str) -> str:
    """
    가격, 특징, 메뉴, 카테고리 등 입력받아서 → 벡터 유사도 검색 → 실제 식당 정보 제공
    """
    res = search_stores(cate)
    return res if res else "관련 식당 정보를 찾을 수 없습니다."
```

### 왜 Tool로 감싸는가?

```
RAG 함수 단독 사용:  코드에서 직접 호출 (항상 실행)
RAG를 Tool로 등록:  LLM이 필요하다고 판단할 때만 자동 호출
```

LLM이 사용자 질문을 보고 "이건 식당 정보가 필요하다"고 판단하면 스스로 `rag_search`를 호출한다.

---

## 7. 전체 에이전트 통합 (`lg_rag_agent.py`)

### 그래프 흐름

```
[START] → thinking → (조건부 분기)
                     ├─ 직접 답변 가능 → [END]
                     └─ 식당 검색 필요 → rag_search(RAG) → thinking → [END]
```

### FewShot 프롬프트

LLM에게 예시를 보여줘서 답변 스타일을 유도하는 기법.

```python
examples = [
    {"input": "비 오는날 국물이 땡겨",    "output": "국룰이죠. 칼국수와 잔치국수가 좋습니다."},
    {"input": "다이어트를 위해 칼로리 낮은것으로", "output": "관리하시는 군요. 닭가슴 샐러드 드세요."},
]
```

### 프롬프트 조합 구조

```python
final_prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 센스 있는 식사 메뉴 추천 전문가입니다..."),  # 1. 페르소나
    few_shot_prompt,                                               # 2. FewShot 예시
    ("human", "{messages}"),                                       # 3. 실제 사용자 질문
])
```

### 커스텀 상태 vs MessagesState

```python
# lg_rag_agent.py: 직접 정의
class AgentState(TypedDict):
    messages: List[BaseMessage]

# lg_test2/3.py: LangGraph 내장
from langgraph.graph import MessagesState
```

둘 다 `messages: List[BaseMessage]` 구조지만, `MessagesState`는 `add_messages` 리듀서가 자동 포함된다.

### 전체 시나리오

```
시나리오 1 - 직접 답변
유저: "비 오는 날 뭐 먹지?"
→ thinking: FewShot 예시 참고 → "칼국수 어떠세요?" 직접 답변
→ END

시나리오 2 - RAG 검색 후 답변
유저: "마라탕 파는 근처 식당 알려줘"
→ thinking: 식당 정보 검색이 필요하다고 판단
→ rag_search("마라탕") → FAISS 검색 → "스파이시 웍, 마라탕 15000원" 반환
→ thinking: 검색 결과를 바탕으로 최종 답변 생성
→ END
```

---

## 8. 전체 흐름 요약

### 학습 단계별 진행

```
lg_test1.py     → LangGraph 기본 뼈대 (State, Node, Edge)
    ↓
lg_test2.py     → LLM + Tool + 조건부 분기 + 사이클
    ↓
lg_test3.py     → 단기 기억 (MemorySaver, thread_id)
    ↓
rag_store.py    → 벡터DB로 RAG 구현 (FAISS + Bedrock Embeddings)
    ↓
tools.py        → RAG 함수를 LLM용 Tool로 변환
    ↓
lg_rag_agent.py → FewShot + RAG Tool + LangGraph 전체 통합
```

### 파일별 핵심 개념 요약

| 파일 | 핵심 개념 | 사용 기술 |
|---|---|---|
| `lg_test1.py` | StateGraph 기본 구조 | `TypedDict`, `add_node`, `add_edge` |
| `lg_test2.py` | LLM + Tool 에이전트 | `MessagesState`, `@tool`, `ToolNode`, `tools_condition` |
| `lg_test3.py` | 대화 기억 | `MemorySaver`, `checkpointer`, `thread_id` |
| `rag_store.py` | 벡터 유사도 검색 | `FAISS`, `BedrockEmbeddings`, `similarity_search` |
| `tools.py` | RAG → Tool 변환 | `@tool`, docstring 기반 LLM 인식 |
| `lg_rag_agent.py` | 전체 에이전트 | `FewShotChatMessagePromptTemplate`, `AgentState` |

### 주의할 점 (자주 하는 실수)

```python
# ❌ 잘못된 예 - 리스트 누락
prompt = {"messages": HumanMessage(content="질문")}
app.invoke({"msg": "질문"})          # 키 이름 오타
workflow.set_entry_point(node_func)  # 함수 객체 전달
workflow.add_edge("wrong_name", END) # 등록되지 않은 노드 이름

# ✅ 올바른 예
prompt = {"messages": [HumanMessage(content="질문")]}   # 반드시 리스트
app.invoke({"messages": [HumanMessage(content="질문")]}) # 키는 "messages"
workflow.set_entry_point("node_name")  # 문자열로 전달
workflow.add_edge("node_name", END)    # add_node에 등록한 이름과 동일해야 함
```
