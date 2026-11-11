"""세션 4 실습: 메모리를 갖춘 일정 관리 Agent"""

import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from tools import TOOLS

SYSTEM = "너는 사용자의 일정을 관리하는 비서다."

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
    checkpointer=InMemorySaver(),
)


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
