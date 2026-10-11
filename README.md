# LLM Application을 위한 AI Agent 설계 기본: 실습

과정 「LLM Application을 위한 AI Agent 설계 기본」의 실습 저장소다. 실습은 GitHub Codespaces에서 브라우저로 진행한다.

## 실습 개요

터미널에서 대화로 일정과 할 일을 관리하는 Agent를 만든다.

```text
$ python assistant/memory_agent.py 화요일 민수
사용자: 민수 / 대화: 화요일 / 종료: exit 또는 quit
you> 다음 주 화요일 오후 2시에 팀 회의 잡아 줘
10월 20일 14:00~14:30 팀 회의를 등록했습니다. 회의는 별도 종료 시각이 없어 30분으로 잡았습니다.
```

완성했을 때의 대화 예시다. 앞 대화에서 「앞으로 회의는 30분으로 잡아 줘」라고 말해 둔 사용자의 경우이고, 답변 문구는 실행마다 다르다.

| 항목 | 내용 |
|---|---|
| 실행 형태 | 터미널 대화형 CLI |
| 프레임워크 | LangChain 1.x, LangGraph 1.x |
| 모델 | OpenAI GPT-6 Luna (`openai:gpt-6-luna`) |
| 데이터 저장 | 로컬 JSON·SQLite 파일 (마지막 단계에서는 Google Calendar·Tasks) |
| 개발 환경 | GitHub Codespaces (브라우저) |

## 세션별 진행

| 세션 | 만드는 것 |
|---|---|
| 1. AI Agent 개요 | LangChain으로 모델을 연결하고 대화 기록(history)을 직접 관리하는 일정 관리 CLI 챗봇. 턴마다 입력 토큰이 쌓이는 것을 확인한다 |
| 2. Agent 개발 프레임워크 | LangGraph `StateGraph`로 일정·할 일을 등록하는 Workflow 그래프를 만든다. 구조화 출력으로 요청을 분류하고, 빠진 정보는 `interrupt`로 되묻는다 |
| 3. Agent 도구 및 프롬프트 설계 | 일정·할 일 도구를 구현하고 모델이 도구를 골라 쓰는 Agent 루프를 만든다. 도구 오류를 결과로 돌려주고, 삭제 전에 사람 승인을 받고, 시스템 프롬프트를 테스트 케이스로 다듬는다 |
| 4. Agent 메모리 설계 | Agent를 `create_agent`로 옮기고, 대화를 파일에 저장해 이어 가는 단기 메모리와 긴 대화 요약, 사용자 선호를 기억해 다음 대화에 쓰는 장기 메모리를 붙인다 |
| 마지막 단계 (시간이 되면) | 일정은 Google Calendar, 할 일은 Google Tasks와 연동해 본인 계정에서 확인한다 |

## 진행 방식

- 이 저장소에는 개발 환경 설정(`.devcontainer/`)만 있고 실습 코드는 없다.
- 코드는 강의에서 안내하는 순서대로 Codespace에서 직접 입력하며 작성한다.
- 각 세션은 실행 가능한 상태로 끝난다.

## 시작하기

### 1. Codespace 만들기

1. 이 저장소 페이지에서 **Code**를 누르고 **Codespaces** 탭을 연다.
2. 탭 오른쪽 위의 `…` 메뉴에서 **New with options**를 고른다.
3. **Branch**가 `main`인지 확인한다.
4. 아래쪽의 `OPENAI_API_KEY` 입력란에 강의에서 안내하는 API 키를 넣는다. 입력한 값은 본인 계정의 Codespaces secret으로 저장된다.
5. **Create codespace**를 누른다.

- 처음 만들 때 패키지 설치가 자동으로 진행된다. 터미널에서 설치가 끝날 때까지 기다린다.

### 2. 환경 확인

Codespace 터미널에서 실행한다.

```bash
python --version
python -c "import os; print('OPENAI_API_KEY' in os.environ)"
python -c "import langchain, langchain_openai; print(langchain.__version__)"

# 예상 출력
# Python 3.14.<패치>
# True
# 1.4.4
```

### 3. 다시 열기

- 다음 세션에는 새로 만들지 않고 같은 Codespace를 다시 연다. 작성한 코드가 그대로 남아 있다.
- 만든 Codespace 목록은 저장소의 **Code** → **Codespaces** 탭에서 볼 수 있다.

## 개발 환경

| 항목 | 버전 |
|---|---|
| Python | 3.14 |
| `langchain` | 1.4.4 |
| `langchain-core` | 1.6.9 |
| `langchain-openai` | 1.7.0 |
| `langgraph` | 1.2.14 |
| `langgraph-checkpoint-sqlite` | 3.1.2 |
| `google-api-python-client` | 2.201.0 |
| `google-auth-oauthlib` | 1.5.0 |

설정은 [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)에 있다.

## 자주 발생하는 문제

| 증상 | 원인 | 조치 |
|---|---|---|
| 환경 확인에서 `False`가 나온다 | API 키를 넣지 않았거나, Codespace를 연 뒤에 secret을 등록했다 | [Codespaces 설정](https://github.com/settings/codespaces)에 `OPENAI_API_KEY`가 있고 이 저장소에 접근이 허용되어 있는지 확인한다. 그다음 Codespace를 멈췄다가 다시 연다 |
| `langchain` import 오류 | 패키지 설치가 끝나기 전에 실행했다 | 터미널에서 설치가 끝난 뒤 다시 실행한다 |
| `LLMChain` 등 import 오류 | 인터넷의 LangChain 0.x 예제를 썼다 | 강의 코드(LangChain 1.x)를 따른다 |
