"""세션 3 실습: 일정·할 일 관리 Agent"""

import uuid
from typing import Annotated, Literal

from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langchain.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from tools import TOOLS

model = init_chat_model("openai:gpt-6-luna").bind_tools(TOOLS)

SYSTEM = SystemMessage(
    "너는 사용자의 일정과 할 일을 관리하는 비서다."
)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def llm(state: State):
    return {"messages": [model.invoke([SYSTEM] + state["messages"])]}


# 5단계: 삭제 전 사람 승인
NEEDS_APPROVAL = {"delete_event", "delete_task"}


def route(state: State) -> Literal["tools", "approve", "__end__"]:
    calls = state["messages"][-1].tool_calls
    if not calls:
        return END
    if any(c["name"] in NEEDS_APPROVAL for c in calls):
        return "approve"
    return "tools"


def approve(state: State) -> Command[Literal["tools", "llm"]]:
    calls = state["messages"][-1].tool_calls
    targets = ", ".join(f"{c['name']}({c['args']})" for c in calls
                        if c["name"] in NEEDS_APPROVAL)
    # 여기서 멈춤. 재개하면 사용자의 답을 반환
    answer = interrupt(f"다음을 실행할까요? {targets} (y/n)")
    if answer.strip().lower() == "y":
        return Command(goto="tools")
    rejected = [ToolMessage("사용자가 거절해 실행하지 않았습니다.", tool_call_id=c["id"])
                for c in calls]
    return Command(goto="llm", update={"messages": rejected})


builder = StateGraph(State)
builder.add_node("llm", llm)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node("approve", approve)
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", route, ["tools", "approve", END])
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
        while "__interrupt__" in result:
            show(result["messages"][seen:])
            seen = len(result["messages"])
            question = result["__interrupt__"][0].value
            answer = input(f"bot> {question}\nyou> ").strip()
            if answer in ("exit", "quit"):
                raise SystemExit
            result = graph.invoke(Command(resume=answer), cfg)
        show(result["messages"][seen:])
        print(result["messages"][-1].text)
