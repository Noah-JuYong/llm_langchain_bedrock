"""
MCP Server 와 통신
MCP에서 정의한 Tool을 Langchain/Langgraph 용 Tool로 변환 처리
LLM이 해당 도구에 대한 이해와 ,사용 판단에 정확한 정보를 제공
"""

# 1. 모듈 가져오기
import asyncio
import sys
from typing import Optional
from mcp import ClientSession, StdioServerParameters  # 커넥션 담당
from mcp.client.stdio import stdio_client  # 입력, 출력을 가진 클라이언트
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


# 2. MCPToolAdapter
class MCPToolAdapter:
    """MCP Server와 통신. LangChain/LangGraph Tool로 변환 제공"""

    # 생성자
    def __init__(self, server_script: str = "server.py"):
        self.server_script = server_script
        self.mcp_tools = []  #  mcp Tool
        self.tools = {}  #  LangChain/LangGraph Tool
        self.read_stream = None  # 입력 스트림 -> 여러 함수에서 사용하겠다.
        self.write_stream = None  # 출력 스트림 -> 여러 함수에서 사용하겠다.
        self.session: Optional[ClientSession] = (
            None  # 세션 맴버변수 -> 여러 함수에서 사용하겠다.
        )
        self._stdio_context = (
            None  # 입출력에 관련한 내부적 프로레스 접근을 위한 컨텍스트
        )
        pass

    # 초기화
    async def initialize(self):
        """MCP Server 연결, Tool 로드"""
        # MCP Server 접속시 필요한 정보 세팅
        server_params = StdioServerParameters(
            command=sys.executable, args=[self.server_script], env=None
        )
        # 메세지가 오염되면 => 출력을 sys.stderr
        print("MCP 서버 연결중..", file=sys.stderr)
        try:
            # 입력, 출력, 세션등, 여러 함수에서 사용한다면 with x
            # MCP 서버를 접속할때 사용하는 내부 컨텍스트 객체
            self._stdio_context = stdio_client(server_params)
            # 내부 함수를 강제로 호출(내가 원하는 시점에 처리)
            # 비동기, 입력/출력 스트림 연결하여 반환
            stdio_tuple = await self._stdio_context.__aenter__()
            # 입력/출력 스트 획득
            if isinstance(stdio_tuple, tuple):
                self.read_stream, self.write_stream = stdio_tuple
            else:
                self.read_stream = stdio_tuple
                self.write_stream = stdio_tuple

            print("MCP 스트림 생성 완료", file=sys.stderr)
            # 세션 획득(생성) => 툴을 가져올수 있음
            # JSON RPC 2.0 기준 상호 통신할수 있는 논리적인 상태(세션) 완성
            self.session = ClientSession(self.read_stream, self.write_stream)
            # 실제 활성화를 위해 직접 호출
            await self.session.__aenter__()
            # 세션 초기화
            await self.session.initialize()
            print("MCP 세션 생성 완료", file=sys.stderr)
            # MCP 서버에게 Tool 목록 요청
            res = await self.session.list_tools()
            self.mcp_tools = res.tools
            print(
                f"MCP 서버로부터 { len(self.mcp_tools) }개의 툴 로드됨", file=sys.stderr
            )

            return self
        except Exception as e:
            print("MCP 서버 연결 실패", e, file=sys.stderr)
            raise
        pass

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """MCP TOOL 호출"""
        try:
            result = await self.session.call_tool(tool_name, arguments)
            if hasattr(result, "content") and result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        return content.text
            return str(result)
        except Exception as e:
            return f"{tool_name} 실행 오류 { str(e) }"

    # MCP tool -> langchain/langgraph tool 변환
    # MCP서버에 등록된 도구를  랭체인 생태계의 `LLM`에서 바로 사용 할수 있도록 자동 변환해주는 함수
    # MCP서버 도구는 스키마를  JSON 을 전달해줌(JSON-RPC)
    # 랭체인 도구는 pydantic 적용하면 강력한 타입 검증(유효성검증) 요구할수 있도록 구성할수 있음
    # 목표 어떤 도구던지 자동 변환 해주는 함수 구성
    def create_langchain_tools(self) -> list:
        langchain_tools = list()

        # 툴 순회 -> 범용적 표현 -> 본 코드를 그냥 사용하면 다 적용됨
        for mcp_tool in self.mcp_tools:
            # 툴 이름
            tool_name = mcp_tool.name
            # 툴 설명
            tool_description = mcp_tool.description
            print(tool_name, tool_description)

            # MCP TOOL을 호출할수 있는 형태 구성(인터페이스)
            # 함수의 형태 -> 동적으로 비동기 함수(도구의 외적 형태) 생성 -> MCPClient 예시
            # 클로저 형태로로 함수를 구성하여 각각의 함수가 독립적으로 생셩되게 구성
            def create_tool_func(name: str):
                async def async_tool_func(**kwargs) -> str:
                    """동적으로 생성되는 TOOL"""
                    return await self.call_tool(name, kwargs)

                return async_tool_func

            tool_func = create_tool_func(tool_name)

            # LLM MCP 도구를 선택할때 판단할 수 있는 재료들
            # 함수의 스키마
            tool_params = {}  # 매개변수 정보
            required_fields = []  # 필수 매개변수

            if (
                hasattr(mcp_tool, "inputSchema") and mcp_tool.inputSchema
            ):  # 스키마 정보가 있다면
                props = mcp_tool.inputSchema.get("properties", {})
                required = mcp_tool.inputSchema.get("required", [])

                for (
                    param_name,
                    param_info,
                ) in props.items():  # 매개변수 이름(키), 정보(값)
                    param_type = param_info.get("type", "string")  # 매개변수명
                    param_desc = param_info.get("description", "")  # 매개변수설명

                    # param_name을 이용하여 기본값 설정
                    if param_name in required:  # 필수 항목에 파라미터명 있다면
                        default = ...  # 모든 정보 다 세팅
                    else:
                        default = None

                    # 타입 변환
                    if param_type == "number":
                        tool_params[param_name] = (
                            float,
                            Field(default=default, description=param_desc),
                        )
                        pass
                    elif param_type == "integer":
                        tool_params[param_name] = (
                            int,
                            Field(default=default, description=param_desc),
                        )
                        pass
                    elif param_type == "boolean":
                        tool_params[param_name] = (
                            bool,
                            Field(default=default, description=param_desc),
                        )
                        pass
                    else:
                        tool_params[param_name] = (
                            str,
                            Field(default=default, description=param_desc),
                        )
                        pass

            # pydantic 모델 동적 적용
            # 매개변수 => 클레스로 감까서 => 타입 제한에 대한 룰 구성
            if tool_params:
                args_schema = create_model(
                    f"{tool_name}_args",  # 모델 이름
                    **tool_params,  # 모든 도구의 매개변수가 세팅
                )
            else:
                # 매개변수 없는 도구의 인자 형태 정의
                class EmptyArgs(BaseModel):
                    pass

                args_schema = EmptyArgs

            # StructuredTool => 랭체인 도구
            # 재료 : 실행함수, 이름, 설명, 아규먼트 스키마
            # 랭체인용 StructuredTool이는 객체로 매핑 => LLM이 도구로 사용 형태
            # StructuredTool 생성하여 랭체인 툴에 반영 적용 -> LLM이 툴에 대해 이해, 필요하면 사용(선택의 지표 제공)
            try:
                langchain_tool = StructuredTool.from_function(
                    func=tool_func,
                    name=tool_name,
                    description=tool_description,
                    args_schema=args_schema,
                    coroutine=tool_func,  # 비동기 함수 명시적 표현
                )
            except Exception as e:
                langchain_tool = StructuredTool.from_function(
                    func=tool_func,
                    name=tool_name,
                    description=tool_description,
                    args_schema=args_schema,
                )
            langchain_tools.append(
                langchain_tool
            )  # 도구를 하나 모아둠 -> 최종 도구 개수만큼 추가됨
            # 관리상
            self.tools[tool_name] = langchain_tool

        return langchain_tools  # 모든 도구를 반환

    async def cleanup(self):
        """입력/출력 스트림, 세션등 자원 해제(개발자 관리)"""
        # 세션이 존재하면 -> 세션 종료
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
        except Exception as e:
            print("세션 종료 에러", e, file=sys.stderr)

        # 컨텍스트가 존재하면 -> 입력/출력 스트림 종료
        try:
            if self._stdio_context:
                await self._stdio_context.__aexit__(None, None, None)
        except Exception as e:
            print("입력/출력 스트림 종료 에러", e, file=sys.stderr)
        pass


# 4. 테스트
if __name__ == "__main__":
    # 단위 테스트
    async def test():
        # 자체적으로 아답터 구성 => 툴 목록 => 함수 구성 => 해제
        adapter = MCPToolAdapter("server.py")
        # 초기화
        await adapter.initialize()
        # MCP tool -> langchain/langgraph tool 변환
        tools = adapter.create_langchain_tools()
        print("도구 생성 완료")
        for tool in tools:
            print(f"{tool.name} ")

        # 해제
        await adapter.cleanup()

    asyncio.run(test())
    pass
