"""세션 1 실습: 일정 관리 CLI 챗봇"""

import os
import sys
from importlib.metadata import version

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage

model = init_chat_model("openai:gpt-6-luna")

SYSTEM = SystemMessage(
    "너는 사용자의 일정을 관리하는 비서다. "
    "일정을 정리할 때는 '- 날짜 시간 제목' 형식의 목록으로 답한다."
)


def section(title):
    """단계 구분선을 출력한다."""
    print(f"\n{'=' * 15} {title} {'=' * 15}")


if __name__ == "__main__":
    section("1단계: 환경 확인")
    print("Python", sys.version.split()[0])
    for package in ("langchain", "langchain-core", "langchain-openai", "langgraph"):
        print(package, version(package))
    print("OPENAI_API_KEY 설정됨:", "OPENAI_API_KEY" in os.environ)

    section("2단계: 모델 연결과 응답 객체")
    ai = model.invoke("내일 오후 3시에 팀 회의가 있어.")
    print("type:", type(ai).__name__)
    print("text:", ai.text)
    print("usage_metadata:", ai.usage_metadata)

    section("3단계: 메시지 role과 시스템 프롬프트")
    schedule = HumanMessage("내일 오후 3시 팀 회의, 모레 오전 10시 치과")
    print("--- 시스템 프롬프트 있음 ---")
    print(model.invoke([SYSTEM, schedule]).text)
    print("\n--- 시스템 프롬프트 없음 ---")
    print(model.invoke([schedule]).text)

    section("4단계: 상태 없는 모델 확인")
    # (1) history 없이 두 번 호출
    model.invoke([SYSTEM, HumanMessage("내일 오후 3시에 팀 회의 있어")])
    print("--- history 없이 ---")
    print(model.invoke([SYSTEM, HumanMessage("내일 일정 뭐 있지?")]).text)

    # (2) 애플리케이션이 history를 보관하고 매번 전체를 다시 전송
    history = [SYSTEM, HumanMessage("내일 오후 3시에 팀 회의 있어")]
    history.append(model.invoke(history))
    history.append(HumanMessage("내일 일정 뭐 있지?"))
    print("\n--- history를 다시 보냄 ---")
    print(model.invoke(history).text)

    section("5단계: CLI 대화 루프와 스트리밍")
    print("종료: exit 또는 quit / 대화 비우기: /reset")
    history = [SYSTEM]
    while True:
        user = input("you> ").strip()
        if user in ("exit", "quit"):
            break
        if not user:
            continue
        if user == "/reset":
            history = [SYSTEM]
            print("(대화를 비웠습니다)")
            continue
        history.append(HumanMessage(user))
        full = None
        for chunk in model.stream(history):  # 토큰 단위로 수신
            print(chunk.text, end="", flush=True)
            full = chunk if full is None else full + chunk
        print()
        history.append(AIMessage(full.text))  # 대화 기억은 애플리케이션이 추가

    # TODO 6단계: 턴마다 이번 입력·출력 토큰과 누적 입력 토큰을 출력한다
