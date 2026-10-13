"""세션 3 실습: 일정·할 일 관리 Agent"""

import uuid
from typing import Annotated

from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langchain.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from tools import TOOLS

model = init_chat_model("openai:gpt-6-luna").bind_tools(TOOLS)

SYSTEM = SystemMessage(
    "너는 사용자의 일정과 할 일을 관리하는 비서다."
)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def llm(state: State):
    return {"messages": [model.invoke([SYSTEM] + state["messages"])]}


builder = StateGraph(State)
builder.add_node("llm", llm)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", tools_condition)
builder.add_edge("tools", "llm")
graph = builder.compile(checkpointer=InMemorySaver())


def show(messages):
    """이번 턴에 오간 tool call과 결과를 보여 준다."""
    for m in messages:
        for c in getattr(m, "tool_calls", []):
            print(f"  [tool call] {c['name']}({c['args']})")
        if isinstance(m, ToolMessage):
            print(f"  [도구 결과] {m.text}")


def new_config():
    return {"configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": 20}


if __name__ == "__main__":
    print("종료: exit 또는 quit / 새 대화: /reset")
    cfg = new_config()
    while True:
        user = input("you> ").strip()
        if user in ("exit", "quit"):
            break
        if not user:
            continue
        if user == "/reset":
            cfg = new_config()
            print("(새 대화를 시작합니다)")
            continue
        seen = len(graph.get_state(cfg).values.get("messages", []))
        result = graph.invoke({"messages": [HumanMessage(user)]}, cfg)
        show(result["messages"][seen:])
        print(result["messages"][-1].text)
