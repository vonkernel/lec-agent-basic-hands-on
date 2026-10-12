"""세션 2 실습: 일정·할 일 관리 Workflow 그래프"""

from typing import Annotated

from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

model = init_chat_model("openai:gpt-6-luna")

SYSTEM = SystemMessage(
    "너는 사용자의 일정을 관리하는 비서다. "
    "일정을 정리할 때는 '- 날짜 시간 제목' 형식의 목록으로 답한다."
)


# 1단계: State와 reply 노드
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def reply(state: State):
    return {"messages": [model.invoke([SYSTEM] + state["messages"])]}


builder = StateGraph(State)
builder.add_node("reply", reply)
builder.add_edge(START, "reply")
builder.add_edge("reply", END)
graph = builder.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
    result = graph.invoke({"messages": [HumanMessage("내일 오후 3시에 팀 회의가 있어.")]})
    for m in result["messages"]:
        print(f"{m.type}: {m.text}")
