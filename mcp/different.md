# today_study.md vs 현재 코드 — 변경사항 정리
> 비교 기준일: 2026-06-05

---

## 요약

| 파일 | 변경 규모 | 주요 내용 |
|------|-----------|-----------|
| `server.py` | 변경 없음 | - |
| `client.py` | 소규모 | 출력 형식 개선, 테스트 완료 메시지 추가 |
| `mcp_tools_adapter.py` | **대규모 (전면 재작성)** | MCPClient → MCPToolAdapter로 완전 교체 |
| `bedrock_mcp_agent.py` | 중규모 | 미완성 부분 구현 완료 |

---

## 1. server.py — 변경 없음

---

## 2. client.py — 출력 형식 개선

### 변경 1: `call_tool()` — 호출 전 도구명/인자 출력 추가

**이전 (study.md 기준)**
```python
async def call_tool(self, session, tool_name: str, arguments: dict):
    try:
        result = await session.call_tool(tool_name, arguments)
        print(f"결과출력 : {result}")
```

**현재**
```python
async def call_tool(self, session, tool_name: str, arguments: dict):
    try:
        print(f" {tool_name} 도구 사용")   # ← 추가: 어떤 도구 호출하는지 출력
        print(f" 인자 {arguments}")         # ← 추가: 어떤 인자 넘기는지 출력
        result = await session.call_tool(tool_name, arguments)
        # print(f'결과출력 : {result}')     # ← 주석 처리 (원시 result 객체 출력 제거)
```

> **이유**: 도구 호출 과정을 단계별로 추적하기 쉽게 개선. 원시 result 객체 출력은 가독성이 낮아 제거.

---

### 변경 2: `call_tool()` — 결과 출력 포맷 변경

**이전**
```python
print(f"\n결과 : {content.text}\n")
```

**현재**
```python
print(f" 결과 : \n {content.text}\n")
```

> 줄바꿈 위치와 들여쓰기가 바뀐 출력 형식 변경.

---

### 변경 3: `run()` — 테스트 완료 메시지 블록 추가

**이전**: 마지막 `list_note()` 호출 이후 별도 메시지 없음

**현재**: 아래 블록이 추가됨
```python
print("\n" + "-" * 30)
print("도구 호출 테스트 완료")
print("-" * 30 + "\n")
```

---

## 3. mcp_tools_adapter.py — 전면 재작성

study.md 당시에는 `client.py`와 **완전히 동일한 코드**(`MCPClient` 클래스)였음.  
현재는 목적에 맞게 **`MCPToolAdapter`** 라는 새로운 클래스로 전면 재작성됨.

---

### 변경 1: 클래스명 및 목적 변경

| 항목 | 이전 | 현재 |
|------|------|------|
| 클래스명 | `MCPClient` | `MCPToolAdapter` |
| 역할 | 도구 호출 테스트용 클라이언트 | MCP Tool → LangChain Tool 변환 전담 |
| import 추가 | - | `StructuredTool`, `BaseModel`, `Field`, `create_model` (pydantic/langchain) |

---

### 변경 2: 세션 관리 방식 변경 (`async with` → 직접 `__aenter__` 호출)

**이전** — `async with`으로 세션을 블록 안에서만 사용
```python
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # 블록 벗어나면 자동 종료
```

**현재** — 스트림/세션을 멤버변수로 저장하고 수동 관리
```python
# 멤버변수로 선언
self.read_stream = None
self.write_stream = None
self.session: Optional[ClientSession] = None
self._stdio_context = None

# initialize()에서 직접 __aenter__ 호출
self._stdio_context = stdio_client(server_params)
stdio_tuple = await self._stdio_context.__aenter__()   # 강제 진입
self.read_stream, self.write_stream = stdio_tuple

self.session = ClientSession(self.read_stream, self.write_stream)
await self.session.__aenter__()   # 강제 진입
await self.session.initialize()
```

> **왜 이렇게 바꿨나?**  
> `async with`를 쓰면 블록이 끝날 때 연결이 자동으로 닫힘.  
> 에이전트처럼 **여러 함수에서 세션을 지속적으로 재사용**해야 하는 경우, 연결을 유지한 채로 필요할 때 직접 닫는 방식이 필요함.  
> `cleanup()` 메서드에서 `__aexit__`를 직접 호출해 수동으로 자원을 해제함.

---

### 변경 3: `call_tool()` — 시그니처 단순화

**이전** (`client.py`의 방식)
```python
async def call_tool(self, session, tool_name: str, arguments: dict):
    result = await session.call_tool(tool_name, arguments)
    # 결과를 print로 출력
```

**현재** — `session`을 인자로 받지 않고 멤버변수 `self.session` 사용, 결과를 `return`으로 반환
```python
async def call_tool(self, tool_name: str, arguments: dict) -> str:
    result = await self.session.call_tool(tool_name, arguments)
    if hasattr(result, "content") and result.content:
        for content in result.content:
            if hasattr(content, "text"):
                return content.text   # print 대신 return
    return str(result)
```

---

### 변경 4: `create_langchain_tools()` 메서드 신규 추가 (핵심)

MCP Tool 스키마(JSON)를 LangChain의 `StructuredTool`로 자동 변환하는 로직.

```python
def create_langchain_tools(self) -> list:
    for mcp_tool in self.mcp_tools:
        # 1. 클로저로 각 도구별 비동기 함수 생성
        def create_tool_func(name: str):
            async def async_tool_func(**kwargs) -> str:
                return await self.call_tool(name, kwargs)
            return async_tool_func

        # 2. MCP 스키마 → pydantic 타입 매핑
        # inputSchema.properties를 순회하며 타입 변환
        if param_type == "number":    → float
        elif param_type == "integer": → int
        elif param_type == "boolean": → bool
        else:                         → str

        # 3. pydantic 모델 동적 생성 후 StructuredTool로 변환 (미완성 - pass 상태)
```

> **클로저 패턴이 왜 필요한가?**  
> `for` 루프 안에서 함수를 만들면 모든 함수가 같은 `tool_name` 변수를 공유함.  
> `create_tool_func(name)` 형태로 함수를 한번 더 감싸면, 각 함수가 호출 시점의 `name` 값을 독립적으로 캡처함.

---

### 변경 5: `cleanup()` 메서드 신규 추가

```python
async def cleanup(self):
    try:
        if self.session:
            await self.session.__aexit__(None, None, None)   # 세션 종료
    except Exception as e:
        print("세션 종료 에러", e, file=sys.stderr)

    try:
        if self._stdio_context:
            await self._stdio_context.__aexit__(None, None, None)   # 스트림 종료
    except Exception as e:
        print("입력/출력 스트림 종료 에러", e, file=sys.stderr)
```

---

## 4. bedrock_mcp_agent.py — 미완성 부분 구현 완료

### 변경 1: import 변경

**이전**
```python
from mcp_tools_adapter import MCPClient
```

**현재**
```python
from mcp_tools_adapter import MCPToolAdapter   # 클래스명 변경에 맞춰 수정
```

---

### 변경 2: `initialize()` — MCPToolAdapter 연결 코드 추가

**이전** — 주석만 있고 구현 없음
```python
async def initialize(self):
    print(f"MCP Server와 연결중..")
    # mcp_tools_adapter.py와 작업 기술  ← 주석만 있었음
```

**현재** — 실제 연결 코드 추가
```python
async def initialize(self):
    print(f"MCP Server와 연결중..")
    self.mcp_adpater = MCPToolAdapter(self.server_script)
    await self.mcp_adpater.initialize()   # ← MCP 서버 연결 및 도구 목록 로드
```

---

### 변경 3: `process_query()` 메서드 신규 구현

**이전** — 주석만 있었음 (미구현)

**현재** — 완전히 구현됨
```python
async def process_query(self, user_input: str) -> str:
    print(f"\n사용자 입력 : {user_input}\n")
    messages = [HumanMessage(content=user_input)]   # 사용자 메시지 구성
    try:
        result = self.graph.invoke({"messages": messages})   # 그래프 실행
        last_msg = result["messages"][-1]                    # 마지막 메시지 추출
        if hasattr(last_msg, "content"):
            res = last_msg.content
        else:
            res = str(last_msg)
        print(f"\n 에이전트 응답 { res }")
        return res
    except Exception as e:
        msg = f"\n 메세지 처리중 에러 발생 {e}"
        print(msg)
        return msg
```

---

### 변경 4: `cleanup()` 메서드 신규 구현

**이전** — `pass`만 있었음

**현재**
```python
async def cleanup(self):
    if self.mcp_adpater:
        await self.mcp_adpater.cleanup()   # MCPToolAdapter의 cleanup() 호출
```

---

### 변경 5: `main()` 함수 구현

**이전** — 주석만 있는 빈 함수

**현재** — 실제 실행 흐름 구현
```python
async def main():
    agent = BedrockMCPAgent()
    try:
        agent.initialize()                     # ← await 누락 (버그, 아래 메모 참고)
        query = input("\n프럼프트 입력: ").strip()
        if query:
            await agent.process_query(query)
    except Exception as e:
        print("main() 오류 발생 {e}")
    finally:
        await agent.cleanup()
```

---

## 주의: 남아있는 버그

`bedrock_mcp_agent.py`의 `main()` 함수에서 `await` 누락이 있음.

```python
# 현재 코드 (버그)
agent.initialize()

# 올바른 코드
await agent.initialize()
```

`initialize()`는 `async def`로 선언되어 있기 때문에, `await` 없이 호출하면 실제로 실행되지 않고 코루틴 객체만 반환됨. MCP 서버 연결과 LLM 초기화가 모두 건너뛰어지므로 이후 `process_query()` 호출 시 에러가 발생함.
