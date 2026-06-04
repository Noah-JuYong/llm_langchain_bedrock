"""
MCP 1.27.2
외부 도구를 구현한 MCP 서버, FastMCP를 이용하여 간결하게 구성
"""

# 1. 모듈 가져오기
import sys
import logging
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# 2. 로깅 설정
#    출력값 섞이면 불편 => stderr 출력 조정
logging.basicConfig(
    level=logging.INFO,
    format="[MCP Server] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# 3. MCP 서버 설정
mcp = FastMCP("6ToolsMCPServer")
logger.info("MCPServer 구성(초기화) 중..")

# 4. 인메모리 -> 메모/임시데이터를 저장할 tool 용도로 dict 형태로 저장관리용 -> 기본 구성 x
note_memory = dict()


# 5. 툴 구현 (외부에 특정 리소스, s/w, 기타.. ), 편의상 간단한 기능 구성, 6개 구성
## Tool 1 : add (두 수를 더하기) -> 함수구성, 타입힌트 명시, 함수 주석
def add(a: float, b: float) -> str:
    """
    두 수를 더하는 계신기

    Args:
        a: 첫 번째 수치
        b: 두 번째 수치

    Returns
        계산 결과
    """
    result = a + b
    logger.info(f"Tool 1 add 호출: {a} + {b} = {result}")
    return f"계산 결과: {a} + {b} = {result}"


## Tool 2 : get_time 서버측 현재시간
def get_time() -> str:
    """
    서버측 현재 시간을 조회

    Returns
        현재 시간 문자열
    """
    cur_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Tool 2 get_time 호출: {cur_time}")
    return f"현재 시간: {cur_time}"


# CRUD 도구
## Tool 3 : save_note 메모 저장/업데이트
def save_note(note_id: str, note_content: str) -> str:
    """
    메모 저장

    Args:
        note_id: 메모의 고유 ID, 키값
        note_content: 메모 내용

    Returns
        저장 완료 메세지
    """
    # 방어코드
    if not note_id or not note_content:  # 내용 혹은 아이디가 누락되면
        logger.warning("필수 파라미터 누락")
        return "Fail: 필수 파라미터 누락"
    # 저장처리
    note_memory[note_id] = {
        "content": note_content,
        "created_at": datetime.now().isoformat(),
    }
    # 로깅
    logger.info(f"save_note 호출: note_id={note_id}")
    # 반환
    return f"메모 저장 완료 {note_id}"
    pass


## Tool 4 : list_note 메모 목록 조회
def list_note() -> str:
    """
    저장된 모든 메모 목록 조회

    Returns
        저장된 모든 메모
    """
    if not note_memory:
        logger.info(f"list_note 호출: 저장된 메모 없음")
        return "저장된 메모 없음"

    # 존재하면 => 하나의 말뭉치로 구성 반한 (컨셉)
    notes = "\n".join(
        [
            f'- id: {note_id},  content: {value["content"]}'
            for note_id, value in note_memory.items()
        ]
    )
    return f"저장된 모든 메모:\n{notes}"


## Tool 5 : delete_note 메모 삭제
def delete_note(note_id: str) -> str:
    """
    특정 메모 삭제

    Args:
        note_id: 메모의 고유 ID, 키값

    Returns
        현재 시간 문자열
    """
    # 실습 -> 삭제는 del 사용
    if note_id in note_memory:
        del note_memory[note_id]
        logger.info(f"delete_note 호출: note_id={note_id}")
        return f"메모 삭제 완료! {note_id}"
    else:
        logger.info(f"delete_note 실패: note_id={note_id}로 구분되는 메모가 없음")
        return f"메모 삭제 실패! {note_id}로 구분되는 메모가 없음"
    pass


## Tool 6 : rag_search 검색증강

# 6. 서버 가동
if __name__ == "__main__":
    logger.info("MCPServer 가동중...")
    logger.info("STDIO 모드 가동 중..")

    mcp.run(transport="stdio")
