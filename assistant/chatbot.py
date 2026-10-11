"""세션 1 실습: 일정 관리 CLI 챗봇"""

import os
import sys
from importlib.metadata import version

from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage

# TODO 2단계: init_chat_model로 모델을 연결한다

# TODO 3단계: 시스템 프롬프트를 만든다


def section(title):
    """단계 구분선을 출력한다."""
    print(f"\n{'=' * 15} {title} {'=' * 15}")


if __name__ == "__main__":
    section("1단계: 환경 확인")
    print("Python", sys.version.split()[0])
    for package in ("langchain", "langchain-core", "langchain-openai", "langgraph"):
        print(package, version(package))
    print("OPENAI_API_KEY 설정됨:", "OPENAI_API_KEY" in os.environ)

    # TODO 2단계: 모델을 호출하고 응답 객체의 text와 usage_metadata를 출력한다
    # TODO 3단계: 시스템 프롬프트와 함께 메시지 리스트로 보낸다
    # TODO 4단계: history 없이 두 번 호출한 결과와 history를 다시 보낸 결과를 비교한다
    # TODO 5단계: history를 관리하는 CLI 대화 루프를 만들고 stream으로 출력한다
    # TODO 6단계: 턴마다 이번 입력·출력 토큰과 누적 입력 토큰을 출력한다
