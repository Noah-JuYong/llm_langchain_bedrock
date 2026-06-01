from langgraph.graph import StateGraph, END
from typing import TypedDict


class CustomState(TypedDict):
    msg: str


def add_prefix(status: CustomState):
    return {"msg": "헬로 " + status["msg"]}


def add_surfix(status: CustomState):
    return {"msg": status["msg"] + " !!"}


workflow = StateGraph(CustomState)

workflow.add_node("T1", add_prefix)
workflow.add_node("T2", add_surfix)

workflow.set_entry_point("T1")

workflow.add_edge("T1", "T2")

workflow.add_edge("T2", END)

app = workflow.compile()

res = app.invoke({"msg": "랭그래프"})
print(res)
