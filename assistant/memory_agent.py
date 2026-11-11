"""세션 4 실습: 메모리를 갖춘 일정 관리 Agent"""

import sqlite3
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from tools import TOOLS

SYSTEM = "너는 사용자의 일정을 관리하는 비서다."

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
# 2단계: 대화를 SQLite 파일에 저장
checkpointer = SqliteSaver(
    sqlite3.connect(DATA / "checkpoints.db", check_same_thread=False)
)

# 1단계: create_agent로 옮기기
agent = create_agent(
    "openai:gpt-6.1-terra",
    tools=TOOLS,
    system_prompt=SYSTEM,
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={  # 삭제 전 사람 승인
            "delete_event": True,
        }),
    ],
    checkpointer=checkpointer,  # 2단계
)


if __name__ == "__main__":
    # 2단계: 대화 이름을 실행 파라미터로 받음
    thread = sys.argv[1] if len(sys.argv) > 1 else "기본"
    cfg = {"configurable": {"thread_id": thread}, "recursion_limit": 20}
    print(f"대화: {thread} / 종료: exit 또는 quit")
    while True:
        user = input("you> ").strip()
        if user in ("exit", "quit"):
            break
        if not user:
            continue
        result = agent.invoke({"messages": [HumanMessage(user)]}, cfg)
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
            result = agent.invoke(resume, cfg)
        print(result["messages"][-1].text)
