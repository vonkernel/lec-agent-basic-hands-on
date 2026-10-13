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
from langgraph.types import Command, interrupt

model = init_chat_model("openai:gpt-6-luna")

SYSTEM = SystemMessage(
    "너는 사용자의 일정을 관리하는 비서다. "
    "일정을 정리할 때는 '- 날짜 시간 제목' 형식의 목록으로 답한다. "
    "등록된 목록에 없는 내용은 등록됐다고 답하지 않는다. "  # 3단계
    "할 일을 정리할 때는 '- 기한 할 일' 형식의 목록으로 답한다."  # 5단계
)


# 1단계: State와 reply 노드
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    events: Annotated[list[dict], operator.add]  # 3단계: 등록한 일정
    intent: str  # 3단계: 분류 결과
    draft: list[dict]  # 3단계: 추출 중인 일정
    since: int  # 3단계: 이번 요청이 시작된 메시지 위치
    tasks: Annotated[list[dict], operator.add]  # 5단계: 등록한 할 일


def reply(state: State):
    saved = SystemMessage(
        f"등록된 일정: {state.get('events', [])}\n"
        f"등록된 할 일: {state.get('tasks', [])}"  # 5단계
    )  # 3단계
    return {"messages": [model.invoke([SYSTEM, saved] + state["messages"])]}


# 3단계: 의도 분류와 일정 추출
class Route(BaseModel):
    """사용자 메시지의 의도"""

    # 5단계: add를 add_event로 바꾸고 add_task를 더함
    intent: Literal["add_event", "add_task", "reply"] = Field(
        description="새로 등록하려는 것이 "
        "진행 기간(시작과 끝 시각)이 필요한 일정이면 add_event, "
        "마감 기한이 필요한 할 일이면 add_task, "
        "새로 등록하는 요청이 아니면(조회, 정리, 그 밖의 대화) reply. "
        "요청에 시각이나 기한이 들어 있는지가 아니라 "
        "등록할 내용에 무엇이 필요한지로 판단한다")


class Event(BaseModel):
    """진행 기간(시작과 끝 시각)이 필요한 일정 하나. 알 수 없는 값은 비워 둔다"""

    title: Optional[str] = Field(None, description="일정 제목")
    start: Optional[str] = Field(None, description="시작 시각. 형식: YYYY-MM-DDTHH:MM")
    end: Optional[str] = Field(None, description="끝 시각. 형식: YYYY-MM-DDTHH:MM")


class Events(BaseModel):
    """이번 요청에서 추출한 일정"""

    items: list[Event]


# 5단계: 할 일(task)
class Task(BaseModel):
    """마감 기한이 필요한 할 일 하나. 알 수 없는 값은 비워 둔다"""

    todo: Optional[str] = Field(None, description="해야 할 일")
    due: Optional[str] = Field(None, description="기한 날짜. 형식: YYYY-MM-DD")


class Tasks(BaseModel):
    """이번 요청에서 추출한 할 일"""

    items: list[Task]


router = model.with_structured_output(Route)
extractor = model.with_structured_output(Events)
task_extractor = model.with_structured_output(Tasks)  # 5단계


def classify(state: State):
    intent = router.invoke(state["messages"][-1:]).intent
    return {"intent": intent, "since": len(state["messages"]) - 1}


def extract(state: State):
    msgs = state["messages"][state["since"]:]  # 이번 요청부터
    if state["intent"] == "add_task":  # 5단계: 할 일은 Task 형식으로 추출
        return {"draft": task_extractor.invoke(msgs).model_dump()["items"]}
    return {"draft": extractor.invoke(msgs).model_dump()["items"]}


def save(state: State):
    d = state["draft"]
    if state["intent"] == "add_task":  # 5단계: 할 일 등록
        text = "\n".join(f"할 일을 등록했습니다: {t['todo']} (기한 {t['due']})"
                         for t in d)
        return {"tasks": d, "messages": [AIMessage(text)]}
    text = "\n".join(f"등록했습니다: {e['title']} {e['start']} ~ {e['end']}"
                     for e in d)
    return {"events": d, "messages": [AIMessage(text)]}


def route_intent(state: State) -> Literal["extract", "reply"]:
    # 5단계: add_event와 add_task 모두 extract로
    return "reply" if state["intent"] == "reply" else "extract"


# 4단계: 빠진 정보 되묻기
LABELS = {"title": "제목", "start": "시작 시각", "end": "끝 시각",
          "todo": "할 일", "due": "기한"}  # 5단계: todo, due 추가


def ask(state: State):
    missing = []
    for e in state["draft"]:
        for key, value in e.items():
            if value is None:
                # 어느 일정인지 알 수 있게 제목과 시작 시각을 앞에 붙임
                name = e.get("title") or e.get("todo")  # 5단계: 할 일 이름도
                parts = [name, e.get("start"), LABELS[key]]
                missing.append(" ".join(p for p in parts if p))
    question = f"다음 정보를 알려 주세요: {', '.join(missing)}"
    answer = interrupt(question)  # 여기서 멈춤. 재개하면 사용자의 답을 반환
    return {"messages": [AIMessage(question), HumanMessage(answer)]}


def check(state: State) -> Literal["ask", "save"]:
    return "ask" if any(None in e.values() for e in state["draft"]) else "save"


builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("extract", extract)
builder.add_node("save", save)
builder.add_node("reply", reply)
builder.add_node("ask", ask)  # 4단계
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_intent, ["extract", "reply"])
# 4단계: extract → save 엣지를 빈 값 여부에 따른 조건부 엣지로 바꿈
builder.add_conditional_edges("extract", check, ["ask", "save"])
builder.add_edge("ask", "extract")  # 4단계: 사이클
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
        while "__interrupt__" in result:  # 4단계: 되묻는 질문에 답하고 재개
            question = result["__interrupt__"][0].value
            answer = input(f"bot> {question}\nyou> ").strip()
            if answer in ("exit", "quit"):  # 되묻는 중에도 종료
                raise SystemExit
            result = graph.invoke(Command(resume=answer), cfg)
        print(result["messages"][-1].text)
