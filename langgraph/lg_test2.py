from langgraph.graph import StateGraph, END, MessagesState, START
from typing import TypedDict
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_aws import ChatBedrock, ChatBedrockConverse
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv
import os
import boto3

load_dotenv()

llm = ChatBedrock(
    model=os.getenv("MODEL_ID"),
    client=boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION")),
)


@tool
def multiply(a: int, b: int) -> int:
    print(f"    [TOOL 실행] {a}x{b} 계산중 ...")
    return a * b


tools = [multiply]
llm_with_tools = llm.bind_tools(tools)


def chatbot_node(state: MessagesState):
    print("[chatbot_node 호출 전 상태값]", state)
    res = llm_with_tools.invoke(state["messages"])
    new_state = {"messages": [res]}
    print("[chatbot_node 호출 후 상태값]", new_state)
    return new_state


workflow = StateGraph(MessagesState)
workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", ToolNode(tools))

workflow.add_edge(START, "chatbot")

workflow.add_conditional_edges("chatbot", tools_condition)

workflow.add_edge("tools", "chatbot")

app = workflow.compile()

if __name__ == "__main__":
    while True:
        user_input = input("\n유저: ")
        if user_input == "q":
            break
