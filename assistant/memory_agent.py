"""세션 4 실습: 메모리를 갖춘 일정 관리 Agent"""

import sqlite3
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelRequest,
    SummarizationMiddleware,
    dynamic_prompt,
)
from langchain.messages import HumanMessage
from langchain.tools import ToolRuntime, tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore
from langgraph.types import Command

from tools import TOOLS

SYSTEM = """너는 사용자의 일정을 관리하는 비서다.
사용자가 앞으로도 지켜 주길 바라는 선호나 규칙을 말하면 remember로 기억한다. 기억한 선호는 아래 「기억한 사용자 선호」에 있다."""

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
# 2단계: 대화를 SQLite 파일에 저장
checkpointer = SqliteSaver(
    sqlite3.connect(DATA / "checkpoints.db", check_same_thread=False)
)

# 4단계: 사용자별 장기 메모리
store = SqliteStore(sqlite3.connect(
    DATA / "memories.db", check_same_thread=False, isolation_level=None
))


@dataclass
class Context:
    user_id: str


@tool
def remember(fact: str, runtime: ToolRuntime[Context]) -> str:
    """사용자가 앞으로도 지켜 주길 바라는 선호나 규칙을 기억한다. 예: 「회의는 오후가 좋아」.
    일정 자체는 기억하지 않는다."""
    namespace = (runtime.context.user_id, "memories")
    runtime.store.put(namespace, uuid.uuid4().hex[:6], {"fact": fact})
    return f"기억함: {fact}"


@dynamic_prompt
def with_memories(request: ModelRequest) -> str:
    """모델을 호출할 때마다 실행 중인 사용자의 메모리를 시스템 프롬프트 끝에 붙인다."""
    namespace = (request.runtime.context.user_id, "memories")
    items = request.runtime.store.search(namespace)
    facts = "\n".join(f"- {i.value['fact']}" for i in items) or "- 없음"
    return SYSTEM + f"\n\n# 기억한 사용자 선호\n{facts}"


# 1단계: create_agent로 옮기기
agent = create_agent(
    "openai:gpt-6.1-terra",
    tools=TOOLS + [remember],  # 4단계: remember 추가
    middleware=[
        with_memories,  # 4단계: 시스템 프롬프트에 메모리를 붙임
        SummarizationMiddleware(  # 3단계: 메시지가 20개를 넘으면 최근 10개만 남기고 요약
            model="openai:gpt-6.1-terra",
            trigger=("messages", 20),
            keep=("messages", 10),
        ),
        HumanInTheLoopMiddleware(interrupt_on={  # 삭제 전 사람 승인
            "delete_event": True,
        }),
    ],
    checkpointer=checkpointer,  # 2단계
    store=store,  # 4단계
    context_schema=Context,  # 4단계
)


if __name__ == "__main__":
    # 2단계: 대화 이름을 실행 파라미터로 받음
    thread = sys.argv[1] if len(sys.argv) > 1 else "기본"
    # 4단계: 사용자 이름을 실행 파라미터로 받음
    user_id = sys.argv[2] if len(sys.argv) > 2 else "나"
    cfg = {"configurable": {"thread_id": f"{user_id}-{thread}"},
           "recursion_limit": 20}
    ctx = Context(user_id=user_id)
    print(f"사용자: {user_id} / 대화: {thread} / 종료: exit 또는 quit")
    while True:
        user = input("you> ").strip()
        if user in ("exit", "quit"):
            break
        if not user:
            continue
        inputs = {"messages": [HumanMessage(user)]}
        result = agent.invoke(inputs, cfg, context=ctx)
        while "__interrupt__" in result:  # 삭제 승인 요청
            decisions = []
            for req in result["__interrupt__"][0].value["action_requests"]:
                question = f"다음을 실행할까요? {req['name']}({req['args']}) (y/n)"
                answer = input(f"bot> {question}\nyou> ").strip()
                if answer in ("exit", "quit"):
                    raise SystemExit
                kind = "approve" if answer.lower() == "y" else "reject"
                decisions.append({"type": kind})
            resume = Command(resume={"decisions": decisions})
            result = agent.invoke(resume, cfg, context=ctx)
        print(result["messages"][-1].text)
