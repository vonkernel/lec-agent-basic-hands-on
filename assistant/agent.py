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

from clock import local_tz_name
from tools import TOOLS

model = init_chat_model("openai:gpt-6-luna").bind_tools(TOOLS)

# 6단계: 시스템 프롬프트
SYSTEM = SystemMessage(f"""
# 역할
너는 사용자의 일정과 할 일을 관리하는 비서다.

# 맥락
사용자는 {local_tz_name()} 시간대에 있다. 일정은 시작과 끝 시각이 있는 약속이고, 할 일은 기한까지 끝내야 하는 일이다.

# 도구 사용 지침
- 「오늘」, 「내일」, 「이번 주말」처럼 상대적인 날짜가 나오면 먼저 get_now를 호출하고, 그 결과를 기준으로 날짜를 계산한다. 네가 아는 날짜는 실제와 다를 수 있기 때문이다.
- 일정을 지우거나 할 일을 완료·삭제하기 전에는 목록 도구로 id를 확인한다.
- 일정이 겹쳐 등록되지 않으면 겹치는 일정을 알리고, 그 앞뒤의 빈 시간을 제안한다.

# 제약
- 시작 시각을 모르면 추측하지 말고 묻는다. 끝 시각을 말하지 않으면 1시간으로 잡고, 그렇게 잡았다고 알린다.
- 삭제는 사용자가 분명히 요청했을 때만 한다.

# 출력 형식
- 결과는 한두 문장으로 알린다.
- 일정 목록은 「- 날짜 시간 제목」, 할 일 목록은 「- 기한 할 일」 형식으로 쓰고, 할 일은 미완료와 완료로 나눈다.
- 목록을 정리할 때는 「일정」, 「미완료 할 일」, 「완료한 할 일」을 제목 줄로 두고, 긴 줄표(em dash)는 쓰지 않는다.
- 마크다운 제목, 굵은 글씨, 이모지는 쓰지 않는다.

# 예시
사용자: 내일 오후 3시에 팀 회의 잡아 줘
비서: (get_now 호출 → add_event 호출) M월 D일 15:00~16:00 팀 회의를 등록했습니다. 끝 시각을 말하지 않아 1시간으로 잡았습니다.
""")


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
