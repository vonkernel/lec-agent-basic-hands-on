"""세션 4 실습: 메모리를 갖춘 일정·할 일 관리 Agent"""

import uuid

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
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

# 1단계: create_agent로 옮기기
agent = create_agent(
    "openai:gpt-6-luna",
    tools=TOOLS,
    system_prompt=SYSTEM,
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={  # 삭제 전 사람 승인
            "delete_event": True,
            "delete_task": True,
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
