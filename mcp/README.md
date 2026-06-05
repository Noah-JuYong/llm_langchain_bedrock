# tool 변환
- MCP 서버에서 구성한 도구의 이름, 인자(혹은 매개변수), 반환값 정보를 가져와서 파이썬(MCP Client) 코드로 변환 (인터페이스 구성)
- MCP Client 도구 호출 -> 파이썬 코드 작동 -> JSON 변환 -> JSON RPC 방식으로 MCP Server에 전닾
- 타입 맞춤

# tool 전달 형태
```
name='add' 
title=None 
description='\n    두 수를 더하는 계신기\n\n    Args:\n        a: 첫 번째 수치\n        b: 두 번째 수치\n    \n    Returns\n        계산 결과\n    ' 

inputSchema={
    'properties': {
        'a': {'title': 'A', 'type': 'number'}, 
        'b': {'title': 'B', 'type': 'number'}
    }, 
    'required': ['a', 'b'], 
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

icons=None 
annotations=None 
meta=None 
execution=None
```