"""세션 2 실습: 일정·할 일 관리 Workflow 그래프"""

import operator
import uuid
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

model = init_chat_model("openai:gpt-6-luna")

SYSTEM = SystemMessage(
    "너는 사용자의 일정을 관리하는 비서다. "
    "일정을 정리할 때는 '- 날짜 시간 제목' 형식의 목록으로 답한다. "
    "등록된 목록에 없는 내용은 등록됐다고 답하지 않는다."  # 3단계
)


# 1단계: State와 reply 노드
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    events: Annotated[list[dict], operator.add]  # 3단계: 등록한 일정
    intent: str  # 3단계: 분류 결과
    draft: list[dict]  # 3단계: 추출 중인 일정
    since: int  # 3단계: 이번 요청이 시작된 메시지 위치


def reply(state: State):
    saved = SystemMessage(f"등록된 일정: {state.get('events', [])}")  # 3단계
    return {"messages": [model.invoke([SYSTEM, saved] + state["messages"])]}


# 3단계: 의도 분류와 일정 추출
class Route(BaseModel):
    """사용자 메시지의 의도"""

    intent: Literal["add", "reply"] = Field(
        description="새 일정을 등록해 달라는 요청이면 add, 그 밖에는 reply")


class Event(BaseModel):
    """진행 기간(시작과 끝 시각)이 필요한 일정 하나. 알 수 없는 값은 비워 둔다"""

    title: Optional[str] = Field(None, description="일정 제목")
    start: Optional[str] = Field(None, description="시작 시각. 형식: YYYY-MM-DDTHH:MM")
    end: Optional[str] = Field(None, description="끝 시각. 형식: YYYY-MM-DDTHH:MM")


class Events(BaseModel):
    """이번 요청에서 추출한 일정"""

    items: list[Event]


router = model.with_structured_output(Route)
extractor = model.with_structured_output(Events)


def classify(state: State):
    intent = router.invoke(state["messages"][-1:]).intent
    return {"intent": intent, "since": len(state["messages"]) - 1}


def extract(state: State):
    msgs = state["messages"][state["since"]:]  # 이번 요청부터
    return {"draft": extractor.invoke(msgs).model_dump()["items"]}


def save(state: State):
    d = state["draft"]
    text = "\n".join(f"등록했습니다: {e['title']} {e['start']} ~ {e['end']}"
                     for e in d)
    return {"events": d, "messages": [AIMessage(text)]}


def route_intent(state: State) -> Literal["extract", "reply"]:
    return "extract" if state["intent"] == "add" else "reply"


builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("extract", extract)
builder.add_node("save", save)
builder.add_node("reply", reply)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_intent, ["extract", "reply"])
builder.add_edge("extract", "save")
builder.add_edge("save", END)
builder.add_edge("reply", END)

# 2단계: checkpointer
graph = builder.compile(checkpointer=InMemorySaver())


def new_config():
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


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
        result = graph.invoke({"messages": [HumanMessage(user)]}, cfg)
        print(result["messages"][-1].text)
