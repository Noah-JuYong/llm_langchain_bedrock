# MCP (Model Context Protocol) 학습 정리
> 작성일: 2026-06-04

---

## 목차
1. [MCP란 무엇인가?](#1-mcp란-무엇인가)
2. [전체 아키텍처 흐름](#2-전체-아키텍처-흐름)
3. [server.py — MCP 서버 구현](#3-serverpy--mcp-서버-구현)
4. [client.py — MCP 클라이언트](#4-clientpy--mcp-클라이언트)
5. [mcp_tools_adapter.py — 어댑터 모듈](#5-mcp_tools_adapterpy--어댑터-모듈)
6. [bedrock_mcp_agent.py — Bedrock + LangGraph 에이전트](#6-bedrock_mcp_agentpy--bedrock--langgraph-에이전트)
7. [핵심 개념 정리](#7-핵심-개념-정리)
8. [파일 간 관계도](#8-파일-간-관계도)

---

## 1. MCP란 무엇인가?

**MCP (Model Context Protocol)** 는 AI 모델(LLM)이 외부 도구(Tool)를 사용할 수 있도록 표준화된 통신 규약이다.

### 왜 필요한가?
- LLM은 기본적으로 텍스트만 처리함
- 계산기, DB 조회, 파일 읽기 등 **외부 기능**을 쓰려면 별도의 연결이 필요
- MCP는 이 연결을 **표준 프로토콜**로 정의해서, 어떤 LLM이든 동일한 방식으로 외부 도구를 쓸 수 있게 함

### 핵심 구조
```
[사용자] → [MCP Client] ←→ [MCP Server] ←→ [외부 도구들]
                ↕
            [LLM (Bedrock)]
```

### 통신 방식 (이 프로젝트에서 사용)
- **STDIO (Standard I/O)** 방식: 클라이언트가 서버 프로세스를 직접 실행하고, 표준 입출력(stdin/stdout)으로 통신
- **JSON-RPC** 형식으로 메시지를 주고받음

---

## 2. 전체 아키텍처 흐름

```
┌─────────────────────────────────────────────┐
│              bedrock_mcp_agent.py            │
│  (LangGraph 에이전트 + Bedrock LLM)          │
│                                             │
│   사용자 입력 → LLM 판단 → Tool 호출 결정   │
└───────────────────┬─────────────────────────┘
                    │ import MCPClient
                    ▼
┌─────────────────────────────────────────────┐
│            mcp_tools_adapter.py             │
│  (MCP Client 역할 - LangChain Tool로 변환)   │
└───────────────────┬─────────────────────────┘
                    │ STDIO 통신 (JSON-RPC)
                    ▼
┌─────────────────────────────────────────────┐
│                 server.py                   │
│  (FastMCP 서버 - 실제 Tool 기능 구현)        │
│                                             │
│   add / get_time / save_note /              │
│   list_note / delete_note                  │
└─────────────────────────────────────────────┘
```

---

## 3. server.py — MCP 서버 구현

### 역할
외부에서 호출 가능한 **도구(Tool)들을 실제로 구현**하는 서버. `FastMCP` 라이브러리를 사용해 간결하게 구성함.

### 전체 코드 분석

#### 핵심: `@mcp.tool()` 데코레이터
```python
mcp = FastMCP("6ToolsMCPServer")  # 서버 인스턴스 생성, 이름 지정

@mcp.tool()   # ← 이 데코레이터가 함수를 "MCP 도구"로 등록해줌
def add(a: float, b: float) -> str:
    ...
```
> **`@mcp.tool()`이란?**  
> 일반 Python 함수를 MCP 프로토콜이 인식할 수 있는 "도구"로 변환해주는 장치.  
> 함수의 **타입 힌트**(`a: float`)와 **docstring**을 읽어서 자동으로 스키마(inputSchema)를 생성함.

---

#### 로깅 설정 - stderr 사용 이유
```python
logging.basicConfig(
    level=logging.INFO,
    format="[MCP Server] %(levelname)s: %(message)s",
    stream=sys.stderr,   # ← stdout이 아닌 stderr!
)
```
> **왜 `stderr`인가?**  
> STDIO 통신 방식에서 MCP 서버는 `stdout`으로 클라이언트에게 결과를 전송함.  
> 만약 로그도 `stdout`에 출력하면 JSON-RPC 메시지와 섞여서 통신이 깨짐.  
> 따라서 로그는 `stderr`(에러 출력 채널)로 분리해야 함.

---

#### 인메모리 저장소
```python
note_memory = dict()   # { "de-001": {"content": "...", "created_at": "..."} }
```
> 서버 프로세스가 살아있는 동안만 데이터 유지. 서버 재시작하면 초기화됨.  
> 실제 서비스에서는 DB나 파일로 대체해야 함.

---

#### 구현된 6개 도구

| 번호 | 함수명 | 기능 | 입력 파라미터 |
|------|--------|------|--------------|
| 1 | `add` | 두 수 덧셈 | `a: float`, `b: float` |
| 2 | `get_time` | 서버 현재 시간 조회 | 없음 |
| 3 | `save_note` | 메모 저장/업데이트 | `note_id: str`, `note_content: str` |
| 4 | `list_note` | 전체 메모 조회 | 없음 |
| 5 | `delete_note` | 특정 메모 삭제 | `note_id: str` |
| 6 | (미구현) | RAG 검색 | - |

---

#### Tool 3: save_note 상세 분석
```python
@mcp.tool()
def save_note(note_id: str, note_content: str) -> str:
    # 방어 코드: 빈값 체크
    if not note_id or not note_content:
        logger.warning("필수 파라미터 누락")
        return "Fail: 필수 파라미터 누락"

    # dict에 저장 (같은 note_id면 덮어쓰기 = Update)
    note_memory[note_id] = {
        "content": note_content,
        "created_at": datetime.now().isoformat(),  # "2026-06-04T10:30:00.123456"
    }
    return f"메모 저장 완료 {note_id}"
```
> `datetime.now().isoformat()` : 현재 시간을 ISO 8601 형식 문자열로 변환.  
> `note_memory[note_id] = ...` : dict는 같은 키로 저장하면 자동으로 업데이트됨 → Create/Update 한번에 처리.

---

#### Tool 4: list_note 상세 분석
```python
@mcp.tool()
def list_note() -> str:
    if not note_memory:   # dict가 비어있으면 False
        return "저장된 메모 없음"

    notes = "\n".join(
        [
            f'- id: {note_id},  content: {value["content"]}'
            for note_id, value in note_memory.items()  # dict 전체를 key,value로 순회
        ]
    )
    return f"저장된 모든 메모:\n{notes}"
```
> **리스트 컴프리헨션 + join** 패턴:  
> `[문자열 for 항목 in 컬렉션]` → 리스트 생성  
> `"\n".join(리스트)` → 각 항목을 줄바꿈으로 연결한 하나의 문자열로 합침

---

#### 서버 실행
```python
if __name__ == "__main__":
    mcp.run(transport="stdio")   # STDIO 모드로 실행
```
> `transport="stdio"` : 표준 입출력을 통해 클라이언트와 통신하겠다는 설정.  
> 클라이언트가 이 서버를 **subprocess(자식 프로세스)**로 실행해서 파이프로 연결함.

---

## 4. client.py — MCP 클라이언트

### 역할
MCP 서버에 접속해서 도구 목록을 조회하고, 직접 도구를 호출하는 **테스트용 클라이언트**.

### 비동기(async/await) 패턴 이해

```python
import asyncio

async def main():       # async 함수 = 비동기 함수
    client = MCPClient()
    await client.run()  # await = 이 작업 끝날 때까지 기다려

if __name__ == "__main__":
    asyncio.run(main()) # 비동기 함수를 동기 환경에서 실행하는 진입점
```

> **왜 async/await를 쓰는가?**  
> MCP 서버와의 통신은 I/O 작업(네트워크/프로세스 간 통신)이다.  
> 동기 방식이면 응답 기다리는 동안 프로그램이 멈춤.  
> async 방식이면 기다리는 동안 다른 작업 가능 → 더 효율적.

---

### 서버 접속 과정

```python
async def run(self):
    # 1. 서버 실행 파라미터 구성
    server_params = StdioServerParameters(
        command=sys.executable,   # 현재 파이썬 인터프리터 경로 (예: /usr/bin/python3)
        args=[self.server_script], # 실행할 스크립트: server.py
        env=None                   # 환경변수 (None = 현재 환경 그대로 상속)
    )

    # 2. 서버 프로세스를 실행하고 STDIO 연결
    async with stdio_client(server_params) as (read, write):
        # read: 서버 → 클라이언트 (서버의 응답을 읽는 스트림)
        # write: 클라이언트 → 서버 (서버에게 요청을 보내는 스트림)

        # 3. 세션(연결 관리 객체) 생성
        async with ClientSession(read, write) as session:
            await session.initialize()   # 핸드쉐이크: 서로 버전/기능 확인
```

> **`async with`란?**  
> 일반 `with`의 비동기 버전. 자원(파일, 네트워크 연결 등)을 열고, 블록이 끝나면 자동으로 닫아줌.  
> `stdio_client()`가 서버 프로세스를 시작하고, `with` 블록 종료 시 자동으로 프로세스도 종료.

---

### 도구 목록 조회

```python
res = await session.list_tools()
self.tools = res.tools   # Tool 객체들의 리스트

for i, tool in enumerate(self.tools, 1):   # 1부터 번호 매김
    print(f"   {i}. {tool.name}")
    print(f"   설명: {tool.description}")

    # 입력 파라미터 정보 추출
    if hasattr(tool, "inputSchema") and tool.inputSchema:
        # hasattr: 해당 속성이 존재하는지 확인 (없으면 에러 방지)
        props = tool.inputSchema.get("properties", {})
        # .get("key", 기본값): 키가 없어도 에러 없이 기본값 반환
        if props:
            print(f'   입력: { ", ".join(props.keys()) }')   # "a, b"
```

> **`hasattr(객체, "속성명")`** : 객체에 해당 속성이 있는지 True/False 반환.  
> 없는 속성에 `.`으로 접근하면 AttributeError 발생하므로, 먼저 존재 확인하는 방어 코드.

---

### 도구 호출

```python
async def call_tool(self, session, tool_name: str, arguments: dict):
    result = await session.call_tool(tool_name, arguments)
    # 내부적으로: Python dict → JSON 변환 → JSON-RPC 형식으로 서버 전송

    # 결과 파싱
    if hasattr(result, "content") and result.content:
        for content in result.content:
            if hasattr(content, "text"):
                print(f"\n결과 : {content.text}\n")   # 텍스트 결과
            else:
                print(f"결과 : \n{content}\n")         # 기타 형식
```

> **왜 결과가 `result.content[0].text` 구조인가?**  
> MCP는 다양한 결과 타입(text, image, 파일 등)을 지원하기 위해 content 배열로 결과를 감쌈.  
> 일반적인 텍스트 결과는 `content[0].text`에 담김.

---

### 테스트 시나리오 (실행 흐름)
```python
# 1. 덧셈
await self.call_tool(session, "add", {"a": 100, "b": 5})
# → "계산 결과: 100.0 + 5.0 = 105.0"

# 2. 현재 시간
await self.call_tool(session, "get_time", {})

# 3. 메모 2개 저장
await self.call_tool(session, "save_note", {"note_id": "de-001", "note_content": "MCP 1"})
await self.call_tool(session, "save_note", {"note_id": "de-002", "note_content": "MCP 2"})

# 4. 전체 목록 조회 → de-001, de-002 출력
await self.call_tool(session, "list_note", {})

# 5. de-001 삭제
await self.call_tool(session, "delete_note", {"note_id": "de-001"})

# 6. 전체 목록 재조회 → de-002만 출력
await self.call_tool(session, "list_note", {})
```

---

## 5. mcp_tools_adapter.py — 어댑터 모듈

### 역할
`client.py`와 동일한 `MCPClient` 코드이지만, **`bedrock_mcp_agent.py`에서 import해서 쓰는 모듈**로 분리됨.

```python
# bedrock_mcp_agent.py에서
from mcp_tools_adapter import MCPClient   # ← 이 파일에서 가져옴
```

### 이름이 "adapter"인 이유
단순히 MCP 서버와 통신하는 것을 넘어서, 앞으로 **MCP 도구들을 LangChain/LangGraph가 이해하는 Tool 형식으로 변환(adapt)**하는 역할을 담당할 것이기 때문.

> **현재 상태**: `client.py`와 동일한 코드  
> **미래 방향**: MCP Tool → LangChain `BaseTool` 형식으로 변환하는 로직이 추가될 예정

---

### Tool 스키마 형태 (README.md에서 확인)

서버에서 클라이언트로 전달되는 도구 정보의 구조:

```python
name='add'
description='두 수를 더하는 계산기...'

inputSchema={
    'properties': {
        'a': {'title': 'A', 'type': 'number'},
        'b': {'title': 'B', 'type': 'number'}
    },
    'required': ['a', 'b'],   # 필수 파라미터 목록
    'title': 'addArguments',
    'type': 'object'
}

outputSchema={
    'properties': {
        'result': {'title': 'Result', 'type': 'string'}
    },
    'required': ['result'],
    'title': 'addOutput',
    'type': 'object'
}
```

> 이 스키마 정보를 바탕으로 LLM이 "어떤 도구에 어떤 인자를 넣어야 하는지" 판단함.  
> `@mcp.tool()` 데코레이터가 함수의 타입 힌트와 docstring을 읽어서 자동으로 이 스키마를 생성함.

---

## 6. bedrock_mcp_agent.py — Bedrock + LangGraph 에이전트

### 역할
AWS Bedrock의 LLM과 MCP 도구들을 **LangGraph 워크플로우**로 연결한 에이전트.

### 전체 구조

```python
class BedrockMCPAgent:
    def __init__(self):
        self.llm = None        # AWS Bedrock LLM
        self.tools = []        # MCP에서 가져온 도구들
        self.graph = None      # LangGraph 워크플로우
        self.mcp_adapter = None  # MCP 서버 연결 객체
```

---

### LLM 초기화: ChatBedrock

```python
self.llm = ChatBedrock(
    model_id=os.getenv("MODEL_ID"),   # 환경변수에서 모델 ID 읽기
    client=boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_REGION")  # AWS 리전 (예: "ap-northeast-2")
    ),
    model_kwargs={
        "temperature": 0.7,   # 창의성 (0=일관성, 1=다양성)
        "max_tokens": 2000    # 최대 응답 길이
    },
)
```

> **`os.getenv("키이름")`**: `.env` 파일이나 환경변수에서 값을 가져옴. 코드에 API 키를 직접 쓰지 않기 위한 보안 패턴.

---

### LangGraph 워크플로우: `_setup_graph()`

#### 개념 이해
LangGraph는 LLM 에이전트의 동작을 **그래프(노드 + 엣지)**로 표현함.
- **노드(Node)**: 실제 작업 단위 (LLM 호출, 도구 실행)
- **엣지(Edge)**: 노드 간 이동 규칙

```
┌──────────┐     도구 호출 필요      ┌──────────┐
│  agent   │ ─────────────────────→ │  tools   │
│ (LLM)   │ ←─────────────────────  │ (실행)   │
└──────────┘     결과 반환           └──────────┘
     │
     │ 도구 불필요 (최종 답변)
     ▼
    END
```

---

#### 코드 분석

```python
def _setup_graph(self):
    # Step 1: LLM에 도구 목록을 알려줌 ("이런 도구들 쓸 수 있어")
    llm_with_tools = self.llm.bind_tools(self.tools)

    # Step 2: 상태(메시지 히스토리)를 공유하는 그래프 생성
    workflow = StateGraph(MessagesState)
    # MessagesState: 메시지 목록을 상태로 관리하는 내장 타입
```

> **`bind_tools()`**: LLM에게 "이런 도구들이 있으니, 필요하면 쓰라"고 알려주는 과정.  
> LLM은 응답할 때 도구를 쓸지 말지 결정하고, 쓰기로 하면 `tool_calls` 필드에 호출 정보를 담아 반환함.

---

```python
    # Step 3: 내부 함수(클로저) - LLM 호출 노드
    def call_agent(state: MessagesState) -> dict:
        messages = state["messages"]   # 지금까지의 대화 내용
        res = llm_with_tools.invoke(messages)   # LLM 호출
        return {"messages": [res]}   # 결과를 메시지에 추가
```

> **내부 함수(클로저)**: 함수 안에 정의된 함수. `llm_with_tools`처럼 외부 변수를 "캡처"해서 사용 가능.

---

```python
    # Step 4: 도구 실행 노드 (LangGraph 내장)
    tool_node = ToolNode(self.tools)
    # ToolNode: LLM이 tool_calls를 반환하면, 실제로 해당 도구를 실행해주는 노드

    # 노드 등록
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", tool_node)
```

---

```python
    # Step 5: 엣지(흐름 규칙) 설정
    workflow.set_entry_point("agent")   # 시작은 항상 agent 노드

    # 조건부 엣지: agent 노드 다음에 어디로 갈지 결정
    def 조건부함수(state: MessagesState) -> str:
        messages = state["messages"]
        last_msg = messages[-1]   # 가장 최근 메시지

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            # LLM이 도구를 쓰겠다고 했으면 → tools 노드로
            return "tools"
        # 아니면 → 종료
        return "end"

    workflow.add_conditional_edges(
        "agent",                           # 출발 노드
        조건부함수,                         # 판단 함수
        {"tools": "tools", "end": END}     # 반환값 → 이동할 노드 매핑
    )

    # tools 노드가 끝나면 → 다시 agent 노드로 (반복)
    workflow.add_edge("tools", "agent")

    # 최종 컴파일 (실행 가능한 상태로 변환)
    self.graph = workflow.compile()
```

> **`add_conditional_edges()`**: 조건에 따라 다른 노드로 이동하는 분기 처리.  
> **`END`**: LangGraph에서 그래프 종료를 나타내는 특수 상수.  
> **`workflow.compile()`**: 그래프 정의를 실행 가능한 객체로 변환. 이후 `.invoke()`로 실행 가능.

---

### 실행 흐름 예시

```
사용자: "100 + 5 계산해줘"
    ↓
agent 노드: LLM이 판단 → "add 도구 써야겠다"
    → tool_calls: [{"name": "add", "args": {"a": 100, "b": 5}}]
    ↓
조건부함수: tool_calls 있음 → "tools" 반환
    ↓
tools 노드: add(100, 5) 실제 실행 → "계산 결과: 100 + 5 = 105"
    ↓
agent 노드: 도구 결과 받아서 최종 답변 생성
    → "100과 5를 더한 결과는 105입니다"
    ↓
조건부함수: tool_calls 없음 → "end" 반환
    ↓
END (종료)
```

---

## 7. 핵심 개념 정리

### async / await
| 키워드 | 의미 |
|--------|------|
| `async def` | 이 함수는 비동기 함수다 (코루틴) |
| `await` | 이 작업 끝날 때까지 기다려 (다른 작업은 계속 실행 가능) |
| `asyncio.run()` | 비동기 함수를 동기 환경에서 실행하는 시작점 |
| `async with` | 비동기 컨텍스트 매니저 (자원 자동 관리) |

### LangGraph 구성 요소
| 요소 | 설명 |
|------|------|
| `StateGraph` | 상태(state)를 공유하는 그래프 |
| `MessagesState` | 메시지 목록을 상태로 갖는 내장 타입 |
| `add_node()` | 그래프에 노드(작업 단위) 추가 |
| `set_entry_point()` | 시작 노드 지정 |
| `add_edge()` | 노드 간 단방향 연결 |
| `add_conditional_edges()` | 조건에 따른 분기 |
| `compile()` | 그래프를 실행 가능한 상태로 변환 |
| `END` | 그래프 종료 신호 |

### MCP 통신 흐름 요약
```
1. 클라이언트가 server.py를 subprocess로 실행
2. STDIO(stdin/stdout)로 JSON-RPC 메시지 교환
3. 세션 초기화 (handshake)
4. list_tools() → 도구 목록과 스키마 수신
5. call_tool(이름, 인자) → 결과 수신
```

---

## 8. 파일 간 관계도

```
server.py
├── FastMCP로 6개 도구 구현
├── STDIO 모드로 서버 실행
└── note_memory(dict)로 인메모리 데이터 관리

client.py (테스트용)
├── MCPClient 클래스
├── server.py에 접속 후 도구 목록 조회
└── 직접 도구 호출 테스트

mcp_tools_adapter.py (어댑터 모듈)
├── client.py와 동일한 MCPClient 클래스
└── bedrock_mcp_agent.py에서 import해서 사용

bedrock_mcp_agent.py (메인 에이전트)
├── mcp_tools_adapter.MCPClient로 MCP 도구 로드
├── ChatBedrock으로 AWS LLM 연결
└── LangGraph 워크플로우로 에이전트 구성
    ├── agent 노드: LLM 판단
    ├── tools 노드: 도구 실행
    └── 조건부 엣지: 도구 필요 여부 분기
```

---

## 메모

- `bedrock_mcp_agent.py`는 **미완성** 상태: `main()` 함수와 사용자 입력 처리 부분이 아직 구현되지 않음
- `_init_llm()`이 `async def`로 선언되어 있으나, `initialize()` 내부에서 `await` 없이 호출되고 있음 → 버그 가능성 있음
- Tool 6 (RAG 검색)도 미구현 상태
