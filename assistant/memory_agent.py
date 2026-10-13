"""세션 4 실습: 메모리를 갖춘 일정·할 일 관리 Agent"""

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

from clock import local_tz_name
from tools import TOOLS

SYSTEM = f"""
# 역할
너는 사용자의 일정과 할 일을 관리하는 비서다.

# 맥락
사용자는 {local_tz_name()} 시간대에 있다. 일정은 시작과 끝 시각이 있는 약속이고, 할 일은 기한까지 끝내야 하는 일이다.

# 도구 사용 지침
- 「오늘」, 「내일」, 「이번 주말」처럼 상대적인 날짜가 나오면 먼저 get_now를 호출하고, 그 결과를 기준으로 날짜를 계산한다. 네가 아는 날짜는 실제와 다를 수 있기 때문이다.
- 일정을 지우거나 할 일을 완료·삭제하기 전에는 목록 도구로 id를 확인한다.
- 일정이 겹쳐 등록되지 않으면 겹치는 일정을 알리고, 그 앞뒤의 빈 시간을 제안한다.
- 사용자가 앞으로도 지켜 주길 바라는 선호나 규칙을 말하면 remember로 기억한다. 기억한 선호는 아래 「기억한 사용자 선호」에 있다.

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
"""

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
    일정이나 할 일 자체는 기억하지 않는다."""
    namespace = (runtime.context.user_id, "memories")
    runtime.store.put(namespace, uuid.uuid4().hex[:6], {"fact": fact})
    return f"기억함: {fact}"


@dynamic_prompt
def with_memories(request: ModelRequest) -> str:
    """모델을 호출할 때마다 실행 중인 사용자의 기억을 시스템 프롬프트 끝에 붙인다."""
    namespace = (request.runtime.context.user_id, "memories")
    items = request.runtime.store.search(namespace)
    facts = "\n".join(f"- {i.value['fact']}" for i in items) or "- 없음"
    return SYSTEM + f"\n# 기억한 사용자 선호\n{facts}\n"


# 1단계: create_agent로 옮기기
agent = create_agent(
    "openai:gpt-6-luna",
    tools=TOOLS + [remember],  # 4단계: remember 추가
    middleware=[
        with_memories,  # 4단계: 시스템 프롬프트에 기억을 붙임
        SummarizationMiddleware(  # 3단계: 메시지가 20개를 넘으면 최근 10개만 남기고 요약
            model="openai:gpt-6-luna",
            trigger=("messages", 20),
            keep=("messages", 10),
        ),
        HumanInTheLoopMiddleware(interrupt_on={  # 삭제 전 사람 승인
            "delete_event": True,
            "delete_task": True,
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
